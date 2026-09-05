from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application settings
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "dev-secret-key-change-in-production-32-chars-min"

    # NVIDIA NIM settings
    NVIDIA_API_KEY: str = ""
    NVIDIA_NIM_MODEL: str = "nvidia/nemotron-3-ultra-550b-a55b"
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_RATE_LIMIT_RPM: int = 40
    NVIDIA_MAX_RETRIES: int = 4
    NVIDIA_INITIAL_BACKOFF_SECONDS: float = 2.0
    NVIDIA_REQUEST_TIMEOUT_SECONDS: float = 120.0

    # Transcription settings
    TRANSCRIPTION_ENGINE: str = "faster-whisper"  # faster-whisper or whisper
    WHISPER_MODEL: str = "large-v3"
    WHISPER_DEVICE: str = "auto"  # auto, cuda, cpu
    WHISPER_COMPUTE_TYPE: str = "auto"  # auto, float16, int8, float32
    WHISPER_LANGUAGE: Optional[str] = "pl"

    # Storage & Data Management
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    DELETE_SOURCE_AFTER_PROCESSING: bool = False

    # Google Calendar OAuth 2.0
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/calendar/callback"
    GOOGLE_CALENDAR_AUTO_ADD: bool = False

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{Path(__file__).resolve().parent.parent / 'data' / 'notely.db'}"

    HF_TOKEN: str = ""

    def ensure_directories(self) -> None:
        """Ensure necessary storage directories exist."""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        if "sqlite" in self.DATABASE_URL:
            db_path = self.BASE_DIR / "data"
            db_path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
