import datetime
from unittest.mock import AsyncMock, patch

from app.models import Contact, Message
from app.enums import MsgStatus


def test_text_reply_success(client, db_session):
    """Successful text reply sets status=replied, reply_mode=text, sent_reply_text set, audio_path null."""
    resp = client.post("/api/messages/inject", json={"tg_chat_id": 987654321, "name": "Dato Razif", "body": "Meeting?"})
    msg_id = resp.json()["id"]
    with patch("app.routers.messages.send_message", new=AsyncMock(return_value={"ok": True})):
        resp2 = client.post(f"/api/messages/{msg_id}/reply", json={
            "reply_mode": "text", "transcript": "I'll be there in 10 minutes"
        })
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["status"] == "replied"
    assert data["reply_mode"] == "text"
    assert data["sent_reply_text"] == "I'll be there in 10 minutes"
    assert data["audio_format"] is None


def test_text_reply_empty_transcript_422(client, db_session):
    """Empty/whitespace-only transcript is rejected with 422."""
    resp = client.post("/api/messages/inject", json={"tg_chat_id": 987654321, "name": "Dato Razif", "body": "Hi"})
    msg_id = resp.json()["id"]
    resp2 = client.post(f"/api/messages/{msg_id}/reply", json={
        "reply_mode": "text", "transcript": "   "
    })
    assert resp2.status_code == 422


def test_text_reply_telegram_failure_sets_send_failed(client, db_session):
    """Telegram failure → status=send_failed, HTTP 200, no 500."""
    resp = client.post("/api/messages/inject", json={"tg_chat_id": 987654321, "name": "Dato Razif", "body": "Hi"})
    msg_id = resp.json()["id"]
    with patch("app.routers.messages.send_message", new=AsyncMock(side_effect=Exception("Telegram down"))):
        resp2 = client.post(f"/api/messages/{msg_id}/reply", json={
            "reply_mode": "text", "transcript": "Sorry, running late"
        })
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "send_failed"


def test_reply_no_telegram_chat_id_returns_409(client, db_session):
    """Contact with no tg_chat_id returns 409 NO_TELEGRAM_CHAT."""
    acme = db_session.query(Contact).filter(Contact.email == "marketing@acme.com").first()
    msg = Message(contact_id=acme.id, body="Test", status=MsgStatus.UNREAD, priority="normal")
    db_session.add(msg)
    db_session.commit()
    resp = client.post(f"/api/messages/{msg.id}/reply", json={"reply_mode": "text", "transcript": "Hello"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "NO_TELEGRAM_CHAT"


def test_voice_reply_disabled_returns_409(client, db_session):
    """voice_reply_enabled=False → 409 VOICE_REPLY_DISABLED for multipart voice."""
    resp = client.post("/api/messages/inject", json={"tg_chat_id": 987654321, "name": "Dato Razif", "body": "Hi"})
    msg_id = resp.json()["id"]
    # voice_reply_enabled defaults to 0 (False)
    resp2 = client.post(
        f"/api/messages/{msg_id}/reply",
        data={"reply_mode": "voice", "transcript": "hello"},
        files={"audio": ("reply.webm", b"\x00" * 200, "audio/webm")},
    )
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["code"] == "VOICE_REPLY_DISABLED"


def test_replying_already_replied_message_returns_409(client, db_session):
    """Replying to an already-replied message returns 409 INVALID_TRANSITION."""
    resp = client.post("/api/messages/inject", json={"tg_chat_id": 987654321, "name": "Dato Razif", "body": "Hi"})
    msg_id = resp.json()["id"]
    msg = db_session.get(Message, msg_id)
    msg.status = MsgStatus.REPLIED
    msg.reply_mode = "text"
    msg.sent_reply_text = "Already replied"
    msg.replied_at = datetime.datetime.utcnow()
    db_session.commit()
    with patch("app.routers.messages.send_message", new=AsyncMock(return_value={"ok": True})):
        resp2 = client.post(f"/api/messages/{msg_id}/reply", json={"reply_mode": "text", "transcript": "Again"})
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["code"] == "INVALID_TRANSITION"
