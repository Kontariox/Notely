import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

SUPPORTED_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".mp4", ".mov", ".webm", ".ogg", ".flac", ".mkv"
}


class AudioProcessingError(Exception):
    """Custom exception for audio processing and extraction failures."""
    pass


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg executable is installed and available in PATH."""
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def validate_media_file(file_path: Path) -> None:
    """Validate that the media file exists, is non-empty, and has a supported extension."""
    if not file_path.exists():
        raise AudioProcessingError(f"Plik nie istnieje: {file_path}")
    if file_path.stat().st_size == 0:
        raise AudioProcessingError("Przesłany plik jest pusty (0 bajtów).")
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise AudioProcessingError(
            f"Nieobsługiwany format pliku: {suffix}. "
            f"Obsługiwane formaty: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )


async def get_audio_duration(file_path: Path) -> float:
    """Get the duration of an audio/video file in seconds using ffprobe."""
    if not shutil.which("ffprobe"):
        # Fallback if ffprobe is missing but ffmpeg is present
        return 0.0

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return 0.0
        duration_str = stdout.decode().strip()
        return float(duration_str) if duration_str else 0.0
    except Exception:
        return 0.0


async def extract_and_convert_audio(
    input_path: Path,
    output_dir: Path,
    target_sample_rate: int = 16000
) -> Tuple[Path, float]:
    """
    Extracts audio from audio or video file and converts it to a standard 16kHz mono WAV file
    optimized for Whisper speech recognition engines.
    Returns (converted_wav_path, duration_seconds).
    """
    if not is_ffmpeg_available():
        raise AudioProcessingError(
            "Brak programu FFmpeg w systemie. Zainstaluj FFmpeg (np. sudo apt install ffmpeg) "
            "aby przetwarzać pliki audio i wideo."
        )

    validate_media_file(input_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = f"{input_path.stem}_converted.wav"
    output_path = output_dir / output_filename

    # FFmpeg command: convert to 16kHz mono 16-bit PCM WAV
    cmd = [
        "ffmpeg",
        "-y",               # Overwrite output without asking
        "-i", str(input_path),
        "-vn",              # Disable video recording
        "-acodec", "pcm_s16le",
        "-ar", str(target_sample_rate),
        "-ac", "1",         # Mono
        str(output_path)
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace")
            raise AudioProcessingError(f"Błąd konwersji audio przez FFmpeg: {err_msg[:300]}")

        duration = await get_audio_duration(output_path)
        return output_path, duration

    except AudioProcessingError:
        raise
    except Exception as e:
        raise AudioProcessingError(f"Nieoczekiwany błąd podczas przygotowywania audio: {str(e)}")


def cleanup_file(file_path: Optional[Path]) -> None:
    """Safely remove a file from filesystem if it exists."""
    if file_path and file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass
