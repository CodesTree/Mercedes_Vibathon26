import os
import json
from pathlib import Path
from datetime import datetime, timezone

import httpx

from ..models import CalendarEvent

TOKEN_FILE = Path(__file__).parent.parent.parent / "calendar_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


def _client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID", "")


def _client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET", "")


def _redirect_uri() -> str:
    return os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/calendar/oauth/callback")


def get_oauth_redirect_url() -> str:
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "scope": " ".join(SCOPES),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


async def exchange_code_for_tokens(code: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": _redirect_uri(),
        })
        resp.raise_for_status()
        token = resp.json()
    TOKEN_FILE.write_text(json.dumps(token))
    return token


def load_token() -> dict | None:
    if not TOKEN_FILE.exists():
        return None
    try:
        return json.loads(TOKEN_FILE.read_text())
    except Exception:
        return None


async def refresh_access_token(token: dict) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": token.get("refresh_token", ""),
            "client_id": _client_id(),
            "client_secret": _client_secret(),
        })
        resp.raise_for_status()
        refreshed = resp.json()
    token["access_token"] = refreshed["access_token"]
    if "expires_in" in refreshed:
        token["expires_in"] = refreshed["expires_in"]
    TOKEN_FILE.write_text(json.dumps(token))
    return token


async def get_access_token() -> str | None:
    token = load_token()
    if token is None:
        return None
    if "refresh_token" in token:
        try:
            token = await refresh_access_token(token)
        except Exception:
            pass
    return token.get("access_token")


async def _fetch_events(access_token: str, limit: int) -> list[dict]:
    now_iso = datetime.now(timezone.utc).isoformat()
    url = f"{CALENDAR_API_BASE}/calendars/primary/events"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "maxResults": limit,
        "orderBy": "startTime",
        "singleEvents": "true",
        "timeMin": now_iso,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code == 401:
            return None  # Signal caller to refresh and retry
        resp.raise_for_status()
        data = resp.json()
    events = []
    for item in data.get("items", []):
        start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date", "")
        end = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date", "")
        raw_attendees = item.get("attendees", [])
        attendees_list = [
            {
                "email": a.get("email", ""),
                "name": a.get("displayName", ""),
                "responseStatus": a.get("responseStatus", ""),
            }
            for a in raw_attendees
        ]
        events.append({
            "id": item.get("id", ""),
            "title": item.get("summary", "(no title)"),
            "start": start,
            "end": end,
            "location": item.get("location"),
            "organizer_email": item.get("organizer", {}).get("email"),
            "attendees": json.dumps(attendees_list),
        })
    return events


async def fetch_from_google(limit: int = 10) -> list[dict]:
    access_token = await get_access_token()
    if access_token is None:
        raise Exception("No access token available")

    result = await _fetch_events(access_token, limit)
    if result is None:
        # 401: try to refresh and retry once
        token = load_token()
        if token and "refresh_token" in token:
            token = await refresh_access_token(token)
            result = await _fetch_events(token["access_token"], limit)
        if result is None:
            raise Exception("Calendar API returned 401 and refresh failed")
    return result


async def get_upcoming_events(db, limit: int = 10) -> tuple[list, str]:
    try:
        events_data = await fetch_from_google(limit)
        for ev in events_data:
            existing = db.query(CalendarEvent).filter(CalendarEvent.id == ev["id"]).first()
            if existing:
                existing.title = ev["title"]
                existing.start = ev["start"]
                existing.end = ev["end"]
                existing.location = ev["location"]
                existing.organizer_email = ev["organizer_email"]
                existing.attendees = ev["attendees"]
                existing.cached_at = datetime.utcnow()
            else:
                db.add(CalendarEvent(
                    id=ev["id"],
                    title=ev["title"],
                    start=ev["start"],
                    end=ev["end"],
                    location=ev["location"],
                    organizer_email=ev["organizer_email"],
                    attendees=ev["attendees"],
                ))
        db.commit()
        events_objects = db.query(CalendarEvent).order_by(CalendarEvent.start).limit(limit).all()
        return events_objects, "live"
    except Exception:
        cached = db.query(CalendarEvent).order_by(CalendarEvent.start).limit(limit).all()
        return cached, "cache"
