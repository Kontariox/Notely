import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid"
]


class CalendarError(Exception):
    """Exception for Google Calendar API and OAuth errors."""
    pass


class GoogleCalendarService:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None
    ):
        self.client_id = client_id or settings.GOOGLE_CLIENT_ID
        self.client_secret = client_secret or settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_client_config(self) -> Dict[str, Any]:
        return {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

    def get_auth_url(self, state: str = "notely_auth") -> Tuple[str, str]:
        if not self.is_configured():
            raise CalendarError(
                "Google Calendar nie jest skonfigurowany. Ustaw GOOGLE_CLIENT_ID oraz GOOGLE_CLIENT_SECRET w .env."
            )

        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=SCOPES,
            redirect_uri=self.redirect_uri,
            autogenerate_code_verifier=False
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state
        )
        return auth_url, state

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise CalendarError("Google Calendar nie jest skonfigurowany.")

        flow = Flow.from_client_config(
            self._get_client_config(),
            scopes=SCOPES,
            redirect_uri=self.redirect_uri,
            autogenerate_code_verifier=False
        )
        flow.fetch_token(code=code)
        creds = flow.credentials

        # Get user email
        user_email = None
        try:
            from googleapiclient.discovery import build as build_service
            oauth2_service = build_service("oauth2", "v2", credentials=creds)
            user_info = oauth2_service.userinfo().get().execute()
            user_email = user_info.get("email")
        except Exception as e:
            logger.warning(f"Nie udało się pobrać adresu e-mail użytkownika Google: {e}")

        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id or self.client_id,
            "client_secret": creds.client_secret or self.client_secret,
            "scopes": " ".join(creds.scopes) if creds.scopes else " ".join(SCOPES),
            "expiry": creds.expiry,
            "email": user_email
        }

    def _build_credentials(self, token_data: Dict[str, Any]) -> Credentials:
        creds = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id") or self.client_id,
            client_secret=token_data.get("client_secret") or self.client_secret,
            scopes=token_data.get("scopes", "").split() if token_data.get("scopes") else SCOPES
        )

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                raise CalendarError(f"Nie udało się odświeżyć tokenu Google: {e}")

        return creds

    def _create_event_sync(
        self,
        token_data: Dict[str, Any],
        event_info: Dict[str, Any],
        subject: str = "Lekcja"
    ) -> Dict[str, Any]:
        creds = self._build_credentials(token_data)
        service = build("calendar", "v3", credentials=creds)

        title = event_info.get("title") or "Wydarzenie szkolne"
        date_str = event_info.get("date")
        time_str = event_info.get("time")
        description = event_info.get("description", "")
        source_text = event_info.get("source_text", "")
        confidence = event_info.get("confidence", 1.0)
        date_explanation = event_info.get("date_explanation", "")

        # Rich formatted description
        full_desc = (
            f"Przedmiot: {subject}\n"
            f"Opis: {description}\n\n"
            f"Cytat z lekcji: \"{source_text}\"\n"
            f"Pewność detekcji AI: {int(confidence * 100)}%\n"
        )
        if date_explanation:
            full_desc += f"Informacja o dacie: {date_explanation}\n"
        full_desc += "\nWygenerowano automatycznie przez aplikację Notely."

        event_body: Dict[str, Any] = {
            "summary": f"[{subject}] {title}",
            "description": full_desc,
            "status": "confirmed",
        }

        # Date / Time configuration
        if date_str and time_str:
            # Event with specific time
            try:
                dt_start = datetime.fromisoformat(f"{date_str}T{time_str}")
                dt_end = dt_start + timedelta(hours=1)
                event_body["start"] = {"dateTime": dt_start.isoformat(), "timeZone": "Europe/Warsaw"}
                event_body["end"] = {"dateTime": dt_end.isoformat(), "timeZone": "Europe/Warsaw"}
            except Exception:
                # Fallback to all-day
                event_body["start"] = {"date": date_str}
                event_body["end"] = {"date": date_str}
        elif date_str:
            # All-day event
            event_body["start"] = {"date": date_str}
            event_body["end"] = {"date": date_str}
        else:
            raise CalendarError(
                f"Wydarzenie '{title}' nie posiada określonej daty kalendarzowej "
                f"({event_info.get('raw_date_expression')}). Podaj datę przed dodaniem do Kalendarza."
            )

        try:
            created = service.events().insert(calendarId="primary", body=event_body).execute()
            return {
                "id": created.get("id"),
                "htmlLink": created.get("htmlLink"),
                "summary": created.get("summary"),
                "status": "success"
            }
        except Exception as e:
            raise CalendarError(f"Błąd tworzenia wydarzenia w Google Calendar: {e}")

    async def create_event(
        self,
        token_data: Dict[str, Any],
        event_info: Dict[str, Any],
        subject: str = "Lekcja"
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(self._create_event_sync, token_data, event_info, subject)
