import json

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import Attendee, CalendarEventOut
from ..services.google_cal import exchange_code_for_tokens, get_oauth_redirect_url, get_upcoming_events

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _build_calendar_event_out(event, source: str) -> CalendarEventOut:
    attendees_raw = json.loads(event.attendees or "[]")
    return CalendarEventOut(
        id=event.id,
        title=event.title,
        start=event.start,
        end=event.end,
        location=event.location,
        organizer_email=event.organizer_email,
        attendees=[Attendee(**a) for a in attendees_raw],
        cached_at=event.cached_at,
        source=source,
    )


@router.get("/auth")
def calendar_auth():
    oauth_url = get_oauth_redirect_url()
    return RedirectResponse(url=oauth_url, status_code=302)


@router.get("/callback")
async def calendar_callback(code: str):
    try:
        await exchange_code_for_tokens(code)
    except Exception as e:
        return {"error": "OAuth failed", "detail": str(e)}
    return RedirectResponse(url="/", status_code=302)


@router.get("/events", response_model=list[CalendarEventOut])
async def list_calendar_events(db: Session = Depends(get_db)):
    events, source = await get_upcoming_events(db, limit=10)
    return [_build_calendar_event_out(ev, source) for ev in events]
