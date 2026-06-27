from datetime import datetime, timezone, timedelta
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AutomationLog, CalendarEvent, CarState, Message, Settings
from ..schemas import AssistantCommand, AssistantResultOut
from ..enums import AutoType, AutoStatus, MsgStatus
from ..services.eta import get_resolved_eta
from ..services.gemini import process_assistant_command

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

_FALLBACK = AssistantResultOut(
    spoken_text="Sorry, I couldn't process that.",
    action=None,
    action_data=None,
)


def _get_or_create_car(db: Session) -> CarState:
    car = db.query(CarState).filter(CarState.id == 1).first()
    if car is None:
        car = CarState(id=1)
        db.add(car)
        db.commit()
        db.refresh(car)
    return car


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


@router.post("/command", response_model=AssistantResultOut)
async def assistant_command(data: AssistantCommand, db: Session = Depends(get_db)):
    try:
        car = _get_or_create_car(db)
        event = _get_next_event(db)
        resolved_eta = get_resolved_eta(car)

        context = {
            "location": car.location_name,
            "eta_minutes": resolved_eta,
            "climate_on": bool(car.climate_on),
            "next_event": {
                "title": event.title,
                "start": event.start,
                "location": event.location,
            } if event else None,
        }

        result = await process_assistant_command(data.transcript, context)
        action = result.get("action")
        action_data = result.get("action_data") or {}
        spoken_text = result.get("spoken_text", _FALLBACK.spoken_text)

        # Dispatch recognized actions
        if action == "summarize_messages":
            unread = (
                db.query(Message)
                .filter(Message.status == MsgStatus.UNREAD)
                .order_by(Message.received_at.desc())
                .limit(5)
                .all()
            )
            if unread:
                summaries = []
                for msg in unread:
                    preview = msg.summary or msg.body[:80]
                    summaries.append(preview)
                spoken_text = f"You have {len(unread)} unread message(s). " + " | ".join(summaries)
            else:
                spoken_text = "You have no unread messages."
            action_data = {"count": len(unread)}

        elif action == "late_check":
            settings = db.query(Settings).filter(Settings.id == 1).first()
            if settings is None:
                settings = Settings(id=1)
                db.add(settings)
                db.commit()

            if event is None or resolved_eta is None:
                spoken_text = "No upcoming event or ETA available to check lateness."
            else:
                now = datetime.now(timezone.utc)
                start = datetime.fromisoformat(event.start).astimezone(timezone.utc)
                arrival = now + timedelta(minutes=resolved_eta)
                mins_late = round((arrival - start).total_seconds() / 60)
                is_late = mins_late >= settings.late_threshold_min
                if is_late:
                    spoken_text = f"Yes, you are running about {mins_late} minutes late to {event.title}."
                else:
                    mins_early = -mins_late
                    spoken_text = f"You are on time for {event.title}, arriving about {mins_early} minutes early."
                action_data = {"is_late": is_late, "mins_late": mins_late, "event_title": event.title}

        elif action == "cabin_cool":
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            if not bool(car.climate_on):
                car.climate_on = 1
                db.commit()
                log = AutomationLog(
                    type=AutoType.PRECOOL,
                    trigger_at=now_naive,
                    payload=json.dumps({"action": "cabin_cool", "source": "assistant"}),
                    status=AutoStatus.OK,
                )
                db.add(log)
                db.commit()
                spoken_text = "Cabin cooling has been activated."
            else:
                spoken_text = "Cabin cooling is already on."
            action_data = {"climate_on": True}

        elif action == "navigate_to":
            destination = action_data.get("destination") if action_data else None
            if destination:
                spoken_text = f"Navigation to {destination} has been noted. Please use the dashboard to confirm the route."
            else:
                spoken_text = "Please specify a destination to navigate to."

        return AssistantResultOut(
            spoken_text=spoken_text,
            action=action,
            action_data=action_data if action_data else None,
        )

    except Exception:
        return _FALLBACK
