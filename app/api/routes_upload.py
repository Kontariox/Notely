import asyncio
from pathlib import Path
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.session import get_db
from app.database.repository import LessonRepository, SettingsRepository
from app.services.audio import SUPPORTED_EXTENSIONS
from app.services.pipeline import LessonPipeline
from app.api.schemas import LessonResponse

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def upload_and_process_recording(
    file: UploadFile = File(...),
    lesson_date: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    # Advanced overrides (optional)
    transcription_engine: Optional[str] = Form(None),
    whisper_model: Optional[str] = Form(None),
    whisper_device: Optional[str] = Form(None),
    whisper_compute_type: Optional[str] = Form(None),
    whisper_language: Optional[str] = Form(None),
    nim_model: Optional[str] = Form(None),
    nim_api_key: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a lesson audio/video recording (MP3, WAV, M4A, AAC, MP4, MOV, WEBM)
    and initiate the background processing pipeline.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brak nazwy pliku w żądaniu."
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nieobsługiwany format: '{ext}'. Dozwolone formaty: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Generate unique storage filename
    unique_id = str(uuid.uuid4())
    safe_filename = f"{unique_id}_{Path(file.filename).name}"
    target_path = settings.UPLOAD_DIR / safe_filename

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Przesłany plik jest pusty (0 bajtów)."
            )

        with open(target_path, "wb") as f:
            f.write(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Błąd zapisu pliku na serwerze: {str(e)}"
        )

    # Fetch default engine from user settings if not overridden
    settings_repo = SettingsRepository(db)
    user_settings = await settings_repo.get_or_create_settings()
    engine = transcription_engine or user_settings.transcription_engine

    # Create DB entry
    lesson_repo = LessonRepository(db)
    lesson = await lesson_repo.create_lesson(
        original_filename=file.filename,
        file_path=str(target_path),
        lesson_date=lesson_date or None,
        subject=subject or "Nieokreślony",
        transcription_engine=engine
    )

    # Launch pipeline asynchronously in background
    asyncio.create_task(
        LessonPipeline.process_lesson(
            lesson_id=lesson.id,
            engine_override=transcription_engine,
            model_override=whisper_model,
            device_override=whisper_device,
            compute_override=whisper_compute_type,
            language_override=whisper_language,
            nim_model_override=nim_model,
            nim_api_key_override=nim_api_key
        )
    )

    return LessonResponse(
        id=lesson.id,
        created_at=lesson.created_at,
        lesson_date=lesson.lesson_date,
        subject=lesson.subject,
        original_filename=lesson.original_filename,
        duration=lesson.duration,
        transcription_engine=lesson.transcription_engine,
        transcription=lesson.transcription,
        segments=lesson.segments,
        summary=lesson.summary,
        notes=lesson.notes,
        detected_events=lesson.detected_events,
        status=lesson.status,
        progress_percent=lesson.progress_percent,
        current_stage=lesson.current_stage,
        error_message=lesson.error_message
    )
