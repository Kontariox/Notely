import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.session import init_db


@pytest_asyncio.fixture
async def client():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_serve_index(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Notely" in response.text
    assert "AI Notatki z Lekcji" in response.text
    assert "historySubjectFilter" in response.text
    assert "historyDateSort" in response.text
    assert "uploadGrid" in response.text


@pytest.mark.asyncio
async def test_get_and_update_settings(client):
    # GET settings
    get_res = await client.get("/api/settings")
    assert get_res.status_code == 200
    settings_data = get_res.json()
    assert "transcription_engine" in settings_data

    # POST update settings
    update_payload = {
        "transcription_engine": "faster-whisper",
        "whisper_model": "large-v3",
        "whisper_device": "cpu",
        "nvidia_nim_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "nvidia_temperature": 0.25,
        "delete_source_after_processing": False,
        "google_calendar_auto_add": False
    }
    post_res = await client.post("/api/settings", json=update_payload)
    assert post_res.status_code == 200
    updated_data = post_res.json()
    assert updated_data["whisper_device"] == "cpu"
    assert updated_data["nvidia_temperature"] == 0.25


@pytest.mark.asyncio
async def test_lessons_list_empty_or_valid(client):
    response = await client.get("/api/lessons")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_calendar_status(client):
    response = await client.get("/api/calendar/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_connected" in data
    assert "is_configured" in data


@pytest.mark.asyncio
async def test_calendar_auth_url_no_code_challenge():
    from app.calendar.google_calendar import GoogleCalendarService
    service = GoogleCalendarService(
        client_id="dummy_client_id.apps.googleusercontent.com",
        client_secret="dummy_client_secret",
        redirect_uri="http://localhost:8000/api/calendar/callback"
    )
    url, state = service.get_auth_url()
    assert "code_challenge" not in url
    assert "code_challenge_method" not in url
    assert "client_id=dummy_client_id" in url
    assert state == "notely_auth"


@pytest.mark.asyncio
async def test_calendar_callback_handles_error(client):
    response = await client.get("/api/calendar/callback?error=access_denied", follow_redirects=False)
    assert response.status_code == 307
    assert "/?calendar_error=access_denied" in response.headers["location"]


@pytest.mark.asyncio
async def test_calendar_disconnect(client):
    response = await client.post("/api/calendar/disconnect")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "disconnected"


@pytest.mark.asyncio
async def test_external_ai_prep_no_forced_split(client):
    from app.database.session import AsyncSessionLocal
    from app.database.repository import LessonRepository

    async with AsyncSessionLocal() as session:
        repo = LessonRepository(session)
        lesson = await repo.create_lesson(
            original_filename="fizyka_kwantowa.mp3",
            file_path=None,
            lesson_date="2026-09-05",
            subject="Fizyka",
            transcription_engine="faster-whisper"
        )
        # Add long transcription > 4000 characters
        long_transcription = "To jest wykład z fizyki kwantowej. " * 200
        await repo.update_transcription(
            lesson.id,
            transcription=long_transcription,
            segments=[],
            duration=3600.0
        )
        lesson_id = lesson.id

    # Test GET
    get_res = await client.get(f"/api/lessons/{lesson_id}/ai-prep")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert "analytical_prompt" in get_data
    assert "transcription" in get_data
    assert "combined_text" in get_data
    assert "Fizyka" in get_data["analytical_prompt"]
    # Verify no forced split when split_parts is False
    assert len(get_data["parts"]) == 0

    # Test POST with split_parts=False
    post_res = await client.post(
        f"/api/lessons/{lesson_id}/ai-prep",
        json={"split_parts": False}
    )
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert len(post_data["parts"]) == 0
    assert post_data["transcription"] == long_transcription

    # Test POST with split_parts=True
    split_res = await client.post(
        f"/api/lessons/{lesson_id}/ai-prep",
        json={"split_parts": True, "max_chars_per_part": 2000}
    )
    assert split_res.status_code == 200
    split_data = split_res.json()
    assert len(split_data["parts"]) > 1
