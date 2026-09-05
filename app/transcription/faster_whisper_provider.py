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


class FasterWhisperProvider(TranscriptionProvider):
    """
    Transcription provider using faster-whisper (CTranslate2).
    Optimized for high performance and low memory footprint with CPU/GPU auto-detection.
    """

    _cached_model = None
    _cached_config: Tuple[str, str, str] = ("", "", "")

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "auto",
        compute_type: str = "auto"
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    def _resolve_device_and_compute(self) -> Tuple[str, str]:
        """Resolve device and compute_type based on available hardware."""
        device = self.device.lower()
        compute = self.compute_type.lower()

        # Check CUDA availability
        cuda_available = False
        try:
            import torch
            cuda_available = torch.cuda.is_available()
        except ImportError:
            pass

        if device == "auto":
            device = "cuda" if cuda_available else "cpu"
        elif device == "cuda" and not cuda_available:
            logger.warning("CUDA zostało zażądane, lecz nie jest dostępne. Przełączam na CPU.")
            device = "cpu"

        if compute == "auto":
            if device == "cuda":
                compute = "float16"
            else:
                compute = "int8"

        # On CPU, float16 is usually not supported by ctranslate2
        if device == "cpu" and compute in ("float16", "int8_float16"):
            compute = "int8"

        return device, compute

    def _get_model(self):
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise TranscriptionError(
                "Pakiet 'faster-whisper' nie jest zainstalowany. "
                "Zainstaluj go komendą: pip install faster-whisper"
            )

        resolved_device, resolved_compute = self._resolve_device_and_compute()
        config_key = (self.model_size, resolved_device, resolved_compute)

        if FasterWhisperProvider._cached_model is not None and FasterWhisperProvider._cached_config == config_key:
            return FasterWhisperProvider._cached_model

        logger.info(
            f"Ładowanie modelu faster-whisper: {self.model_size} (device={resolved_device}, compute_type={resolved_compute})"
        )
        try:
            model = WhisperModel(
                self.model_size,
                device=resolved_device,
                compute_type=resolved_compute
            )
            FasterWhisperProvider._cached_model = model
            FasterWhisperProvider._cached_config = config_key
            return model
        except Exception as e:
            # If failed on CUDA, attempt emergency CPU fallback
            if resolved_device == "cuda":
                logger.warning(f"Błąd inicjalizacji faster-whisper na CUDA ({e}). Próbuję awaryjnie CPU (int8)...")
                try:
                    model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                    FasterWhisperProvider._cached_model = model
                    FasterWhisperProvider._cached_config = (self.model_size, "cpu", "int8")
                    return model
                except Exception as fallback_err:
                    raise TranscriptionError(f"Awaryjny fallback na CPU również nie powiódł się: {fallback_err}")
            raise TranscriptionError(f"Nie udało się załadować modelu faster-whisper: {e}")

    def _transcribe_sync(self, audio_path: Path, language: Optional[str] = None) -> TranscriptionResult:
        model = self._get_model()

        try:
            segments_gen, info = model.transcribe(
                str(audio_path),
                language=language if language and language.lower() != "auto" else None,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            detected_language = info.language if info else (language or "pl")
            duration = info.duration if info else 0.0

            transcribed_segments = []
            full_text_parts = []

            for idx, seg in enumerate(segments_gen):
                seg_text = seg.text.strip()
                if seg_text:
                    transcribed_segments.append(
                        TranscriptionSegment(
                            id=idx,
                            start=seg.start,
                            end=seg.end,
                            text=seg_text,
                            confidence=getattr(seg, "avg_logprob", 1.0)
                        )
                    )
                    full_text_parts.append(seg_text)

            full_text = " ".join(full_text_parts)
            return TranscriptionResult(
                text=full_text,
                segments=transcribed_segments,
                language=detected_language,
                duration=duration
            )

        except Exception as e:
            raise TranscriptionError(f"Błąd podczas transkrypcji faster-whisper: {str(e)}")

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)
