import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database.models import Base
from app.database.repository import LessonRepository, SettingsRepository, GoogleOAuthRepository


@pytest_asyncio.fixture
async def async_db_session():
    # Use SQLite in-memory database for isolated testing
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_lesson_repository_lifecycle(async_db_session):
    repo = LessonRepository(async_db_session)

    # 1. Create
    lesson = await repo.create_lesson(
        original_filename="fizyka_optyka.mp3",
        file_path="/tmp/fizyka.mp3",
        lesson_date="2026-09-03",
        subject="Fizyka",
        transcription_engine="faster-whisper"
    )
    assert lesson.id is not None
    assert lesson.subject == "Fizyka"
    assert lesson.status == "pending"

    # 2. Update progress
    await repo.update_progress(lesson.id, stage="Transkrypcja w toku...", progress_percent=40)
    fetched = await repo.get_by_id(lesson.id)
    assert fetched.progress_percent == 40
    assert fetched.current_stage == "Transkrypcja w toku..."

    # 3. Update transcription (independent save)
    await repo.update_transcription(
        lesson_id=lesson.id,
        transcription="Zjawisko załamania światła...",
        segments=[{"id": 0, "start": 0.0, "end": 5.0, "text": "Zjawisko załamania..."}],
        duration=120.5
    )
    fetched = await repo.get_by_id(lesson.id)
    assert "załamania" in fetched.transcription
    assert len(fetched.segments) == 1
    assert fetched.duration == 120.5

    # 4. Update AI analysis
    await repo.update_analysis(
        lesson_id=lesson.id,
        subject="Fizyka - Optyka",
        summary="Lekcja o optyce.",
        notes="# Notatka z optyki",
        detected_events=[{"title": "Kartkówka z optyki", "type": "quiz", "confidence": 0.9}]
    )
    fetched = await repo.get_by_id(lesson.id)
    assert fetched.status == "completed"
    assert fetched.progress_percent == 100
    assert len(fetched.detected_events) == 1

    # 5. List recent
    recent = await repo.list_recent(limit=10)
    assert len(recent) == 1
    assert recent[0].id == lesson.id

    # 6. Delete
    deleted = await repo.delete_lesson(lesson.id)
    assert deleted is True
    assert await repo.get_by_id(lesson.id) is None


@pytest.mark.asyncio
async def test_settings_repository(async_db_session):
    repo = SettingsRepository(async_db_session)

    # Fetch initial defaults
    settings = await repo.get_or_create_settings()
    assert settings.transcription_engine == "faster-whisper"
    assert settings.whisper_model == "large-v3"

    # Update settings
    updated = await repo.update_settings(
        transcription_engine="whisper",
        whisper_device="cuda",
        delete_source_after_processing=True
    )
    assert updated.transcription_engine == "whisper"
    assert updated.whisper_device == "cuda"
    assert updated.delete_source_after_processing is True


@pytest.mark.asyncio
async def test_google_oauth_repository(async_db_session):
    repo = GoogleOAuthRepository(async_db_session)

    # Initial token is None
    assert await repo.get_token() is None

    # Save token
    token = await repo.save_token(
        access_token="mock_access_token",
        refresh_token="mock_refresh_token",
        email="uczen@szkola.pl"
    )
    assert token.access_token == "mock_access_token"
    assert token.email == "uczen@szkola.pl"

    # Fetch
    fetched = await repo.get_token()
    assert fetched.refresh_token == "mock_refresh_token"

    # Disconnect
    deleted = await repo.delete_token()
    assert deleted is True
    assert await repo.get_token() is None
