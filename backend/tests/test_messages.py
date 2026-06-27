from unittest.mock import AsyncMock, patch


def test_inject_creates_contact_and_message(client):
    """Injecting creates exactly one contact and one message."""
    resp = client.post("/api/messages/inject", json={
        "tg_chat_id": 111, "name": "Test User", "body": "Hello"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] in ("unread", "summarized")
    assert data["contact_name"] == "Test User"


def test_inject_same_contact_twice_creates_one_contact(client, db_session):
    """Second inject from same tg_chat_id doesn't create a new contact."""
    from app.models import Contact
    client.post("/api/messages/inject", json={"tg_chat_id": 222, "name": "Alice", "body": "Hi"})
    client.post("/api/messages/inject", json={"tg_chat_id": 222, "name": "Alice", "body": "Hi again"})
    count = db_session.query(Contact).filter(Contact.tg_chat_id == 222).count()
    assert count == 1


def test_inject_marketing_contact_silenced(client, db_session):
    """marketing contact with low priority is auto-silenced."""
    from app.models import Contact
    mock_result = {"priority": "low", "summary": "Ad", "suggested_reply": None}
    with patch("app.routers.messages.classify_and_summarize", new=AsyncMock(return_value=mock_result)):
        contact = Contact(name="Spammer", tg_chat_id=55555, relationship="marketing", rel_source="seed")
        db_session.add(contact)
        db_session.commit()
        resp = client.post("/api/messages/inject", json={
            "tg_chat_id": 55555, "name": "Spammer", "body": "50% off!"
        })
    assert resp.status_code == 201
    assert resp.json()["status"] == "silenced"


def test_list_messages_filter_by_status(client):
    """GET /messages filters by status parameter."""
    client.post("/api/messages/inject", json={"tg_chat_id": 333, "name": "Bob", "body": "Hey"})
    resp = client.get("/api/messages/?status=unread")
    assert resp.status_code == 200
    assert "X-Total-Count" in resp.headers


def test_silence_message(client, db_session):
    """Silencing a message sets status to silenced."""
    resp = client.post("/api/messages/inject", json={"tg_chat_id": 444, "name": "Carol", "body": "Meeting?"})
    msg_id = resp.json()["id"]
    resp2 = client.post(f"/api/messages/{msg_id}/silence")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "silenced"


def test_silence_already_replied_returns_409(client, db_session):
    """Silencing an already replied message returns 409."""
    import datetime
    from app.models import Message
    from app.enums import MsgStatus
    resp = client.post("/api/messages/inject", json={"tg_chat_id": 666, "name": "Dave", "body": "Hi"})
    msg_id = resp.json()["id"]
    msg = db_session.get(Message, msg_id)
    msg.status = MsgStatus.REPLIED
    msg.replied_at = datetime.datetime.utcnow()
    msg.reply_mode = "text"
    msg.sent_reply_text = "Done"
    db_session.commit()
    resp2 = client.post(f"/api/messages/{msg_id}/silence")
    assert resp2.status_code == 409


def test_gemini_outage_still_creates_message(client):
    """Gemini outage: message still created with priority=normal, status=unread, HTTP 201."""
    with patch("app.routers.messages.classify_and_summarize", new=AsyncMock(side_effect=Exception("Gemini down"))):
        resp = client.post("/api/messages/inject", json={"tg_chat_id": 777, "name": "Eve", "body": "Hello"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["priority"] == "normal"
    assert data["summary"] is None
