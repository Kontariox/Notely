from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Lesson, UserSettings, GoogleOAuthToken


class LessonRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_lesson(
        self,
        original_filename: str,
        file_path: Optional[str],
        lesson_date: Optional[str] = None,
        subject: Optional[str] = None,
        transcription_engine: str = "faster-whisper"
    ) -> Lesson:
        lesson = Lesson(
            original_filename=original_filename,
            file_path=file_path,
            lesson_date=lesson_date,
            subject=subject or "Nieokreślony",
            transcription_engine=transcription_engine,
            status="pending",
            progress_percent=5,
            current_stage="Plik przesłany"
        )
        self.session.add(lesson)
        await self.session.commit()
        await self.session.refresh(lesson)
        return lesson

    async def get_by_id(self, lesson_id: str) -> Optional[Lesson]:
        stmt = select(Lesson).where(Lesson.id == lesson_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 50) -> List[Lesson]:
        stmt = select(Lesson).order_by(desc(Lesson.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_progress(
        self,
        lesson_id: str,
        stage: str,
        progress_percent: int,
        status: Optional[str] = None
    ) -> None:
        lesson = await self.get_by_id(lesson_id)
        if lesson:
            lesson.current_stage = stage
            lesson.progress_percent = progress_percent
            if status:
                lesson.status = status
            await self.session.commit()

    async def update_transcription(
        self,
        lesson_id: str,
        transcription: str,
        segments: List[Dict[str, Any]],
        duration: float
    ) -> None:
        lesson = await self.get_by_id(lesson_id)
        if lesson:
            lesson.transcription = transcription
            lesson.segments = segments
            lesson.duration = duration
            lesson.current_stage = "Transkrypcja zakończona"
            lesson.progress_percent = 50
            await self.session.commit()

    async def update_analysis(
        self,
        lesson_id: str,
        subject: Optional[str],
        summary: str,
        notes: str,
        detected_events: List[Dict[str, Any]]
    ) -> None:
        lesson = await self.get_by_id(lesson_id)
        if lesson:
            if subject and (lesson.subject == "Nieokreślony" or not lesson.subject):
                lesson.subject = subject
            lesson.summary = summary
            lesson.notes = notes
            lesson.detected_events = detected_events
            lesson.status = "completed"
            lesson.progress_percent = 100
            lesson.current_stage = "Przetwarzanie zakończone pomyślnie"
            await self.session.commit()

    async def set_failed(self, lesson_id: str, error_message: str) -> None:
        lesson = await self.get_by_id(lesson_id)
        if lesson:
            lesson.status = "failed"
            lesson.error_message = error_message
            lesson.current_stage = f"Błąd: {error_message[:100]}"
            await self.session.commit()

    async def delete_lesson(self, lesson_id: str) -> bool:
        lesson = await self.get_by_id(lesson_id)
        if lesson:
            await self.session.delete(lesson)
            await self.session.commit()
            return True
        return False


class SettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_settings(self) -> UserSettings:
        stmt = select(UserSettings).where(UserSettings.id == 1)
        result = await self.session.execute(stmt)
        settings_row = result.scalar_one_or_none()
        if not settings_row:
            settings_row = UserSettings(id=1)
            self.session.add(settings_row)
            await self.session.commit()
            await self.session.refresh(settings_row)
        return settings_row

    async def update_settings(self, **kwargs) -> UserSettings:
        settings_row = await self.get_or_create_settings()
        for key, value in kwargs.items():
            if hasattr(settings_row, key) and value is not None:
                setattr(settings_row, key, value)
        settings_row.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(settings_row)
        return settings_row


class GoogleOAuthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_token(self) -> Optional[GoogleOAuthToken]:
        stmt = select(GoogleOAuthToken).where(GoogleOAuthToken.id == 1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_token(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_uri: str = "https://oauth2.googleapis.com/token",
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        scopes: Optional[str] = None,
        expiry: Optional[datetime] = None,
        email: Optional[str] = None
    ) -> GoogleOAuthToken:
        token = await self.get_token()
        if not token:
            token = GoogleOAuthToken(id=1)
            self.session.add(token)

        token.access_token = access_token
        if refresh_token:
            token.refresh_token = refresh_token
        token.token_uri = token_uri
        if client_id:
            token.client_id = client_id
        if client_secret:
            token.client_secret = client_secret
        if scopes:
            token.scopes = scopes
        if expiry:
            token.expiry = expiry
        if email:
            token.email = email
        token.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(token)
        return token

    async def delete_token(self) -> bool:
        token = await self.get_token()
        if token:
            await self.session.delete(token)
            await self.session.commit()
            return True
        return False
