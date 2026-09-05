from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
import json

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    lesson_date = Column(String(10), nullable=True)  # YYYY-MM-DD
    subject = Column(String(120), nullable=True, default="Nieokreślony")
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=True)
    duration = Column(Float, default=0.0)  # in seconds
    transcription_engine = Column(String(60), nullable=False, default="faster-whisper")

    # Content
    transcription = Column(Text, nullable=True)  # Raw full transcription
    segments_json = Column(Text, nullable=True)  # List of segment dicts
    summary = Column(Text, nullable=True)        # Brief summary
    notes = Column(Text, nullable=True)          # Structured markdown notes
    detected_events_json = Column(Text, nullable=True)  # Structured events JSON

    # Pipeline progress & status
    status = Column(String(30), default="pending", nullable=False)
    # pending, audio_processing, transcribing, analyzing, completed, failed
    progress_percent = Column(Integer, default=0)
    current_stage = Column(String(120), default="Oczekiwanie na start")
    error_message = Column(Text, nullable=True)

    # Extensibility
    metadata_json = Column(Text, nullable=True)

    @property
    def segments(self) -> List[Dict[str, Any]]:
        if self.segments_json:
            try:
                return json.loads(self.segments_json)
            except Exception:
                return []
        return []

    @segments.setter
    def segments(self, value: List[Dict[str, Any]]) -> None:
        self.segments_json = json.dumps(value, ensure_ascii=False)

    @property
    def detected_events(self) -> List[Dict[str, Any]]:
        if self.detected_events_json:
            try:
                return json.loads(self.detected_events_json)
            except Exception:
                return []
        return []

    @detected_events.setter
    def detected_events(self, value: List[Dict[str, Any]]) -> None:
        self.detected_events_json = json.dumps(value, ensure_ascii=False)

    @property
    def extra_metadata(self) -> Dict[str, Any]:
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except Exception:
                return {}
        return {}

    @extra_metadata.setter
    def extra_metadata(self, value: Dict[str, Any]) -> None:
        self.metadata_json = json.dumps(value, ensure_ascii=False)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, default=1)
    transcription_engine = Column(String(60), default="faster-whisper", nullable=False)
    whisper_model = Column(String(60), default="large-v3", nullable=False)
    whisper_device = Column(String(20), default="auto", nullable=False)
    whisper_compute_type = Column(String(30), default="auto", nullable=False)
    whisper_language = Column(String(10), default="pl", nullable=False)

    nvidia_nim_model = Column(String(120), default="nvidia/nemotron-3-ultra-550b-a55b", nullable=False)
    nvidia_temperature = Column(Float, default=0.2, nullable=False)
    nvidia_api_key = Column(String(255), nullable=True)
    nvidia_base_url = Column(String(255), nullable=True)

    delete_source_after_processing = Column(Boolean, default=False, nullable=False)
    google_calendar_auto_add = Column(Boolean, default=False, nullable=False)
    preferred_export_format = Column(String(20), default="markdown", nullable=False)

    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)


class GoogleOAuthToken(Base):
    __tablename__ = "google_oauth_tokens"

    id = Column(Integer, primary_key=True, default=1)
    email = Column(String(255), nullable=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_uri = Column(String(255), default="https://oauth2.googleapis.com/token")
    client_id = Column(String(255), nullable=True)
    client_secret = Column(String(255), nullable=True)
    scopes = Column(Text, nullable=True)
    expiry = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)
