import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.database.repository import GoogleOAuthRepository, LessonRepository, SettingsRepository
from app.calendar.google_calendar import GoogleCalendarService, CalendarError
from app.api.schemas import CalendarSyncRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/status")
async def get_calendar_status(db: AsyncSession = Depends(get_db)):
    """Check if Google Calendar is connected and configured."""
    cal_service = GoogleCalendarService()
    google_repo = GoogleOAuthRepository(db)
    token = await google_repo.get_token()
    settings_repo = SettingsRepository(db)
    user_settings = await settings_repo.get_or_create_settings()

    return {
        "is_configured": cal_service.is_configured(),
        "is_connected": token is not None,
        "email": token.email if token else None,
        "auto_add": user_settings.google_calendar_auto_add
    }


@router.get("/auth-url")
async def get_google_auth_url():
    """Generates Google OAuth 2.0 authorization URL."""
    cal_service = GoogleCalendarService()
    try:
        url, _ = cal_service.get_auth_url()
        return {"auth_url": url}
    except CalendarError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/callback")
async def google_auth_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Handles Google OAuth redirect callback."""
    if error:
        logger.warning(f"Google OAuth zwrócił błąd: {error}")
        return RedirectResponse(url=f"/?calendar_error={error}")

    if not code:
        logger.warning("Google OAuth callback wywołany bez parametru code.")
        return RedirectResponse(url="/?calendar_error=missing_code")

    cal_service = GoogleCalendarService()
    google_repo = GoogleOAuthRepository(db)

    try:
        token_data = cal_service.exchange_code_for_token(code)
        await google_repo.save_token(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
            expiry=token_data.get("expiry"),
            email=token_data.get("email")
        )
        logger.info(f"Pomyślnie połączono z kontem Google Calendar: {token_data.get('email')}")
        return RedirectResponse(url="/?calendar=connected")
    except Exception as e:
        logger.exception(f"Błąd podczas wymiany kodu na token Google Calendar: {e}")
        return RedirectResponse(url=f"/?calendar_error={str(e)}")


@router.post("/disconnect")
async def disconnect_google_calendar(db: AsyncSession = Depends(get_db)):
    """Disconnects Google Calendar and permanently purges local OAuth tokens."""
    google_repo = GoogleOAuthRepository(db)
    deleted = await google_repo.delete_token()
    return {"status": "disconnected", "success": deleted}


@router.post("/sync")
async def sync_events_to_calendar(
    req: CalendarSyncRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates selected detected events in Google Calendar.
    Requires user confirmation of which events to add.
    """
    google_repo = GoogleOAuthRepository(db)
    token_row = await google_repo.get_token()
    if not token_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Konto Google Calendar nie jest połączone. Przejdź do Ustawień i połącz konto."
        )

    lesson_repo = LessonRepository(db)
    lesson = await lesson_repo.get_by_id(req.lesson_id)
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nie znaleziono wskazanej lekcji."
        )

    detected_events = lesson.detected_events
    if not detected_events:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="W tej lekcji nie wykryto żadnych wydarzeń."
        )

    cal_service = GoogleCalendarService()
    token_data = {
        "access_token": token_row.access_token,
        "refresh_token": token_row.refresh_token,
        "token_uri": token_row.token_uri,
        "client_id": token_row.client_id,
        "client_secret": token_row.client_secret,
        "scopes": token_row.scopes
    }

    synced_results = []
    errors = []

    for idx in req.selected_indices:
        if 0 <= idx < len(detected_events):
            event_info = detected_events[idx]
            try:
                result = await cal_service.create_event(
                    token_data=token_data,
                    event_info=event_info,
                    subject=lesson.subject or "Lekcja"
                )
                synced_results.append({
                    "index": idx,
                    "title": event_info.get("title"),
                    "google_event_id": result.get("id"),
                    "link": result.get("htmlLink")
                })
            except Exception as e:
                errors.append({"index": idx, "title": event_info.get("title"), "error": str(e)})

    return {
        "synced_count": len(synced_results),
        "synced": synced_results,
        "errors": errors
    }
