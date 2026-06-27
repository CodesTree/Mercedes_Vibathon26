import json
from html import escape

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import Attendee, CalendarEventOut
from ..services.google_cal import exchange_code_for_tokens, get_oauth_redirect_url, get_upcoming_events, has_google_credentials

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _callback_page(title: str, message: str, status_code: int) -> HTMLResponse:
    return HTMLResponse(
        content=f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <style>
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #09090b;
        color: #fafafa;
        font-family: Arial, sans-serif;
      }}
      main {{
        width: min(520px, calc(100vw - 32px));
        border: 1px solid #27272a;
        border-radius: 8px;
        background: #18181b;
        padding: 24px;
      }}
      p {{ color: #d4d4d8; line-height: 1.5; }}
      a {{ color: #22d3ee; }}
    </style>
  </head>
  <body>
    <main>
      <h1>{escape(title)}</h1>
      <p>{escape(message)}</p>
      <p><a href="http://localhost:5173">Return to the app</a></p>
    </main>
  </body>
</html>
""",
        status_code=status_code,
    )


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
    if not has_google_credentials():
        return _callback_page(
            "Google Calendar credentials missing",
            "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env, then restart the backend.",
            500,
        )

    oauth_url = get_oauth_redirect_url()
    return RedirectResponse(url=oauth_url, status_code=302)


@router.get("/callback", response_class=HTMLResponse)
async def calendar_callback(code: str | None = None, error: str | None = None):
    if error:
        return _callback_page(
            "Calendar connection cancelled",
            f"Google returned an error: {error}",
            400,
        )

    if not code:
        return _callback_page(
            "Calendar connection not started",
            "Open /api/calendar/auth first. Google will send you back here with a temporary code.",
            400,
        )

    try:
        await exchange_code_for_tokens(code)
    except Exception as e:
        return _callback_page("Calendar connection failed", str(e), 400)

    return _callback_page(
        "Calendar connected",
        "Google Calendar is connected. You can return to the app.",
        200,
    )


@router.get("/events", response_model=list[CalendarEventOut])
async def list_calendar_events(db: Session = Depends(get_db)):
    events, source = await get_upcoming_events(db, limit=10)
    return [_build_calendar_event_out(ev, source) for ev in events]
