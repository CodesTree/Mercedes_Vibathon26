from datetime import datetime, timezone, timedelta
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AutomationLog, CalendarEvent, CarState, Contact, Settings
from ..schemas import (
    Attendee,
    AutomationLogOut,
    CalendarEventOut,
    LateCheckResultOut,
    NextDepartureOut,
    NotifiedTarget,
)
from ..enums import AutoType, AutoStatus
from ..services.eta import get_resolved_eta
from ..services.gemini import draft_late_apology
from ..services.telegram import send_message

router = APIRouter(prefix="/api/automations", tags=["automations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_car(db: Session) -> CarState:
    car = db.query(CarState).filter(CarState.id == 1).first()
    if car is None:
        car = CarState(id=1)
        db.add(car)
        db.commit()
        db.refresh(car)
    return car


def _get_or_create_settings(db: Session) -> Settings:
    settings = db.query(Settings).filter(Settings.id == 1).first()
    if settings is None:
        settings = Settings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _get_next_event(db: Session) -> CalendarEvent | None:
    """Returns the next upcoming CalendarEvent or None."""
    all_events = db.query(CalendarEvent).all()
    now = datetime.now(timezone.utc)
    upcoming = [
        e for e in all_events
        if datetime.fromisoformat(e.start).astimezone(timezone.utc) > now
    ]
    if not upcoming:
        return None
    return min(upcoming, key=lambda e: datetime.fromisoformat(e.start))


def _build_event_out(event: CalendarEvent | None, source: str = "cache") -> CalendarEventOut | None:
    if event is None:
        return None
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


def _build_log_out(log: AutomationLog) -> AutomationLogOut:
    return AutomationLogOut(
        id=log.id,
        type=log.type,
        trigger_at=log.trigger_at,
        payload=json.loads(log.payload or "{}"),
        status=log.status,
        error_msg=log.error_msg,
    )


# ---------------------------------------------------------------------------
# GET /next-departure
# ---------------------------------------------------------------------------

@router.get("/next-departure", response_model=NextDepartureOut)
def get_next_departure(db: Session = Depends(get_db)):
    car = _get_or_create_car(db)
    settings = _get_or_create_settings(db)
    resolved_eta = get_resolved_eta(car)
    event = _get_next_event(db)

    if event is None or resolved_eta is None:
        return NextDepartureOut(
            event=_build_event_out(event),
            resolved_eta=resolved_eta,
            eta_source=car.eta_source,
            leave_by=None,
            minutes_until_leave=None,
            is_late=False,
            precool_due=None,
            precool_fired=False,
        )

    event_start = datetime.fromisoformat(event.start).astimezone(timezone.utc)
    now = datetime.now(timezone.utc)

    leave_by = event_start - timedelta(minutes=resolved_eta) - timedelta(minutes=5)
    precool_due = leave_by - timedelta(minutes=settings.precool_lead_min)
    minutes_until_leave = round((leave_by - now).total_seconds() / 60)

    arrival = now + timedelta(minutes=resolved_eta)
    is_late = (arrival - event_start).total_seconds() / 60 >= settings.late_threshold_min

    # Check if precool has been fired for current event today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    precool_log = db.query(AutomationLog).filter(
        AutomationLog.type == AutoType.PRECOOL,
        AutomationLog.trigger_at >= today_start.replace(tzinfo=None),
        AutomationLog.trigger_at < today_end.replace(tzinfo=None),
    ).first()
    precool_fired = precool_log is not None

    return NextDepartureOut(
        event=_build_event_out(event),
        resolved_eta=resolved_eta,
        eta_source=car.eta_source,
        leave_by=leave_by,
        minutes_until_leave=minutes_until_leave,
        is_late=is_late,
        precool_due=precool_due,
        precool_fired=precool_fired,
    )


# ---------------------------------------------------------------------------
# POST /run-late-check
# ---------------------------------------------------------------------------

@router.post("/run-late-check", response_model=LateCheckResultOut)
async def run_late_check(db: Session = Depends(get_db)):
    car = _get_or_create_car(db)
    settings = _get_or_create_settings(db)
    event = _get_next_event(db)
    resolved_eta = get_resolved_eta(car)

    now = datetime.now(timezone.utc)

    if event is None or resolved_eta is None:
        log = AutomationLog(
            type=AutoType.LATE,
            trigger_at=now.replace(tzinfo=None),
            payload=json.dumps({"reason": "no_event_or_eta", "event": None, "eta": resolved_eta}),
            status=AutoStatus.SKIPPED,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return LateCheckResultOut(
            is_late=False,
            minutes_late=None,
            event=None,
            message_sent_to=[],
            log_id=log.id,
        )

    start = datetime.fromisoformat(event.start).astimezone(timezone.utc)
    arrival = now + timedelta(minutes=resolved_eta)
    mins_late = round((arrival - start).total_seconds() / 60)
    is_late = mins_late >= settings.late_threshold_min

    if not is_late:
        log = AutomationLog(
            type=AutoType.LATE,
            trigger_at=now.replace(tzinfo=None),
            payload=json.dumps({
                "event_id": event.id,
                "event_title": event.title,
                "eta_min": resolved_eta,
                "mins_late": mins_late,
                "is_late": False,
            }),
            status=AutoStatus.SKIPPED,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return LateCheckResultOut(
            is_late=False,
            minutes_late=mins_late,
            event=_build_event_out(event),
            message_sent_to=[],
            log_id=log.id,
        )

    # IS late — notify attendees
    attendees_raw = json.loads(event.attendees or "[]")
    accepted_attendees = [
        a for a in attendees_raw
        if a.get("responseStatus") in ("accepted", "needsAction")
    ]

    notified: list[NotifiedTarget] = []
    for attendee_data in accepted_attendees:
        email = attendee_data.get("email", "")
        name = attendee_data.get("name") or email

        contact = db.query(Contact).filter(Contact.email == email).first()

        if contact is None or contact.tg_chat_id is None:
            notified.append(NotifiedTarget(
                name=name,
                tg_chat_id=None,
                status="skipped",
            ))
            continue

        try:
            apology_text = await draft_late_apology(contact.name, event.title, mins_late)
        except Exception:
            apology_text = f"Hi {contact.name}, I'm running about {mins_late} minutes late to {event.title}. See you soon."

        try:
            await send_message(contact.tg_chat_id, apology_text)
            notified.append(NotifiedTarget(
                name=contact.name,
                tg_chat_id=contact.tg_chat_id,
                status="sent",
            ))
        except Exception:
            notified.append(NotifiedTarget(
                name=contact.name,
                tg_chat_id=contact.tg_chat_id,
                status="failed",
            ))

    log = AutomationLog(
        type=AutoType.LATE,
        trigger_at=now.replace(tzinfo=None),
        payload=json.dumps({
            "event_id": event.id,
            "event_title": event.title,
            "eta_min": resolved_eta,
            "mins_late": mins_late,
            "is_late": True,
            "notified": [n.model_dump() for n in notified],
        }),
        status=AutoStatus.OK,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return LateCheckResultOut(
        is_late=True,
        minutes_late=mins_late,
        event=_build_event_out(event),
        message_sent_to=notified,
        log_id=log.id,
    )


# ---------------------------------------------------------------------------
# GET /log
# ---------------------------------------------------------------------------

@router.get("/log", response_model=list[AutomationLogOut])
def get_log(limit: int = 20, db: Session = Depends(get_db)):
    logs = (
        db.query(AutomationLog)
        .order_by(AutomationLog.trigger_at.desc())
        .limit(limit)
        .all()
    )
    return [_build_log_out(log) for log in logs]
