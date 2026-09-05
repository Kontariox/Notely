import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple

from app.transcription.base import (
    TranscriptionError,
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptionSegment,
)

logger = logging.getLogger(__name__)


class WhisperProvider(TranscriptionProvider):
    """
    Transcription provider using OpenAI's standard Whisper library.
    Supports large-v3, medium, small, base, tiny with automatic CPU/GPU detection.
    """

    _cached_model = None
    _cached_config: Tuple[str, str] = ("", "")

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "auto"
    ):
        self.model_size = model_size
        self.device = device

    def _resolve_device(self) -> str:
        device = self.device.lower()
        cuda_available = False
        try:
            import torch
            cuda_available = torch.cuda.is_available()
        except ImportError:
            pass

        if device == "auto":
            return "cuda" if cuda_available else "cpu"
        elif device == "cuda" and not cuda_available:
            logger.warning("CUDA zostało zażądane dla OpenAI Whisper, lecz nie jest dostępne. Używam CPU.")
            return "cpu"
        return device

    def _get_model(self):
        try:
            import whisper
        except ImportError:
            raise TranscriptionError(
                "Pakiet 'openai-whisper' nie jest zainstalowany. "
                "Zainstaluj go komendą: pip install openai-whisper"
            )

        resolved_device = self._resolve_device()
        config_key = (self.model_size, resolved_device)

        if WhisperProvider._cached_model is not None and WhisperProvider._cached_config == config_key:
            return WhisperProvider._cached_model

        logger.info(f"Ładowanie modelu OpenAI Whisper: {self.model_size} na urządzeniu {resolved_device}")
        try:
            model = whisper.load_model(self.model_size, device=resolved_device)
            WhisperProvider._cached_model = model
            WhisperProvider._cached_config = config_key
            return model
        except Exception as e:
            if resolved_device == "cuda":
                logger.warning(f"Błąd ładowania Whisper na CUDA ({e}). Próbuję awaryjnie na CPU...")
                try:
                    model = whisper.load_model(self.model_size, device="cpu")
                    WhisperProvider._cached_model = model
                    WhisperProvider._cached_config = (self.model_size, "cpu")
                    return model
                except Exception as fallback_err:
                    raise TranscriptionError(f"Awaryjny fallback OpenAI Whisper na CPU nie powiódł się: {fallback_err}")
            raise TranscriptionError(f"Nie udało się załadować modelu OpenAI Whisper: {e}")

    def _transcribe_sync(self, audio_path: Path, language: Optional[str] = None) -> TranscriptionResult:
        model = self._get_model()

        options = {}
        if language and language.lower() != "auto":
            options["language"] = language

        try:
            result = model.transcribe(str(audio_path), **options)

            full_text = result.get("text", "").strip()
            detected_language = result.get("language", language or "pl")

            raw_segments = result.get("segments", [])
            transcribed_segments = []
            max_end = 0.0

            for idx, seg in enumerate(raw_segments):
                seg_text = seg.get("text", "").strip()
                if seg_text:
                    start_t = float(seg.get("start", 0.0))
                    end_t = float(seg.get("end", 0.0))
                    max_end = max(max_end, end_t)
                    transcribed_segments.append(
                        TranscriptionSegment(
                            id=idx,
                            start=start_t,
                            end=end_t,
                            text=seg_text,
                            confidence=float(seg.get("avg_logprob", 1.0))
                        )
                    )

            return TranscriptionResult(
                text=full_text,
                segments=transcribed_segments,
                language=detected_language,
                duration=max_end
            )

        except Exception as e:
            raise TranscriptionError(f"Błąd podczas transkrypcji OpenAI Whisper: {str(e)}")

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)
