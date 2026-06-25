import os
import asyncio
from datetime import datetime, timezone

import httpx
from sqlalchemy.exc import IntegrityError

from ..database import SessionLocal
from ..models import Contact, Message
from ..enums import MsgStatus, Priority

TG_BASE = "https://api.telegram.org"


async def poll_updates(offset: int = 0) -> list[dict]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    async with httpx.AsyncClient(timeout=35.0) as client:
        resp = await client.get(
            f"{TG_BASE}/bot{token}/getUpdates",
            params={"timeout": 30, "offset": offset, "allowed_updates": ["message"]},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])


async def send_message(chat_id: int, text: str) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{TG_BASE}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        resp.raise_for_status()
        return resp.json()


async def send_voice(chat_id: int, audio_bytes: bytes, caption: str = "") -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{TG_BASE}/bot{token}/sendVoice",
            data={"chat_id": chat_id, "caption": caption},
            files={"voice": ("reply.webm", audio_bytes, "audio/webm")},
        )
        resp.raise_for_status()
        return resp.json()


async def ingest_update(update: dict) -> None:
    msg_data = update.get("message")
    if not msg_data:
        return

    chat = msg_data.get("chat", {})
    if chat.get("type") != "private":
        return

    text = msg_data.get("text", "")
    if not text:
        return

    tg_id: int = chat.get("id")
    sender = msg_data.get("from", {})
    first = sender.get("first_name", "")
    last = sender.get("last_name", "")
    name = (first + " " + last).strip() or f"tg_{tg_id}"
    username = sender.get("username")

    tg_update_id: int = update.get("update_id")
    tg_message_id: int = msg_data.get("message_id")
    date_ts: int = msg_data.get("date", 0)
    received_at = datetime.fromtimestamp(date_ts, tz=timezone.utc).replace(tzinfo=None) if date_ts else datetime.utcnow()

    db = SessionLocal()
    try:
        # Upsert contact by tg_chat_id
        contact = db.query(Contact).filter(Contact.tg_chat_id == tg_id).first()
        if contact is None:
            contact = Contact(
                name=name,
                tg_chat_id=tg_id,
                tg_username=username,
                rel_source="unknown",
            )
            db.add(contact)
            db.commit()
            db.refresh(contact)
        else:
            if name:
                contact.name = name
            db.commit()

        # Insert message — skip silently on duplicate tg_update_id
        message = Message(
            contact_id=contact.id,
            tg_update_id=tg_update_id,
            tg_message_id=tg_message_id,
            body=text,
            received_at=received_at,
            priority=Priority.NORMAL,
            status=MsgStatus.UNREAD,
            summary=None,
        )
        db.add(message)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # duplicate tg_update_id — skip silently

        # TODO: Gemini classify after Task 3
    finally:
        db.close()


async def run_poller() -> None:
    offset = 0
    while True:
        try:
            updates = await poll_updates(offset)
            for update in updates:
                await ingest_update(update)
                update_id = update.get("update_id", 0)
                if update_id >= offset:
                    offset = update_id + 1
        except Exception as e:
            print(f"[poller] error: {e}")
            await asyncio.sleep(5)
