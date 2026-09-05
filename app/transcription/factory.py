from typing import Optional
from app.config import settings
from app.transcription.base import TranscriptionProvider, TranscriptionError
from app.transcription.faster_whisper_provider import FasterWhisperProvider
from app.transcription.whisper_provider import WhisperProvider


def get_transcription_provider(
    engine_name: Optional[str] = None,
    model_name: Optional[str] = None,
    device: Optional[str] = None,
    compute_type: Optional[str] = None
) -> TranscriptionProvider:
    """
    Factory function returning the configured TranscriptionProvider.
    Defaults to settings if specific options are not provided.
    """
    engine = (engine_name or settings.TRANSCRIPTION_ENGINE).strip().lower()
    model = model_name or settings.WHISPER_MODEL
    dev = device or settings.WHISPER_DEVICE
    comp = compute_type or settings.WHISPER_COMPUTE_TYPE

    if engine in ("faster-whisper", "faster_whisper"):
        return FasterWhisperProvider(model_size=model, device=dev, compute_type=comp)
    elif engine in ("whisper", "openai-whisper", "openai_whisper"):
        return WhisperProvider(model_size=model, device=dev)
    else:
        raise TranscriptionError(
            f"Nieznany silnik transkrypcji: '{engine}'. "
            f"Dostępne opcje to: 'faster-whisper' oraz 'whisper'."
        )
