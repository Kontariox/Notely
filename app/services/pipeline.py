import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.config import settings
from app.database.session import AsyncSessionLocal
from app.database.repository import (
    GoogleOAuthRepository,
    LessonRepository,
    SettingsRepository,
)
from app.services.audio import (
    AudioProcessingError,
    cleanup_file,
    extract_and_convert_audio,
)
from app.transcription.base import TranscriptionError
from app.transcription.factory import get_transcription_provider
from app.ai.nvidia_nim import NvidiaNimProvider, AIProviderError
from app.calendar.google_calendar import GoogleCalendarService

logger = logging.getLogger(__name__)


class LessonPipeline:
    """
    Modular processing pipeline orchestrating:
    Validation -> Audio Conversion -> Speech-to-Text Transcription ->
    Independent Raw Save -> Chunking & AI Analysis -> Structured Extraction ->
    Optional Calendar Sync -> Cleanup.
    """

    @classmethod
    async def process_lesson(
        cls,
        lesson_id: str,
        engine_override: Optional[str] = None,
        model_override: Optional[str] = None,
        device_override: Optional[str] = None,
        compute_override: Optional[str] = None,
        language_override: Optional[str] = None,
        nim_model_override: Optional[str] = None,
        nim_api_key_override: Optional[str] = None
    ) -> None:
        """Executes the full pipeline for a given lesson."""
        converted_wav: Optional[Path] = None
        raw_upload_path: Optional[Path] = None

        async with AsyncSessionLocal() as session:
            lesson_repo = LessonRepository(session)
            settings_repo = SettingsRepository(session)
            google_repo = GoogleOAuthRepository(session)

            user_settings = await settings_repo.get_or_create_settings()
            lesson = await lesson_repo.get_by_id(lesson_id)
            if not lesson:
                logger.error(f"[Pipeline] Nie znaleziono lekcji o ID: {lesson_id}")
                return

            try:
                raw_upload_path = Path(lesson.file_path) if lesson.file_path else None
                if not raw_upload_path or not raw_upload_path.exists():
                    raise AudioProcessingError("Brak pliku źródłowego na serwerze.")

                # STAGE 1: Audio Extraction / Conversion
                await lesson_repo.update_progress(
                    lesson_id,
                    stage="Konwersja i przygotowanie strumienia audio (FFmpeg)...",
                    progress_percent=15,
                    status="audio_processing"
                )

                converted_wav, duration = await extract_and_convert_audio(
                    input_path=raw_upload_path,
                    output_dir=settings.PROCESSED_DIR
                )

                # STAGE 2: Speech-to-Text Transcription
                engine = engine_override or user_settings.transcription_engine or settings.TRANSCRIPTION_ENGINE
                model = model_override or user_settings.whisper_model or settings.WHISPER_MODEL
                device = device_override or user_settings.whisper_device or settings.WHISPER_DEVICE
                compute = compute_override or user_settings.whisper_compute_type or settings.WHISPER_COMPUTE_TYPE
                language = language_override or user_settings.whisper_language or settings.WHISPER_LANGUAGE

                await lesson_repo.update_progress(
                    lesson_id,
                    stage=f"Transkrypcja mowy ({engine} {model})...",
                    progress_percent=35,
                    status="transcribing"
                )

                provider = get_transcription_provider(
                    engine_name=engine,
                    model_name=model,
                    device=device,
                    compute_type=compute
                )

                transcription_result = await provider.transcribe(
                    audio_path=converted_wav,
                    language=language
                )

                # STAGE 3: Independent Save of Raw Transcription
                # This guarantees transcription is preserved even if AI steps fail!
                await lesson_repo.update_transcription(
                    lesson_id=lesson_id,
                    transcription=transcription_result.text,
                    segments=[s.to_dict() for s in transcription_result.segments],
                    duration=duration or transcription_result.duration
                )

                # STAGE 4: AI Analysis & Information Extraction
                await lesson_repo.update_progress(
                    lesson_id,
                    stage="Analiza AI, wykrywanie wydarzeń i synteza notatki (NVIDIA NIM)...",
                    progress_percent=70,
                    status="analyzing"
                )

                nim_key = nim_api_key_override or user_settings.nvidia_api_key or settings.NVIDIA_API_KEY
                nim_model = nim_model_override or user_settings.nvidia_nim_model or settings.NVIDIA_NIM_MODEL
                nim_base_url = user_settings.nvidia_base_url or settings.NVIDIA_BASE_URL

                ai_provider = NvidiaNimProvider(
                    api_key=nim_key,
                    model=nim_model,
                    base_url=nim_base_url,
                    temperature=user_settings.nvidia_temperature
                )

                try:
                    analysis_result = await ai_provider.analyze_lesson(
                        transcription_result=transcription_result,
                        lesson_date=lesson.lesson_date,
                        given_subject=lesson.subject
                    )

                    await lesson_repo.update_analysis(
                        lesson_id=lesson_id,
                        subject=analysis_result.subject,
                        summary=analysis_result.summary,
                        notes=analysis_result.notes,
                        detected_events=[e.to_dict() for e in analysis_result.events]
                    )

                    # STAGE 5: Optional Google Calendar Auto-Add
                    auto_add_calendar = user_settings.google_calendar_auto_add or settings.GOOGLE_CALENDAR_AUTO_ADD
                    if auto_add_calendar:
                        token_row = await google_repo.get_token()
                        if token_row:
                            cal_service = GoogleCalendarService()
                            token_data = {
                                "access_token": token_row.access_token,
                                "refresh_token": token_row.refresh_token,
                                "token_uri": token_row.token_uri,
                                "client_id": token_row.client_id,
                                "client_secret": token_row.client_secret,
                                "scopes": token_row.scopes
                            }
                            for ev in analysis_result.events:
                                if ev.date and ev.confidence >= 0.85:
                                    try:
                                        await cal_service.create_event(
                                            token_data=token_data,
                                            event_info=ev.to_dict(),
                                            subject=analysis_result.subject
                                        )
                                    except Exception as cal_err:
                                        logger.warning(f"Błąd auto-dodawania do kalendarza: {cal_err}")

                except AIProviderError as ai_err:
                    # AI failed, but transcription was already saved! Mark lesson as transcribed with notice.
                    logger.error(f"[Pipeline] Błąd analizy AI dla lekcji {lesson_id}: {ai_err}")
                    await lesson_repo.update_progress(
                        lesson_id,
                        stage=f"Transkrypcja zachowana. Błąd analizy AI: {ai_err}",
                        progress_percent=100,
                        status="completed"
                    )
                    lesson_cur = await lesson_repo.get_by_id(lesson_id)
                    if lesson_cur:
                        lesson_cur.notes = f"# Transkrypcja lekcji\n\n*(Analiza AI nie powiodła się: {ai_err})*\n\n{transcription_result.text}"
                        await session.commit()

                # STAGE 6: Privacy & Cleanup
                delete_source = user_settings.delete_source_after_processing or settings.DELETE_SOURCE_AFTER_PROCESSING
                if delete_source and raw_upload_path and raw_upload_path.exists():
                    cleanup_file(raw_upload_path)
                    lesson_cur = await lesson_repo.get_by_id(lesson_id)
                    if lesson_cur:
                        lesson_cur.file_path = None
                        await session.commit()

                # Always clean up converted intermediate WAV to save disk space
                if converted_wav and converted_wav.exists():
                    cleanup_file(converted_wav)

                logger.info(f"[Pipeline] Zakończono z sukcesem przetwarzanie lekcji {lesson_id}")

            except (AudioProcessingError, TranscriptionError) as known_err:
                logger.error(f"[Pipeline] Błąd przetwarzania lekcji {lesson_id}: {known_err}")
                await lesson_repo.set_failed(lesson_id, str(known_err))
                if converted_wav and converted_wav.exists():
                    cleanup_file(converted_wav)
            except Exception as unk_err:
                logger.exception(f"[Pipeline] Nieoczekiwany wyjątek w pipeline: {unk_err}")
                await lesson_repo.set_failed(lesson_id, f"Nieoczekiwany błąd systemowy: {str(unk_err)}")
                if converted_wav and converted_wav.exists():
                    cleanup_file(converted_wav)
