from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TranscriptionSegment:
    id: int
    start: float
    end: float
    text: str
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "start": round(self.start, 2),
            "end": round(self.end, 2),
            "text": self.text.strip(),
            "confidence": round(self.confidence, 2)
        }


@dataclass
class TranscriptionResult:
    text: str
    segments: List[TranscriptionSegment] = field(default_factory=list)
    language: str = "pl"
    duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "segments": [seg.to_dict() for seg in self.segments],
            "language": self.language,
            "duration": round(self.duration, 2)
        }


class TranscriptionError(Exception):
    """Exception raised when speech-to-text transcription fails."""
    pass


class TranscriptionProvider(ABC):
    """Abstract Base Class for speech-to-text transcription providers."""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """Transcribes the given audio file into text and timestamped segments."""
        pass
