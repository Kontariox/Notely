from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from app.transcription.base import TranscriptionResult


@dataclass
class DetectedEvent:
    type: str  # test, quiz, homework, book, presentation, project, deadline, other
    title: str
    date: Optional[str]  # YYYY-MM-DD or None
    raw_date_expression: Optional[str]
    time: Optional[str]
    description: str
    confidence: float
    source_text: str
    is_date_calculated: bool = False
    date_explanation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "title": self.title,
            "date": self.date,
            "raw_date_expression": self.raw_date_expression,
            "time": self.time,
            "description": self.description,
            "confidence": round(self.confidence, 2),
            "source_text": self.source_text,
            "is_date_calculated": self.is_date_calculated,
            "date_explanation": self.date_explanation
        }


@dataclass
class LessonAnalysisResult:
    subject: str
    topic: str
    summary: str
    notes: str
    events: List[DetectedEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "topic": self.topic,
            "summary": self.summary,
            "notes": self.notes,
            "events": [e.to_dict() for e in self.events]
        }


class AIProvider(ABC):
    """Abstract interface for AI analysis providers."""

    @abstractmethod
    async def analyze_lesson(
        self,
        transcription_result: TranscriptionResult,
        lesson_date: Optional[str] = None,
        given_subject: Optional[str] = None
    ) -> LessonAnalysisResult:
        """Analyzes transcription, extracts events, and creates structured notes."""
        pass
