import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..enums import AutoStatus, AutoType, MsgStatus, Priority
from ..models import AutomationLog, Contact, Message, Settings
from ..schemas import (
    InjectRequest,
    MessageListOut,
    MessageOut,
    TextReplyRequest,
    VoiceReplyForm,
)
from ..services.gemini import classify_and_summarize
from ..services.status import Conflict, apply_status
from ..services.telegram import send_message, send_voice

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/messages", tags=["messages"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log_automation(db: Session, type: str, status: str, payload: dict, error: str | None = None) -> AutomationLog:
    row = AutomationLog(
        type=type,
        trigger_at=datetime.now(timezone.utc).replace(tzinfo=None),
        payload=json.dumps(payload),
        status=status,
        error_msg=error,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _get_message_or_404(db: Session, msg_id: int) -> Message:
    msg = db.query(Message).filter(Message.id == msg_id).first()
    if msg is None:
        raise HTTPException(status_code=404, detail=f"Message {msg_id} not found")
    return msg


def _get_quiet_ids(settings: Settings) -> list[int]:
    try:
        return json.loads(settings.quiet_contact_ids or "[]")
    except Exception:
        return []


# ---------------------------------------------------------------------------
# POST /inject
# ---------------------------------------------------------------------------

@router.post("/inject", response_model=MessageOut, status_code=201)
async def inject_message(data: InjectRequest, db: Session = Depends(get_db)):
    # Upsert contact by tg_chat_id
    contact = db.query(Contact).filter(Contact.tg_chat_id == data.tg_chat_id).first()
    if contact is None:
        contact = Contact(
            name=f"tg_{data.tg_chat_id}",
            tg_chat_id=data.tg_chat_id,
            rel_source="unknown",
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)

    # Create message
    msg = Message(
        contact_id=contact.id,
        body=data.body,
        received_at=datetime.now(timezone.utc).replace(tzinfo=None),
        tg_update_id=None,
        priority=Priority.NORMAL,
        status=MsgStatus.UNREAD,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Classify/summarize — Gemini outage leaves message as unread/normal
    try:
        result = await classify_and_summarize(data.body, contact.name, contact.relationship)
        msg.priority = result["priority"]
        msg.summary = result["summary"]
        msg.suggested_reply = result["suggested_reply"]
        apply_status(msg, MsgStatus.SUMMARIZED)
    except Exception:
        pass  # leave as unread/normal
    db.commit()
    db.refresh(msg)

    # Auto-silence: marketing + low priority
    if contact.relationship == "marketing" and msg.priority == Priority.LOW:
        try:
            apply_status(msg, MsgStatus.SILENCED)
        except Conflict:
            pass
        db.commit()
        db.refresh(msg)

    # Auto-silence: quiet_contact_ids
    settings = db.query(Settings).filter(Settings.id == 1).first()
    if settings and contact.id in _get_quiet_ids(settings):
        try:
            apply_status(msg, MsgStatus.SILENCED)
        except Conflict:
            pass
        db.commit()
        db.refresh(msg)

    return MessageOut.from_orm_with_contact(msg)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@router.get("/", response_model=MessageListOut)
def list_messages(
    status: str | None = None,
    priority: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    from fastapi.responses import JSONResponse

    query = db.query(Message)
    if status:
        query = query.filter(Message.status == status)
    if priority:
        query = query.filter(Message.priority == priority)

    total = query.count()
    messages = query.order_by(Message.received_at.desc()).limit(limit).all()
    items = [MessageOut.from_orm_with_contact(m) for m in messages]

    return MessageListOut(messages=items, total=total)


# ---------------------------------------------------------------------------
# GET /{id}
# ---------------------------------------------------------------------------

@router.get("/{id}", response_model=MessageOut)
def get_message(id: int, db: Session = Depends(get_db)):
    msg = _get_message_or_404(db, id)
    return MessageOut.from_orm_with_contact(msg)


# ---------------------------------------------------------------------------
# POST /{id}/summarize
# ---------------------------------------------------------------------------

@router.post("/{id}/summarize", response_model=MessageOut)
async def summarize_message(id: int, db: Session = Depends(get_db)):
    msg = _get_message_or_404(db, id)
    contact = msg.contact

    result = await classify_and_summarize(msg.body, contact.name, contact.relationship)
    msg.priority = result["priority"]
    msg.summary = result["summary"]
    msg.suggested_reply = result["suggested_reply"]

    try:
        apply_status(msg, MsgStatus.SUMMARIZED)
    except Conflict as e:
        raise HTTPException(status_code=409, detail={"detail": e.detail, "code": e.code})

    db.commit()
    db.refresh(msg)
    return MessageOut.from_orm_with_contact(msg)


# ---------------------------------------------------------------------------
# POST /{id}/reply — dual-mode: text (primary) / voice (stretch)
# ---------------------------------------------------------------------------

@router.post("/{id}/reply", response_model=MessageOut)
async def reply_message(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        reply_mode = form.get("reply_mode")
        if reply_mode != "voice":
            raise HTTPException(
                status_code=422,
                detail={"detail": "Expected reply_mode='voice' for multipart", "code": "VALIDATION_ERROR"},
            )
        data = VoiceReplyForm(audio_format=form.get("audio_format", "webm_opus"))
        transcript = form.get("transcript", "")
        audio_file = form.get("audio")
        return await handle_voice_reply(id, data, transcript, audio_file, db)
    else:
        body = await request.json()
        data = TextReplyRequest(**body)
        return await handle_text_reply(id, data, db)


async def handle_text_reply(msg_id: int, data: TextReplyRequest, db: Session) -> MessageOut:
    msg = _get_message_or_404(db, msg_id)
    contact = msg.contact

    if contact.tg_chat_id is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "Contact has no Telegram chat ID", "code": "NO_TELEGRAM_CHAT"},
        )

    try:
        apply_status(msg, MsgStatus.REPLIED)
    except Conflict as e:
        raise HTTPException(status_code=409, detail={"detail": e.detail, "code": e.code})

    try:
        await send_message(contact.tg_chat_id, data.transcript)
    except Exception as exc:
        logger.error("send_message failed for msg %s: %s", msg_id, exc)
        try:
            apply_status(msg, MsgStatus.SEND_FAILED)
        except Conflict:
            pass
        db.commit()
        log_automation(db, AutoType.TEXT_REPLY, AutoStatus.ERROR, {"msg_id": msg_id}, str(exc))
        db.refresh(msg)
        return MessageOut.from_orm_with_contact(msg)

    msg.reply_mode = "text"
    msg.sent_reply_text = data.transcript
    msg.replied_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    log_automation(db, AutoType.TEXT_REPLY, AutoStatus.OK, {"msg_id": msg_id})
    db.refresh(msg)
    return MessageOut.from_orm_with_contact(msg)


async def handle_voice_reply(
    msg_id: int,
    data: VoiceReplyForm,
    transcript: str,
    audio_file,
    db: Session,
) -> MessageOut:
    settings = db.query(Settings).filter(Settings.id == 1).first()
    if settings is None or settings.voice_reply_enabled == 0:
        raise HTTPException(
            status_code=409,
            detail={"detail": "Voice reply disabled", "code": "VOICE_REPLY_DISABLED"},
        )

    msg = _get_message_or_404(db, msg_id)
    contact = msg.contact

    if contact.tg_chat_id is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "Contact has no Telegram chat ID", "code": "NO_TELEGRAM_CHAT"},
        )

    # Validate audio file content type
    audio_content_type = getattr(audio_file, "content_type", "") or ""
    if not (audio_content_type.startswith("audio/webm") or audio_content_type.startswith("audio/ogg")):
        raise HTTPException(
            status_code=422,
            detail={"detail": "Invalid audio type", "code": "INVALID_AUDIO_TYPE"},
        )

    audio_bytes = await audio_file.read()
    if len(audio_bytes) < 100:
        raise HTTPException(
            status_code=422,
            detail={"detail": "Audio file too small", "code": "AUDIO_EMPTY"},
        )
    if len(audio_bytes) > 5_000_000:
        raise HTTPException(
            status_code=413,
            detail={"detail": "Audio file too large", "code": "AUDIO_TOO_LARGE"},
        )

    try:
        apply_status(msg, MsgStatus.REPLIED)
    except Conflict as e:
        raise HTTPException(status_code=409, detail={"detail": e.detail, "code": e.code})

    # Determine fmt and ext from content type
    if audio_content_type.startswith("audio/ogg"):
        fmt = "ogg_opus"
        ext = "ogg"
    else:
        fmt = "webm_opus"
        ext = "webm"

    path = f"audio_replies/{msg_id}.{ext}"
    audio_path = Path(path)
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(audio_bytes)

    try:
        await send_voice(contact.tg_chat_id, audio_bytes)
    except Exception as exc:
        logger.error("send_voice failed for msg %s: %s", msg_id, exc)
        audio_path.unlink(missing_ok=True)
        try:
            apply_status(msg, MsgStatus.SEND_FAILED)
        except Conflict:
            pass
        db.commit()
        log_automation(db, AutoType.VOICE_REPLY, AutoStatus.ERROR, {"msg_id": msg_id}, str(exc))
        db.refresh(msg)
        return MessageOut.from_orm_with_contact(msg)

    msg.reply_mode = "voice"
    msg.sent_reply_text = transcript
    msg.replied_at = datetime.now(timezone.utc).replace(tzinfo=None)
    msg.audio_path = path
    msg.audio_format = fmt
    db.commit()
    log_automation(db, AutoType.VOICE_REPLY, AutoStatus.OK, {"msg_id": msg_id})
    db.refresh(msg)
    return MessageOut.from_orm_with_contact(msg)


# ---------------------------------------------------------------------------
# POST /{id}/silence
# ---------------------------------------------------------------------------

@router.post("/{id}/silence", response_model=MessageOut)
def silence_message(id: int, db: Session = Depends(get_db)):
    msg = _get_message_or_404(db, id)

    try:
        apply_status(msg, MsgStatus.SILENCED)
    except Conflict as e:
        raise HTTPException(status_code=409, detail={"detail": e.detail, "code": e.code})

    db.commit()
    db.refresh(msg)
    return MessageOut.from_orm_with_contact(msg)
