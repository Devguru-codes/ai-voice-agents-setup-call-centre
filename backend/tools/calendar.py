"""
Google Calendar tool — books meetings on behalf of the AI agent.

Uses google-api-python-client with OAuth2 credentials.
If credentials are not available, falls back to a simulated booking
so the app still works during development.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _get_service():
    """Build the Google Calendar service if credentials exist."""
    import config
    import os
    if not config.GOOGLE_CLIENT_SECRETS_FILE or not os.path.exists(config.GOOGLE_CLIENT_SECRETS_FILE):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle

        SCOPES = ["https://www.googleapis.com/auth/calendar"]
        token_path = "token_calendar.pkl"
        creds = None

        if os.path.exists(token_path):
            with open(token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    config.GOOGLE_CLIENT_SECRETS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)

        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        logger.warning(f"⚠️ Google Calendar unavailable: {e}")
        return None


async def book_meeting(
    summary: str,
    date_time_iso: str,
    duration_minutes: int = 30,
    attendee_email: Optional[str] = None,
) -> dict:
    """
    Create a Google Calendar event.

    Returns:
        dict with keys: success, event_id, link, message
    """
    try:
        start_dt = datetime.fromisoformat(date_time_iso)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        service = _get_service()

        if service is None:
            # Development fallback — simulate success
            logger.info(f"📅 [SIMULATED] Meeting booked: {summary} at {date_time_iso}")
            return {
                "success": True,
                "event_id": "simulated-event-123",
                "link": "https://calendar.google.com",
                "message": (
                    f"✅ Meeting '{summary}' booked for "
                    f"{start_dt.strftime('%B %d at %I:%M %p')} "
                    f"({duration_minutes} min). [Simulated — connect Google Calendar in .env]"
                ),
            }

        event_body: dict = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
        }

        if attendee_email:
            event_body["attendees"] = [{"email": attendee_email}]
            event_body["sendUpdates"] = "all"

        event = service.events().insert(
            calendarId="primary", body=event_body
        ).execute()

        link = event.get("htmlLink", "")
        logger.info(f"📅 Calendar event created: {event['id']}")
        return {
            "success": True,
            "event_id": event["id"],
            "link": link,
            "message": (
                f"✅ Meeting '{summary}' booked for "
                f"{start_dt.strftime('%B %d at %I:%M %p')} UTC. "
                f"{'Invite sent to ' + attendee_email + '.' if attendee_email else ''}"
            ),
        }

    except ValueError as e:
        msg = f"Invalid date/time format: {e}"
        logger.error(f"❌ Calendar tool error: {msg}")
        return {"success": False, "message": msg}
    except Exception as e:
        msg = f"Failed to book meeting: {e}"
        logger.error(f"❌ Calendar tool error: {msg}")
        return {"success": False, "message": msg}
