from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    lesson_date: Optional[str] = None
    subject: Optional[str] = None
    original_filename: str
    duration: float = 0.0
    transcription_engine: str
    transcription: Optional[str] = None
    segments: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None
    notes: Optional[str] = None
    detected_events: List[Dict[str, Any]] = Field(default_factory=list)
    status: str
    progress_percent: int = 0
    current_stage: str
    error_message: Optional[str] = None


class LessonListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    lesson_date: Optional[str] = None
    subject: Optional[str] = None
    original_filename: str
    duration: float = 0.0
    status: str
    progress_percent: int = 0
    current_stage: str


class LessonStatusResponse(BaseModel):
    id: str
    status: str
    progress_percent: int
    current_stage: str
    error_message: Optional[str] = None


class UserSettingsSchema(BaseModel):
    transcription_engine: str = "faster-whisper"
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    whisper_language: str = "pl"

    nvidia_nim_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nvidia_temperature: float = 0.2
    nvidia_api_key: Optional[str] = None
    nvidia_base_url: Optional[str] = None

    delete_source_after_processing: bool = False
    google_calendar_auto_add: bool = False
    preferred_export_format: str = "markdown"


class UserSettingsUpdate(BaseModel):
    transcription_engine: Optional[str] = None
    whisper_model: Optional[str] = None
    whisper_device: Optional[str] = None
    whisper_compute_type: Optional[str] = None
    whisper_language: Optional[str] = None

    nvidia_nim_model: Optional[str] = None
    nvidia_temperature: Optional[float] = None
    nvidia_api_key: Optional[str] = None
    nvidia_base_url: Optional[str] = None

    delete_source_after_processing: Optional[bool] = None
    google_calendar_auto_add: Optional[bool] = None
    preferred_export_format: Optional[str] = None


class CalendarSyncRequest(BaseModel):
    lesson_id: str
    selected_indices: List[int] = Field(default_factory=list)


class ExternalAIPrepRequest(BaseModel):
    content_type: str = "all_data"
    # Options: all_data, full_transcription, prompt_transcription, summary, note
    split_parts: bool = False
    max_chars_per_part: int = 4000
    custom_prompt: Optional[str] = None


class ExternalAIPart(BaseModel):
    part_number: int
    total_parts: int
    header: str
    content: str


class ExternalAIPrepResponse(BaseModel):
    content_type: str = "analytical_prompt"
    full_text: str = ""
    parts: List[ExternalAIPart] = Field(default_factory=list)
    analytical_prompt: str = ""
    transcription: str = ""
    combined_text: str = ""
    subject: Optional[str] = None
    lesson_date: Optional[str] = None
    topic: Optional[str] = None
