import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch


def _seed_event(db_session, minutes_from_now: int):
    """Helper: insert a calendar event N minutes from now."""
    from app.models import CalendarEvent
    start = datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)
    event = CalendarEvent(
        id="test-event-1",
        title="Board Meeting",
        start=start.isoformat(),
        end=(start + timedelta(hours=1)).isoformat(),
        attendees=json.dumps([
            {"email": "razif@mbm.com", "name": "Dato Razif", "responseStatus": "accepted"},
            {"email": "nobody@example.com", "name": "Unknown", "responseStatus": "accepted"},
        ]),
    )
    db_session.add(event)
    db_session.commit()
    return event


def test_late_check_is_late_when_eta_exceeds_threshold(client, db_session):
    """eta=35, event in 20 min → is_late=True."""
    from app.models import CarState
    car = db_session.get(CarState, 1)
    car.eta_minutes = 35
    car.eta_source = "simulator"
    db_session.commit()
    _seed_event(db_session, minutes_from_now=20)
    with patch("app.routers.automations.send_message", new=AsyncMock(return_value={"ok": True})):
        with patch("app.routers.automations.draft_late_apology", new=AsyncMock(return_value="Sorry")):
            resp = client.post("/api/automations/run-late-check")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_late"] is True


def test_late_check_not_late_below_threshold(client, db_session):
    """eta=25, event in 20 min → mins_late=5 < 15 threshold → is_late=False, log status=skipped."""
    from app.models import CarState
    car = db_session.get(CarState, 1)
    car.eta_minutes = 25
    car.eta_source = "simulator"
    db_session.commit()
    _seed_event(db_session, minutes_from_now=20)
    resp = client.post("/api/automations/run-late-check")
    assert resp.status_code == 200
    assert resp.json()["is_late"] is False
    from app.models import AutomationLog
    log = db_session.query(AutomationLog).filter(AutomationLog.type == "late_responder").first()
    assert log is not None
    assert log.status == "skipped"


def test_late_check_skips_attendee_without_tg_chat_id(client, db_session):
    """Attendee without tg_chat_id is skipped, not errored."""
    from app.models import CarState
    car = db_session.get(CarState, 1)
    car.eta_minutes = 35
    car.eta_source = "simulator"
    db_session.commit()
    _seed_event(db_session, minutes_from_now=20)
    with patch("app.routers.automations.send_message", new=AsyncMock(return_value={"ok": True})):
        with patch("app.routers.automations.draft_late_apology", new=AsyncMock(return_value="Sorry")):
            resp = client.post("/api/automations/run-late-check")
    assert resp.status_code == 200
    sent_to = resp.json()["message_sent_to"]
    skipped = [t for t in sent_to if t["status"] == "skipped"]
    assert len(skipped) >= 1  # nobody@example.com has no contact


def test_late_check_no_event_returns_not_late(client, db_session):
    """No upcoming event → is_late=False, no crash."""
    resp = client.post("/api/automations/run-late-check")
    assert resp.status_code == 200
    assert resp.json()["is_late"] is False


def test_next_departure_computes_leave_by(client, db_session):
    """leave_by = event.start - resolved_eta - 5min."""
    from app.models import CarState
    car = db_session.get(CarState, 1)
    car.eta_minutes = 20
    car.eta_source = "simulator"
    db_session.commit()
    _seed_event(db_session, minutes_from_now=60)
    resp = client.get("/api/automations/next-departure")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event"] is not None
    assert data["leave_by"] is not None
    # leave_by should be ~35 minutes from now (60 - 20 - 5)
    leave_by = datetime.fromisoformat(data["leave_by"])
    expected = datetime.now(timezone.utc) + timedelta(minutes=35)
    diff = abs((leave_by.astimezone(timezone.utc) - expected).total_seconds())
    assert diff < 120  # within 2 minutes tolerance
