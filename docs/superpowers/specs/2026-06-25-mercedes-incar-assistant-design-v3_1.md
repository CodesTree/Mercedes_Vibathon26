# Spec Sheet — Mercedes In-Car AI Co-Pilot (Vibathon 2026)
**Revision: v3.1 — Backend-Hardened Edition (foolproof data model + typed API models + acceptance criteria)**
_Last updated: June 2026_

> **What's new in v3.1:** This revision keeps the v3 architecture unchanged and adds backend rigor:
> §3.0 data-integrity invariants (incl. the SQLite footguns that silently corrupt PoC data),
> a formal message state machine (§3.2.1), a consolidated constraint catalog (§3.8),
> full Pydantic request/response models (§6.0), a standardized error catalog (§6.0.2),
> and **explicit conditions of success / acceptance criteria for every feature** (§4.x "Done when").

---

## Context

The repo is a clean CI/CD boilerplate (FastAPI + SQLite + React/Tailwind + Playwright) with a
sample `items` CRUD. This spec defines the features the team builds on top: an **in-car AI
assistant** ("co-pilot") that triages Telegram messages, handles being late, and uses the
driver's Google Calendar to pre-cool the cabin and plan departures — with a voice + screen
interface.

**Decisions locked for v3:**

| Decision | Choice |
|---|---|
| Messaging platform | **Telegram Bot API** (replaces OpenWA/WhatsApp entirely) |
| Inbound messages | Telegram `getUpdates` long-poll **or** webhook — bot receives texts sent to the demo bot |
| Outbound replies | **Voice note** — driver records via browser mic (`getUserMedia` + `MediaRecorder`) → FastAPI → Telegram `sendVoice` |
| LLM | **Google Gemini** (`gemini-2.5-flash` classify/summarize, `gemini-2.5-pro` draft) — same GCP project as Calendar |
| Calendar | **Real Google Calendar API** with OAuth 2.0 + SQLite read-through cache |
| Interface | React MBUX-style dashboard + browser **Web Speech API** (STT + TTS) |
| Maps / Navigation | **TomTom Maps SDK** — map render + route polyline + ETA only; used to feed F2 late-check. No live traffic overlay, no animated marker, no turn-by-turn voice |
| F4 Navigation feature | **Dropped.** Nav (geocode + route + ETA) exists purely as a utility to compute travel time for F2 |
| Car telemetry | **Car Simulator** panel — simulated position, ETA override, cabin temp, climate |
| Auth | Single demo driver profile — no login |
| GPS | Simulated — no real device GPS |

**Must-demo features:** F1 (Telegram messages + mic reply), F2 (Late Responder → sends Telegram voice note to meeting attendees), F3 (Calendar → cabin pre-cool + departure planning).

---

## 0. Telegram Bot Quick-Start Guide

> **Marcus owns this. Complete Day 1 before any other work — the bot must be receiving messages before F1 can be tested.**

### Step 1 — Create the Bot

1. Open Telegram and message **@BotFather**.
2. Send `/newbot`. Follow the prompts — name it `MercedesCoPilot`, username e.g. `mbx_copilot_bot`.
3. BotFather replies with a **token**: `7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`.
4. Add to `.env`: `TELEGRAM_BOT_TOKEN=<token>`.
5. Send `/setprivacy` → select your bot → choose **Disable** (so it can read all group messages if needed, though we use DMs only).

---

### Step 2 — Get the Demo Chat ID

The bot only replies to the demo driver's chat (single-user PoC). After creating the bot:

1. From the demo phone's Telegram, send `/start` to the bot.
2. Fetch updates to find the chat ID:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates"
# Look for: "chat": {"id": 123456789, ...}
```

3. Add to `.env`: `TELEGRAM_DEMO_CHAT_ID=123456789`.

For F2 (sending to meeting attendees), each attendee must have started a conversation with the bot first — their chat IDs are stored in `contacts.tg_chat_id`.

---

### Step 3 — Choose Inbound Strategy: Long-Poll (recommended for PoC)

No public URL needed. FastAPI runs a background task that calls `getUpdates` with `timeout=30`:

```python
# backend/app/services/telegram.py
import httpx, os

TG_BASE = "https://api.telegram.org"
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

async def poll_updates(offset: int = 0) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TG_BASE}/bot{TG_TOKEN}/getUpdates",
            params={"timeout": 30, "offset": offset, "allowed_updates": ["message"]},
            timeout=35.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])
```

The poller runs as a FastAPI lifespan background task (`asyncio.create_task`). On each received
message it calls `POST /api/messages/internal-ingest` to run the same classify → summarize →
priority pipeline as a webhook would.

**Alternative: Telegram webhook (if you have a public URL or use ngrok).**

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<your-ngrok>.ngrok.io/api/messages/webhook"}'
# Confirm: {"ok":true,"result":true,"description":"Webhook was set"}
```

Use long-poll for local dev; switch to webhook for demo day if ngrok is available.

---

### Step 4 — Incoming Message Payload (`getUpdates` / webhook)

Telegram delivers the same `Update` object whether long-polling or webhook:

```json
{
  "update_id": 100500001,
  "message": {
    "message_id": 42,
    "from": {
      "id": 987654321,
      "is_bot": false,
      "first_name": "Ahmad",
      "last_name": "Razif",
      "username": "ahmadrazif"
    },
    "chat": {
      "id": 987654321,
      "type": "private"
    },
    "date": 1750848300,
    "text": "Running 10 min late, is that okay?"
  }
}
```

Key fields used by the backend:

| Field | Used for |
|---|---|
| `update_id` | Deduplication — used as the `tg_update_id` on the `messages` table; also the `offset` for the next `getUpdates` call |
| `message.from.id` | Sender's Telegram user ID — used to upsert `contacts.tg_chat_id` |
| `message.from.first_name` + `last_name` | Display name for `contacts.name` |
| `message.chat.id` | The chat to reply to (for private chats equals `from.id`) |
| `message.date` | Unix timestamp → stored as `messages.received_at` |
| `message.text` | Raw message body → Gemini classify + summarize |
| `message.chat.type` | Drop anything that is not `"private"` — group chats are ignored |

---

### Step 5 — Send a Test Text Message (verify bot can send)

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": '"$TELEGRAM_DEMO_CHAT_ID"',
    "text": "Hello from the co-pilot!"
  }'
# Expected: {"ok":true,"result":{"message_id":43,...}}
```

---

### Step 6 — Send a Voice Note Reply (the real reply format)

The driver records a mic clip in the browser. FastAPI receives the WebM/Opus blob and sends it
via Telegram `sendVoice`. Telegram renders it as a playable voice note.

```bash
# Convert a local .webm file as a test
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendVoice" \
  -F "chat_id=$TELEGRAM_DEMO_CHAT_ID" \
  -F "voice=@/path/to/reply.webm" \
  -F "caption=Voice reply from the driver"
# Expected: {"ok":true,"result":{"voice":{"file_id":"...","duration":5},...}}
```

FastAPI uses `multipart/form-data` to forward the blob:

```python
# backend/app/services/telegram.py
async def send_voice(chat_id: int, audio_bytes: bytes, caption: str = "") -> dict:
    """
    chat_id:     Telegram chat/user ID (integer)
    audio_bytes: raw WebM/Opus bytes from browser MediaRecorder
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TG_BASE}/bot{TG_TOKEN}/sendVoice",
            data={"chat_id": chat_id, "caption": caption},
            files={"voice": ("reply.webm", audio_bytes, "audio/webm")},
            timeout=20.0,
        )
        resp.raise_for_status()
        return resp.json()  # {"ok":true,"result":{"message_id":44,...}}
```

> **Browser MediaRecorder note:** `getUserMedia({audio:true})` + `MediaRecorder` in Chrome produces
> `audio/webm; codecs=opus` natively. Telegram's `sendVoice` accepts WebM/Opus and renders it as a
> voice message bubble. No transcoding needed. Firefox produces `audio/ogg; codecs=opus` — also
> accepted. Set `MediaRecorder` `mimeType` preference to `audio/webm;codecs=opus` and fall back to
> `audio/ogg;codecs=opus`.

---

### Step 7 — Verify End-to-End

1. Send a Telegram message to the demo bot from any phone.
2. The long-poller picks it up within ~2 s and calls the internal ingest path.
3. Check: `curl http://localhost:8000/api/messages` → message appears with `status="unread"` or `"summarized"`.
4. Dashboard shows the message card.
5. Driver taps "Reply" → holds mic → sends → voice note lands in sender's Telegram.

Full `.env` for Telegram integration:

```env
TELEGRAM_BOT_TOKEN=7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_DEMO_CHAT_ID=123456789
```

---

## 1. System Overview

```text
Telegram (any phone messages the demo bot)
   │  HTTPS long-poll (getUpdates) or webhook
FastAPI backend  (http://localhost:8000)
   ├─ messages/      Long-poll ingest, inject fallback, Gemini classify+summarize,
   │                 mic-recorded voice reply via Telegram sendVoice, silence
   ├─ ai/            Gemini: classify, summarize, draft reply, NL command routing (F2 apology draft)
   ├─ calendar/      Google Calendar OAuth + live fetch + SQLite read-through cache
   ├─ navigation/    TomTom proxy: geocode + route ETA only (feeds F2 late-check threshold)
   ├─ car/           Simulated car state: position, ETA override, cabin temp, climate
   └─ automations/   F2 late-responder, F3 departure planning + cabin pre-cool
   │
SQLite  contacts · messages · audio_replies · calendar_events · car_state · automation_log · settings

External APIs: Telegram Bot API · Google Calendar API · Google Gemini · TomTom Routing API
```

**Key architectural decisions:**

- **No sidecar process.** Telegram long-polling runs inside FastAPI's lifespan as a background
  `asyncio.Task`. No Docker-in-Docker, no separate Node process, no session management.
- **Audio reply = real mic.** Browser `getUserMedia` → `MediaRecorder` → WebM/Opus blob →
  `POST /api/messages/{id}/reply` (multipart) → FastAPI → Telegram `sendVoice`. No TTS capture.
- **Navigation is a utility, not a feature.** `POST /api/nav/route` computes ETA and writes it
  to `car_state.route_eta_minutes`. The map renders the polyline on the dashboard. That's it.
  No animated marker, no turn-by-turn, no traffic overlay.
- **F2 late-check fires against meeting attendees, not just the organiser.** The event's
  `attendees` list (from Google Calendar) is matched to `contacts.email`; all matched contacts
  with a `tg_chat_id` receive the Telegram voice apology.

---

## 2. Telegram Integration Details

### 2.1 Long-Poll Background Task

```python
# backend/app/main.py
from contextlib import asynccontextmanager
import asyncio
from app.services.telegram import run_poller

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_poller())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)
```

```python
# backend/app/services/telegram.py
async def run_poller():
    """Long-poll loop. Runs forever as a background task."""
    offset = 0
    while True:
        try:
            updates = await poll_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                await ingest_update(update)   # calls internal ingest logic
        except Exception as e:
            print(f"[poller] error: {e}")
            await asyncio.sleep(5)            # back-off on transient failure
```

### 2.2 Message Deduplication

`messages.tg_update_id` has a `UNIQUE` constraint. If the poller delivers the same
`update_id` twice (restart scenario), the `INSERT OR IGNORE` on `messages` silently drops it.
No separate dedup table needed.

### 2.3 Sending Text (F2 automated apology — text preview only)

For the late-responder automation where attendees may not have a `tg_chat_id` yet, FastAPI
can fall back to a text message:

```python
async def send_message(chat_id: int, text: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TG_BASE}/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
```

F2 preference order: **voice note if driver has recorded one** → text apology (Gemini-drafted) as
fallback. Both are sent via the same `/api/automations/run-late-check` endpoint.

### 2.4 Car Simulator — Message Injection

`POST /api/messages/inject` inserts a fake message directly into the DB (skips Telegram), then
runs the same classify → summarize → priority pipeline. This is the **primary demo path** —
real Telegram is the bonus.

---

## 3. Data Model (SQLite — PoC Schema)

All tables in `demo.db`. Created via `SQLAlchemy create_all()` on startup. Seed applied once
if tables are empty.

### 3.0 Data Integrity Rules & Invariants (read first)

These are the rules that make the data model foolproof. They address SQLite-specific behaviour
that silently corrupts data if ignored, plus the cross-table invariants every writer must uphold.

**3.0.1 — Connection PRAGMAs (mandatory).** SQLite disables foreign-key enforcement by default and
uses a blocking rollback journal. Both must be fixed on **every** connection, or FK constraints in
this spec are decorative and the async poller will hit `database is locked` errors:

```python
# backend/app/database.py
from sqlalchemy import create_engine, event

engine = create_engine(
    "sqlite:///demo.db",
    connect_args={"check_same_thread": False},  # poller task + request handlers share the engine
)

@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")    # enforce FK constraints (OFF by default!)
    cur.execute("PRAGMA journal_mode = WAL")   # allow concurrent reads during a write
    cur.execute("PRAGMA busy_timeout = 5000")  # wait 5s instead of erroring on a locked DB
    cur.close()
```

**3.0.2 — One writer at a time.** SQLite permits a single writer. The Telegram poller and the HTTP
handlers all write. Rules: (a) each unit of work uses one short-lived `Session` and commits
promptly; (b) never hold a transaction open across an `await` to an external API (Gemini, Telegram,
TomTom) — fetch/compute first, then open the transaction to write; (c) `busy_timeout` (above)
absorbs brief contention.

**3.0.3 — Timestamp discipline.** Two storage conventions coexist by design:
- `messages.received_at`, `*.created_at/updated_at/cached_at/trigger_at` → stored by SQLAlchemy
  `DateTime` as naive **UTC**. Always write `datetime.now(timezone.utc)`; never local time.
- `calendar_events.start/end` → stored as **timezone-aware ISO-8601 TEXT** exactly as Google
  returns it (e.g. `2026-06-25T10:00:00+08:00`), because late-math must respect the event's own tz.
- Rule: any comparison between "now" and an event time converts both to aware UTC first
  (`datetime.fromisoformat(event.start).astimezone(timezone.utc)`).

**3.0.4 — Enums are single-sourced.** Every `CHECK(... IN (...))` value is mirrored by a Python
`enum.StrEnum` in `app/enums.py`. The DB `CHECK` is the hard guard; the enum is what application
code and Pydantic validate against. They must never drift.

```python
# backend/app/enums.py
from enum import StrEnum
class Priority(StrEnum):     LOW="low"; NORMAL="normal"; HIGH="high"
class MsgStatus(StrEnum):    UNREAD="unread"; SUMMARIZED="summarized"; REPLIED="replied"; SILENCED="silenced"; SEND_FAILED="send_failed"
class RelSource(StrEnum):    SEED="seed"; AI="ai_inferred"; USER="user_tagged"; UNKNOWN="unknown"
class Relationship(StrEnum): BOSS="boss"; FAMILY="family"; FRIEND="friend"; COLLEAGUE="colleague"; MARKETING="marketing"
class EtaSource(StrEnum):    TOMTOM="tomtom"; SIMULATOR="simulator"
class AudioFmt(StrEnum):     WEBM="webm_opus"; OGG="ogg_opus"
class AutoType(StrEnum):     LATE="late_responder"; PRECOOL="cabin_precool"; DEPART="departure_plan"; VOICE="voice_reply"
class AutoStatus(StrEnum):   OK="ok"; ERROR="error"; SKIPPED="skipped"
```

**3.0.5 — Nullable-UNIQUE is intentional.** `contacts.tg_chat_id`, `contacts.email`,
`contacts.phone`, and `messages.tg_update_id` are `UNIQUE` but nullable. SQLite treats each `NULL`
as distinct, so multiple rows may have `NULL` (e.g. several contacts with no Telegram yet, several
injected messages with no `tg_update_id`). This is the desired behaviour — uniqueness applies only
to non-null values.

**3.0.6 — Cross-table invariants (must always hold).**

| # | Invariant | Enforced by |
|---|---|---|
| I1 | Every `messages.contact_id` references an existing `contacts.id` | FK + `PRAGMA foreign_keys=ON` |
| I2 | A message is upserted only **after** its contact row exists | Ingest writes contact, commits, then writes message |
| I3 | Exactly one row each in `car_state` and `settings`, always `id=1` | `CHECK(id=1)` + seed `INSERT OR REPLACE` |
| I4 | `messages.status="replied"` ⟹ `audio_path`, `audio_format`, `sent_reply_text`, `replied_at` all non-null | Reply handler sets all four in one transaction |
| I5 | `messages.status="send_failed"` ⟹ no orphan file on disk | Failure path deletes the saved blob |
| I6 | `car_state.eta_source="tomtom"` ⟹ `route_eta_minutes` is non-null OR `get_resolved_eta()` returns null (never a stale value) | `/nav/route` sets both atomically; failure mutates neither |
| I7 | No two `messages` share a non-null `tg_update_id` | `UNIQUE` + `INSERT OR IGNORE` |
| I8 | A silenced or replied message is terminal for status transitions except the allowed set (§3.2.1) | `apply_status()` guard helper |

**3.0.7 — All writes go through helpers, not raw column sets.** Status changes call
`apply_status(msg, new)` (validates the transition, §3.2.1). Car/settings singletons are mutated
only via their routers. This keeps invariants in one place.

### 3.1 Table: `contacts`

```sql
CREATE TABLE contacts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name         TEXT    NOT NULL,
  phone        TEXT    UNIQUE,                    -- E.164, nullable (not all contacts have phone)
  email        TEXT    UNIQUE,                    -- matched against calendar attendee emails (F2)
  tg_chat_id   INTEGER UNIQUE,                   -- Telegram user/chat ID; null until they message the bot
  tg_username  TEXT,                             -- @username, for display only
  org          TEXT,
  relationship TEXT    CHECK(relationship IN
                ('boss','family','friend','colleague','marketing',NULL)),
  rel_source   TEXT    NOT NULL DEFAULT 'unknown'
                CHECK(rel_source IN ('seed','ai_inferred','user_tagged','unknown')),
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_contacts_tg_chat_id ON contacts(tg_chat_id);
CREATE INDEX idx_contacts_email ON contacts(email);
```

| Column | Notes |
|---|---|
| `tg_chat_id` | Telegram integer user ID. Set when they first message the bot. `null` = bot has never seen them; F2 will use text fallback. |
| `email` | Matched against `calendar_events.attendees` JSON to find who to notify in F2. Seeded for demo contacts. |
| `phone` | Optional — kept for display, not for sending. |
| `tg_username` | `@handle` from Telegram `from.username`. Display only. |
| `relationship` | `"boss"`, `"family"`, `"friend"`, `"colleague"`, `"marketing"`, or `null`. |
| `rel_source` | `"seed"` / `"ai_inferred"` / `"user_tagged"` / `"unknown"`. |

**Upsert on inbound Telegram message:**
```python
tg_id = update["message"]["from"]["id"]
name  = f"{update['message']['from'].get('first_name','')} {update['message']['from'].get('last_name','')}".strip()
contact = db.query(Contact).filter_by(tg_chat_id=tg_id).first()
if not contact:
    contact = Contact(name=name, tg_chat_id=tg_id,
                      tg_username=update["message"]["from"].get("username"))
    db.add(contact)
else:
    contact.name = name or contact.name
db.commit()
```

**Relationship resolution order:**
1. **Seed** — demo contacts with explicit labels + emails.
2. **AI-inferred** — Gemini infers from name + org on first message if `relationship IS NULL`.
3. **User-tagged** — driver patches via `PATCH /api/contacts/{id}`.
4. **Unknown fallback** — `relationship=NULL`, `priority` defaults to `"normal"`.

---

### 3.2 Table: `messages`

```sql
CREATE TABLE messages (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  contact_id      INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  tg_update_id    INTEGER UNIQUE,                 -- Telegram update_id; UNIQUE = dedup
  tg_message_id   INTEGER,                        -- Telegram message_id within the chat
  body            TEXT    NOT NULL,
  received_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  priority        TEXT NOT NULL DEFAULT 'normal'
                  CHECK(priority IN ('low','normal','high')),
  status          TEXT NOT NULL DEFAULT 'unread'
                  CHECK(status IN ('unread','summarized','replied','silenced','send_failed')),
  summary         TEXT,
  suggested_reply TEXT,                           -- Gemini-drafted text shown for driver approval
  sent_reply_text TEXT,                           -- approved text stored even though reply is audio
  replied_at      DATETIME,
  audio_path      TEXT,                           -- relative path e.g. audio_replies/7.webm
  audio_format    TEXT CHECK(audio_format IN ('webm_opus','ogg_opus',NULL))
);
CREATE INDEX idx_messages_contact_id ON messages(contact_id);
CREATE INDEX idx_messages_status ON messages(status);
CREATE INDEX idx_messages_priority ON messages(priority);
CREATE INDEX idx_messages_received_at ON messages(received_at DESC);
```

| Column | Notes |
|---|---|
| `tg_update_id` | `UNIQUE` constraint is the sole dedup mechanism — no separate table needed. |
| `tg_message_id` | Telegram's own `message_id`. Stored for reference; not used for dedup. |
| `audio_path` | Relative path to the recorded voice blob, e.g. `audio_replies/7.webm`. `null` until replied. |
| `audio_format` | `"webm_opus"` (Chrome) or `"ogg_opus"` (Firefox). Null until replied. |
| `sent_reply_text` | The approved text the driver confirmed before recording (stored for log/audit). |

> **Why `audio_path` on `messages` instead of a separate `audio_replies` table?**
> It's a 1:1 relationship with no extra attributes that matter for demo. Two columns on `messages`
> is simpler than a separate table + FK + JOIN on every message fetch.

**Status state machine:**
```
unread
  ├─ [Gemini classify+summarize] → summarized
  │     ├─ [driver records + sends reply] → replied
  │     ├─ [driver silences]              → silenced
  │     └─ [Telegram send fails]          → send_failed
  └─ [auto-silence rule fires]           → silenced
```
Once `status = "replied"`, all further status mutations return `409 Conflict`.

#### 3.2.1 Formal Status Transition Table (authoritative)

`apply_status(msg, new_status)` is the **only** function permitted to change `messages.status`.
It looks the pair up in this table; an absent pair raises `409 Conflict` (`code=INVALID_TRANSITION`).

| From \ To | unread | summarized | replied | silenced | send_failed |
|---|:--:|:--:|:--:|:--:|:--:|
| **unread** | — | ✅ classify | ❌ | ✅ auto/manual | ❌ |
| **summarized** | ❌ | ✅ re-summarize | ✅ reply ok | ✅ manual silence | ✅ send fail |
| **replied** | ❌ | ❌ | ❌ | ❌ | ❌ (terminal) |
| **silenced** | ❌ | ✅ un-silence†| ✅ reply ok | — | ❌ |
| **send_failed** | ❌ | ❌ | ✅ retry ok | ❌ | ❌ |

✅ = allowed, ❌ = rejected with `409`, — = no-op (same state, returns 200 unchanged).
† Un-silencing is optional (stretch); if not built, treat `silenced→summarized` as ❌.

**Guard reference implementation:**
```python
# backend/app/services/status.py
from app.enums import MsgStatus as S

_ALLOWED = {
    S.UNREAD:      {S.SUMMARIZED, S.SILENCED},
    S.SUMMARIZED:  {S.SUMMARIZED, S.REPLIED, S.SILENCED, S.SEND_FAILED},
    S.REPLIED:     set(),                       # terminal
    S.SILENCED:    {S.SUMMARIZED, S.REPLIED},   # un-silence + reply
    S.SEND_FAILED: {S.REPLIED},                 # retry
}

def apply_status(msg, new: S):
    cur = S(msg.status)
    if new == cur:
        return msg                              # idempotent no-op
    if new not in _ALLOWED[cur]:
        raise Conflict(code="INVALID_TRANSITION",
                       detail=f"{cur} → {new} is not allowed")
    msg.status = new
    return msg
```

---

### 3.3 Table: `car_state` (singleton)

One row, `id=1`. All mutations are `UPDATE WHERE id=1`.

```sql
CREATE TABLE car_state (
  id                INTEGER PRIMARY KEY DEFAULT 1 CHECK(id = 1),
  location_name     TEXT    NOT NULL DEFAULT 'KL Sentral',
  destination_name  TEXT,
  current_lat       REAL    NOT NULL DEFAULT 3.1319,
  current_lng       REAL    NOT NULL DEFAULT 101.6841,
  destination_lat   REAL,
  destination_lng   REAL,
  route_polyline    TEXT,                         -- JSON string "[[lat,lng],...]"
  route_eta_minutes INTEGER,                      -- TomTom-computed; feeds F2
  eta_source        TEXT    NOT NULL DEFAULT 'simulator'
                    CHECK(eta_source IN ('tomtom','simulator')),
  eta_minutes       INTEGER NOT NULL DEFAULT 20,  -- Car Simulator manual override
  cabin_temp_c      REAL    NOT NULL DEFAULT 28.0,
  target_temp_c     REAL    NOT NULL DEFAULT 22.0,
  climate_on        INTEGER NOT NULL DEFAULT 0,   -- 0/1 boolean
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

> `drive_active` and `speed_kmh` are **removed** — they only existed to support F4 animated
> marker, which is dropped.

**ETA resolution — single source of truth (used by F2 and F3):**

```python
# backend/app/services/eta.py
def get_resolved_eta(car: CarState) -> int | None:
    """Returns minutes. Never call inline if/else — always use this."""
    if car.eta_source == "simulator":
        return car.eta_minutes
    return car.route_eta_minutes   # None if no TomTom route computed yet
```

| Column | Writable by API | Notes |
|---|---|---|
| `location_name` | YES (`PUT /car/state`) | |
| `destination_name` | NO | Set by `POST /nav/route` side-effect |
| `current_lat/lng` | YES | Simulator panel input |
| `destination_lat/lng` | NO | Set by `POST /nav/route` |
| `route_polyline` | NO | Set by `POST /nav/route`; rendered on map |
| `route_eta_minutes` | NO | Set by `POST /nav/route`; feeds `get_resolved_eta()` |
| `eta_source` | YES | Switch between `"tomtom"` and `"simulator"` |
| `eta_minutes` | YES | Simulator override value |
| `cabin_temp_c` | YES | Simulator input |
| `target_temp_c` | YES | Setpoint |
| `climate_on` | NO | Set only by `POST /car/cabin/cool` |
| `resolved_eta` | COMPUTED | Not stored; always included in `/car/state` response |

---

### 3.4 Table: `calendar_events`

```sql
CREATE TABLE calendar_events (
  id              TEXT    PRIMARY KEY,            -- Google Calendar event ID
  title           TEXT    NOT NULL,
  start           TEXT    NOT NULL,               -- ISO-8601 with tz e.g. "2026-06-25T10:00:00+08:00"
  end             TEXT    NOT NULL,
  location        TEXT,
  organizer_email TEXT,
  attendees       TEXT    NOT NULL DEFAULT '[]',  -- JSON array of {"email":"...","name":"..."}
  cached_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_calendar_events_start ON calendar_events(start ASC);
```

| Column | Notes |
|---|---|
| `attendees` | JSON array. **New in v3** — used by F2 to find Telegram chat IDs to notify. Format: `[{"email":"razif@mbm.com","name":"Dato Razif","responseStatus":"accepted"}]`. |
| `organizer_email` | Kept as the primary fallback if no accepted attendees are found. |
| `cached_at` | Used to detect stale cache (warn if >1 hour old). |

**Read-through cache logic:**
```python
# services/google_cal.py
async def get_upcoming_events(db, limit=10):
    try:
        events = await fetch_from_google(limit)   # calls Google Calendar API
        for e in events:
            db.merge(CalendarEvent(**e))           # INSERT OR REPLACE
        db.commit()
        return events, "live"
    except Exception:
        cached = db.query(CalendarEvent).order_by(CalendarEvent.start).limit(limit).all()
        return cached, "cache"
```

---

### 3.5 Table: `automation_log`

```sql
CREATE TABLE automation_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  type        TEXT    NOT NULL
              CHECK(type IN ('late_responder','cabin_precool','departure_plan','voice_reply')),
  trigger_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  payload     TEXT    NOT NULL,  -- JSON snapshot
  status      TEXT    NOT NULL DEFAULT 'ok'
              CHECK(status IN ('ok','error','skipped')),
  error_msg   TEXT
);
CREATE INDEX idx_automation_log_trigger_at ON automation_log(trigger_at DESC);
```

Log rows are written on action (not on no-ops). `status="skipped"` only for late-check when
not actually late — this is what E2E tests assert.

**Example `late_responder` payload:**
```json
{
  "event_id": "abc123xyz",
  "event_title": "Board Meeting",
  "event_start": "2026-06-25T10:00:00+08:00",
  "resolved_eta_minutes": 32,
  "minutes_late": 17,
  "notified": [
    {"name": "Dato Razif", "tg_chat_id": 987654321, "format": "voice"},
    {"name": "James Tan",  "tg_chat_id": null,       "format": "text_skipped"}
  ]
}
```

---

### 3.6 Table: `settings` (singleton)

```sql
CREATE TABLE settings (
  id                   INTEGER PRIMARY KEY DEFAULT 1 CHECK(id = 1),
  target_cabin_temp_c  REAL    NOT NULL DEFAULT 22.0,
  late_threshold_min   INTEGER NOT NULL DEFAULT 15,  -- F2 fires when ETA ≥ 15 min past start
  precool_lead_min     INTEGER NOT NULL DEFAULT 10,
  quiet_contact_ids    TEXT    NOT NULL DEFAULT '[]' -- JSON array of contact IDs
);
```

> `late_threshold_min` changed from 5 to **15** to match the new F2 trigger condition
> ("ETA is 15 mins or more from the meeting start time").

---

### 3.7 SQLAlchemy ORM Models

```python
# backend/app/models.py

class Contact(Base):
    __tablename__ = "contacts"
    id           = Column(Integer, primary_key=True)
    name         = Column(Text, nullable=False)
    phone        = Column(Text, unique=True)
    email        = Column(Text, unique=True)
    tg_chat_id   = Column(Integer, unique=True)
    tg_username  = Column(Text)
    org          = Column(Text)
    relationship = Column(Text)
    rel_source   = Column(Text, default="unknown")
    created_at   = Column(DateTime, default=func.now())
    updated_at   = Column(DateTime, default=func.now(), onupdate=func.now())
    messages     = relationship("Message", back_populates="contact")

class Message(Base):
    __tablename__ = "messages"
    id              = Column(Integer, primary_key=True)
    contact_id      = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    tg_update_id    = Column(Integer, unique=True)       # dedup key
    tg_message_id   = Column(Integer)
    body            = Column(Text, nullable=False)
    received_at     = Column(DateTime, default=func.now())
    priority        = Column(Text, default="normal")
    status          = Column(Text, default="unread")
    summary         = Column(Text)
    suggested_reply = Column(Text)
    sent_reply_text = Column(Text)
    replied_at      = Column(DateTime)
    audio_path      = Column(Text)
    audio_format    = Column(Text)
    contact         = relationship("Contact", back_populates="messages")

class CarState(Base):
    __tablename__ = "car_state"
    id                = Column(Integer, primary_key=True, default=1)
    location_name     = Column(Text, default="KL Sentral")
    destination_name  = Column(Text)
    current_lat       = Column(Float, default=3.1319)
    current_lng       = Column(Float, default=101.6841)
    destination_lat   = Column(Float)
    destination_lng   = Column(Float)
    route_polyline    = Column(Text)
    route_eta_minutes = Column(Integer)
    eta_source        = Column(Text, default="simulator")
    eta_minutes       = Column(Integer, default=20)
    cabin_temp_c      = Column(Float, default=28.0)
    target_temp_c     = Column(Float, default=22.0)
    climate_on        = Column(Integer, default=0)
    updated_at        = Column(DateTime, default=func.now(), onupdate=func.now())

class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id              = Column(Text, primary_key=True)
    title           = Column(Text, nullable=False)
    start           = Column(Text, nullable=False)
    end             = Column(Text, nullable=False)
    location        = Column(Text)
    organizer_email = Column(Text)
    attendees       = Column(Text, default="[]")   # JSON
    cached_at       = Column(DateTime, default=func.now())

class AutomationLog(Base):
    __tablename__ = "automation_log"
    id         = Column(Integer, primary_key=True)
    type       = Column(Text, nullable=False)
    trigger_at = Column(DateTime, default=func.now())
    payload    = Column(Text, nullable=False)
    status     = Column(Text, default="ok")
    error_msg  = Column(Text)

class Settings(Base):
    __tablename__ = "settings"
    id                  = Column(Integer, primary_key=True, default=1)
    target_cabin_temp_c = Column(Float, default=22.0)
    late_threshold_min  = Column(Integer, default=15)
    precool_lead_min    = Column(Integer, default=10)
    quiet_contact_ids   = Column(Text, default="[]")
```

**Table count: 6.** No `webhook_events` (dedup is the `UNIQUE` on `tg_update_id`). No separate
`audio_replies` table (two columns on `messages` is sufficient).

---

### 3.8 Constraint & Validation Catalog (the foolproof summary)

Every field that can reject bad data, in one place. "DB" = enforced by SQLite; "App" = enforced by
Pydantic/handler before the DB is touched. Both layers apply to inputs (defense in depth).

| Table.Column | Type | DB constraint | App validation |
|---|---|---|---|
| `contacts.name` | TEXT | NOT NULL | 1–120 chars, trimmed |
| `contacts.phone` | TEXT | UNIQUE (nullable) | E.164 regex `^\+?[1-9]\d{6,14}$` if present |
| `contacts.email` | TEXT | UNIQUE (nullable) | RFC-lite email if present; lowercased on write |
| `contacts.tg_chat_id` | INTEGER | UNIQUE (nullable) | positive int if present |
| `contacts.relationship` | TEXT | CHECK in enum or NULL | `Relationship` enum or null |
| `contacts.rel_source` | TEXT | NOT NULL, CHECK in enum | `RelSource` enum; defaults `unknown` |
| `messages.contact_id` | INTEGER | NOT NULL, FK→contacts.id | must resolve to existing contact |
| `messages.tg_update_id` | INTEGER | UNIQUE (nullable) | positive int or null (inject = null) |
| `messages.body` | TEXT | NOT NULL | 1–4096 chars; empty→`"[no text]"` |
| `messages.priority` | TEXT | NOT NULL, CHECK in enum | `Priority` enum; default `normal` |
| `messages.status` | TEXT | NOT NULL, CHECK in enum | only via `apply_status()` (§3.2.1) |
| `messages.audio_format` | TEXT | CHECK in enum or NULL | set with `audio_path` together or both null |
| `car_state.id` | INTEGER | PK, CHECK(id=1) | never accepted in request body |
| `car_state.eta_source` | TEXT | NOT NULL, CHECK in enum | `EtaSource` enum |
| `car_state.eta_minutes` | INTEGER | NOT NULL | 0 ≤ n ≤ 600 |
| `car_state.route_eta_minutes` | INTEGER | nullable | 0 ≤ n ≤ 600; write-locked to `/nav/route` |
| `car_state.cabin_temp_c` | REAL | NOT NULL | 14.0 ≤ t ≤ 40.0 |
| `car_state.target_temp_c` | REAL | NOT NULL | 16.0 ≤ t ≤ 30.0 |
| `car_state.current_lat` | REAL | NOT NULL | −90 ≤ lat ≤ 90 |
| `car_state.current_lng` | REAL | NOT NULL | −180 ≤ lng ≤ 180 |
| `calendar_events.id` | TEXT | PK | non-empty Google event id |
| `calendar_events.start/end` | TEXT | NOT NULL | parseable aware ISO-8601; `end ≥ start` |
| `calendar_events.attendees` | TEXT | NOT NULL default `[]` | valid JSON array of `{email,name,responseStatus}` |
| `settings.id` | INTEGER | PK, CHECK(id=1) | never in request body |
| `settings.late_threshold_min` | INTEGER | NOT NULL | 0 ≤ n ≤ 180 |
| `settings.precool_lead_min` | INTEGER | NOT NULL | 0 ≤ n ≤ 60 |
| `settings.quiet_contact_ids` | TEXT | NOT NULL default `[]` | JSON array of ints; each must exist in `contacts` |
| `automation_log.type` | TEXT | NOT NULL, CHECK in enum | `AutoType` enum |
| `automation_log.payload` | TEXT | NOT NULL | valid JSON object |
| `automation_log.status` | TEXT | NOT NULL, CHECK in enum | `AutoStatus` enum |

**Audio upload constraints (`POST /messages/{id}/reply`):**

| Rule | Value | On violation |
|---|---|---|
| Content-Type | `audio/webm` or `audio/ogg` | `422 INVALID_AUDIO_TYPE` |
| Max file size | 5 MB | `413 AUDIO_TOO_LARGE` |
| Min file size | 100 bytes (reject empty recordings) | `422 AUDIO_EMPTY` |
| `approved_text` length | 1–1000 chars | `422 VALIDATION_ERROR` |
| Target contact has `tg_chat_id` | required | `409 NO_TELEGRAM_CHAT` |

---

## 4. Primary Features (Must-Demo)

### F1 — Telegram Message Triage + Mic-Recorded Voice Reply

**Inbound path:**
- Telegram long-poller picks up messages → internal ingest.
- Contact upserted by `tg_chat_id`. If `relationship IS NULL` → AI inference.
- Gemini classifies priority (`low` / `normal` / `high`) and summarizes.
- `marketing` contacts or `low`-priority → auto-silenced.
- Dashboard shows card for `normal` / `high` messages with Gemini-drafted reply suggestion.

**Reply path (Option A — real mic):**
- Driver taps "Reply" on a message card.
- Browser calls `getUserMedia({audio:true})` — prompts mic permission once.
- Driver reads (or ad-libs from) the suggested reply text; taps "Stop".
- `MediaRecorder` blob (WebM/Opus or OGG/Opus) uploaded to `POST /api/messages/{id}/reply`.
- FastAPI saves blob to `backend/audio_replies/<message_id>.webm`, calls `telegram.send_voice(tg_chat_id, blob)`.
- On success: `messages.status="replied"`, `audio_path` and `audio_format` set, `automation_log` row.
- On Telegram failure: `messages.status="send_failed"`, saved file deleted.
- Inject fallback: `POST /api/messages/inject` for offline demo (skips Telegram entirely).

**✅ F1 — Conditions of Success (Done when):**

| # | Acceptance criterion | How to verify |
|---|---|---|
| F1-1 | A Telegram DM to the bot appears as a `messages` row within 3 s, `status` `unread`→`summarized` | Send DM → `GET /api/messages` shows it with a `summary` |
| F1-2 | Priority is assigned: boss/high-intent → `high`, marketing → `low` | Inject 3 seed messages → priorities match §9.2 |
| F1-3 | `low`+`marketing` messages auto-set `status="silenced"` and never alert | Inject Acme message → not in `?status=unread`, present in `?status=silenced` |
| F1-4 | A new sender creates exactly one `contacts` row; a repeat sender creates none | Inject twice from same `tg_chat_id` → contact count +1 only |
| F1-5 | Driver can record a voice note and it is delivered to the sender's Telegram | Reply flow → voice bubble appears in sender's chat |
| F1-6 | After a successful reply, message is `replied` with all four reply fields set (I4) | `GET /api/messages/{id}` → `audio_path`, `audio_format`, `sent_reply_text`, `replied_at` non-null |
| F1-7 | Telegram send failure leaves `status="send_failed"`, no orphan file (I5), no 500 to client | Mock Telegram 500 → status correct, `audio_replies/` has no stale file, HTTP 200 |
| F1-8 | Replying to / silencing an already-`replied` message returns `409 INVALID_TRANSITION` | `POST /{id}/silence` on replied msg → 409 |
| F1-9 | Duplicate Telegram `update_id` never creates a second row (I7) | Re-deliver same update → row count unchanged |
| F1-10 | Gemini outage still yields a usable row (`priority="normal"`, `summary=null`), HTTP 200 | Mock Gemini raise → message created, request 200 |

### F2 — Arriving-Late Responder (triggered by nav ETA)

**Trigger condition:** `get_resolved_eta() ≥ settings.late_threshold_min` (default: 15 min) past
the start time of the next calendar event.

**Flow:**
1. `POST /api/automations/run-late-check` is called (manually from dashboard, or driver voice command "am I late?").
2. Fetches next upcoming event from `calendar_events`.
3. Computes `minutes_late = (now + resolved_eta) − event.start` in minutes.
4. If `minutes_late < 15`: returns `is_late=false`, logs `status="skipped"`.
5. If `minutes_late ≥ 15`:
   - Gemini drafts a short apology: `"Hi {name}, I'm running about {N} minutes late to {event_title}. See you soon."`.
   - Parses `calendar_events.attendees` JSON → matches emails against `contacts.email`.
   - For each matched contact with `tg_chat_id`: sends **Telegram text message** (Gemini draft).
   - Logs `automation_log` row with `type="late_responder"`, full notified list.

> **Voice note for F2:** The late-responder sends a **text message** (Gemini draft) because the
> driver is driving and cannot record a voice note. Only F1 manual replies use mic recording.
> This keeps F2 fully automated and non-interactive.

**ETA source for F2:**
- If `eta_source="simulator"`: uses `car_state.eta_minutes` (set by Car Simulator panel).
- If `eta_source="tomtom"`: uses `car_state.route_eta_minutes` (set by `POST /nav/route`).
- For the demo: set `eta_source="tomtom"` and use the map to route to the event venue → real
  TomTom ETA trips the late-check automatically. Or use simulator override for reliable demo.

**Exact lateness math (authoritative):**
```python
now      = datetime.now(timezone.utc)
eta_min  = get_resolved_eta(car)                       # None → is_late=False, status="skipped"
start    = datetime.fromisoformat(event.start).astimezone(timezone.utc)
arrival  = now + timedelta(minutes=eta_min)
mins_late = round((arrival - start).total_seconds() / 60)
is_late  = mins_late >= settings.late_threshold_min    # default 15
```

**✅ F2 — Conditions of Success (Done when):**

| # | Acceptance criterion | How to verify |
|---|---|---|
| F2-1 | When projected arrival is ≥15 min after event start, `is_late=true` | Set `eta_minutes=35`, event in 20 min → `is_late=true`, `minutes_late=15` |
| F2-2 | When <15 min late, `is_late=false` and a `skipped` log row is written | Set `eta_minutes=25`, event in 20 min → `is_late=false`, log `status="skipped"` |
| F2-3 | Every accepted attendee matched to a contact **with** `tg_chat_id` receives a Telegram message | 2 matched attendees → both `message_sent_to[].status="sent"` |
| F2-4 | Attendees with no `tg_chat_id` are skipped, not errored | Attendee without TG → entry `status="skipped"`, no crash |
| F2-5 | Works identically whether ETA came from simulator or TomTom (single source of truth) | Run F2-1 once with each `eta_source` → same outcome |
| F2-6 | Exactly one `automation_log` row per invocation, with full notified list in `payload` | Run once → one `late_responder` row; `payload.notified` lists all recipients |
| F2-7 | No upcoming event → graceful `is_late=false`, `event=null`, `status="skipped"` | Empty calendar → no crash, skipped log |
| F2-8 | Gemini draft failure falls back to a static apology template, still sends | Mock Gemini raise → static text sent, log `status="ok"` |

### F3 — Calendar → Cabin Cooling + Departure Planning

- `GET /api/calendar/events` fetches from Google Calendar (cached in SQLite).
- `GET /api/automations/next-departure` computes:
  - `leave_by = event.start − get_resolved_eta() − 5 min buffer`
  - `precool_due = leave_by − settings.precool_lead_min`
  - `is_late` (same logic as F2)
- Dashboard "Next Trip" card shows leave-by countdown + is-late warning.
- `POST /api/car/cabin/cool`: sets `climate_on=true`, logs `automation_log` with `type="cabin_precool"`.
- The dashboard can trigger pre-cool manually ("Cool cabin now") or it can be shown as a prompt when `now ≥ precool_due`.

**✅ F3 — Conditions of Success (Done when):**

| # | Acceptance criterion | How to verify |
|---|---|---|
| F3-1 | `GET /api/calendar/events` returns live Google events after OAuth, `source="live"` | Auth then fetch → real events, `source="live"` |
| F3-2 | If Google is unreachable, cached rows are returned with `source="cache"` (no 500) | Mock Google down → cached events, `source="cache"` |
| F3-3 | `leave_by` equals `event.start − resolved_eta − 5 min` exactly | Known event + ETA → computed `leave_by` matches |
| F3-4 | `precool_due` equals `leave_by − precool_lead_min` | Same fixture → `precool_due` matches |
| F3-5 | `POST /car/cabin/cool` sets `climate_on=true` and writes a `cabin_precool` log row | Call → `GET /car/state` shows `climate_on=true`; log present |
| F3-6 | Calling cabin/cool when already on is idempotent (still 200, one extra log row only if state changed) | Call twice → `climate_on` stays true, no error |
| F3-7 | `precool_fired` flips to true once a precool log exists for the current event | After F3-5 → `next-departure.precool_fired=true` |

### Navigation (utility, not a feature)

The TomTom integration exists only to give F2 a realistic ETA when `eta_source="tomtom"`:

- Driver types a destination in the dashboard search box.
- `POST /api/nav/geocode` resolves the text to lat/lng.
- `POST /api/nav/route` calls TomTom Routing API → returns polyline + ETA.
- FastAPI writes `route_polyline`, `route_eta_minutes`, and `eta_source="tomtom"` to `car_state`.
- The map renders the polyline (TomTom Maps SDK). That's the full extent of the nav feature.
- No animated marker. No turn-by-turn. No traffic overlay. No drive controls.

**✅ Navigation — Conditions of Success (Done when):**

| # | Acceptance criterion | How to verify |
|---|---|---|
| N-1 | `POST /nav/route` writes `route_polyline`, `route_eta_minutes`, `eta_source="tomtom"` atomically | Call with mocked TomTom → all three set together |
| N-2 | TomTom failure returns `502` and mutates **nothing** in `car_state` (I6) | Mock TomTom 500 → 502; `car_state` unchanged, `eta_source` unchanged |
| N-3 | After a route, the map renders the polyline and F2 uses the new ETA | Route → reload dashboard → polyline visible; run F2 → uses `route_eta_minutes` |
| N-4 | `TOMTOM_API_KEY` never appears in any browser-facing response or asset | Inspect network tab → server key absent |

---

## 5. Voice + Screen Interface

**Dashboard cards (React MBUX-style):**
- **Messages card** — unread/summarized Telegram messages, priority badge, summary text, "Reply" + "Silence" buttons.
- **Reply card (modal)** — shows Gemini-drafted suggested text; mic record button; send button.
- **Next Trip card** — next event title/time, leave-by countdown, is-late warning, "Cool Cabin" button.
- **Map card** — TomTom Maps SDK; destination search box; shows polyline after route computed; ETA badge.
- **Car Simulator panel** (dev/demo) — set ETA source, eta_minutes, cabin_temp, location; inject Telegram message.

**Voice input (STT — Web Speech API):**
Commands: `"read my messages"`, `"am I late?"`, `"cool the cabin"`, `"navigate to [place]"`.
Transcript → `POST /api/assistant/command` → Gemini function-calling → action + `spoken_text` → TTS.

**Voice output (TTS — Web Speech API):**
Reads message summaries, departure countdowns, late alerts. No turn-by-turn.

**Mic recording (for F1 replies):**
```javascript
// 1. Request mic
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
// 2. Record
const recorder = new MediaRecorder(stream, {
  mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
    ? "audio/webm;codecs=opus"
    : "audio/ogg;codecs=opus"
});
recorder.start();
// 3. On stop — collect blob and POST
recorder.ondataavailable = (e) => chunks.push(e.data);
recorder.onstop = async () => {
  const blob = new Blob(chunks, { type: recorder.mimeType });
  const fd = new FormData();
  fd.append("audio", blob, "reply.webm");
  fd.append("approved_text", suggestedReplyText);
  await fetch(`/api/messages/${messageId}/reply`, { method: "POST", body: fd });
};
```

---

## 6. API Contracts

All endpoints prefixed `/api`. All responses are bare JSON objects (no `{ok, data}` envelope —
FastAPI `HTTPException` handles error shape). Every request body and response is backed by a
Pydantic model (§6.0) — there are no untyped dict endpoints.

### 6.0 Pydantic API Models (`app/schemas.py`)

These are the authoritative request/response contracts. FastAPI validates inbound bodies against
the `*In` / `*Request` models and serializes outbound via the `*Out` models (`response_model=`).
Field constraints here mirror the validation catalog in §3.8.

```python
# backend/app/schemas.py
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from datetime import datetime
from app.enums import Priority, MsgStatus, Relationship, RelSource, EtaSource, AudioFmt

# ---------- shared ----------
class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # read straight off SQLAlchemy rows

# ---------- contacts ----------
class ContactOut(ORMModel):
    id: int
    name: str
    phone: str | None = None
    email: EmailStr | None = None
    tg_chat_id: int | None = None
    tg_username: str | None = None
    org: str | None = None
    relationship: Relationship | None = None
    rel_source: RelSource

class ContactPatch(BaseModel):
    relationship: Relationship | None = None
    email: EmailStr | None = None
    org: str | None = Field(default=None, max_length=120)
    # rel_source is forced to "user_tagged" by the handler, never accepted from client

# ---------- messages ----------
class MessageOut(ORMModel):
    id: int
    contact_id: int
    contact_name: str                 # joined from contacts.name
    tg_chat_id: int | None = None     # joined from contacts.tg_chat_id
    body: str
    received_at: datetime
    priority: Priority
    status: MsgStatus
    summary: str | None = None
    suggested_reply: str | None = None
    sent_reply_text: str | None = None
    replied_at: datetime | None = None
    audio_format: AudioFmt | None = None

class MessageListOut(BaseModel):
    items: list[MessageOut]
    count: int                        # also mirrored in X-Total-Count header

class InjectRequest(BaseModel):
    tg_chat_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=120)
    body: str = Field(..., min_length=1, max_length=4096)
    received_at: datetime | None = None   # defaults to now(UTC) if omitted
    email: EmailStr | None = None         # optional, helps F2 attendee matching

class ReplyForm(BaseModel):
    # multipart: `audio` arrives as UploadFile in the handler signature, not here
    approved_text: str = Field(..., min_length=1, max_length=1000)

# ---------- car_state ----------
class CarStateOut(ORMModel):
    location_name: str
    destination_name: str | None = None
    current_lat: float
    current_lng: float
    destination_lat: float | None = None
    destination_lng: float | None = None
    route_polyline: str | None = None
    route_eta_minutes: int | None = None
    eta_source: EtaSource
    eta_minutes: int
    resolved_eta: int | None = None    # computed, injected by handler
    cabin_temp_c: float
    target_temp_c: float
    climate_on: bool
    updated_at: datetime

class CarStatePatch(BaseModel):
    # only writable fields; NO id, NO route_*, NO destination_*, NO climate_on
    location_name: str | None = Field(default=None, max_length=120)
    current_lat: float | None = Field(default=None, ge=-90, le=90)
    current_lng: float | None = Field(default=None, ge=-180, le=180)
    eta_source: EtaSource | None = None
    eta_minutes: int | None = Field(default=None, ge=0, le=600)
    cabin_temp_c: float | None = Field(default=None, ge=14.0, le=40.0)
    target_temp_c: float | None = Field(default=None, ge=16.0, le=30.0)

# ---------- calendar ----------
class Attendee(BaseModel):
    email: EmailStr
    name: str | None = None
    responseStatus: str | None = None

class CalendarEventOut(ORMModel):
    id: str
    title: str
    start: str            # ISO-8601 aware string, passed through verbatim
    end: str
    location: str | None = None
    organizer_email: EmailStr | None = None
    attendees: list[Attendee] = []
    cached_at: datetime
    source: str           # "live" | "cache", injected by handler

# ---------- navigation ----------
class GeocodeRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)

class GeocodeOut(BaseModel):
    lat: float
    lng: float
    label: str

class RouteRequest(BaseModel):
    origin_lat: float = Field(..., ge=-90, le=90)
    origin_lng: float = Field(..., ge=-180, le=180)
    dest_lat: float = Field(..., ge=-90, le=90)
    dest_lng: float = Field(..., ge=-180, le=180)

class RouteResultOut(BaseModel):
    polyline: list[tuple[float, float]]
    eta_minutes: int = Field(..., ge=0, le=600)
    distance_km: float
    destination_name: str

# ---------- automations ----------
class NotifiedTarget(BaseModel):
    name: str
    tg_chat_id: int | None = None
    status: str            # "sent" | "skipped" | "failed"

class NextDepartureOut(BaseModel):
    event: CalendarEventOut | None = None
    resolved_eta: int | None = None
    eta_source: EtaSource
    leave_by: datetime | None = None
    minutes_until_leave: int | None = None
    is_late: bool
    precool_due: datetime | None = None
    precool_fired: bool

class LateCheckResultOut(BaseModel):
    is_late: bool
    minutes_late: int | None = None
    event: CalendarEventOut | None = None
    message_sent_to: list[NotifiedTarget] = []
    log_id: int

class AutomationLogOut(ORMModel):
    id: int
    type: str
    trigger_at: datetime
    payload: dict          # parsed from JSON TEXT
    status: str
    error_msg: str | None = None

# ---------- assistant ----------
class AssistantCommand(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=300)

class AssistantResultOut(BaseModel):
    spoken_text: str
    action: str | None = None
    action_data: dict | None = None
```

### 6.0.1 Endpoint → Model Map

| Endpoint | Request model | Response model | Success status |
|---|---|---|---|
| `POST /messages/inject` | `InjectRequest` | `MessageOut` | 201 |
| `GET /messages` | query params | `MessageListOut` | 200 |
| `GET /messages/{id}` | — | `MessageOut` | 200 |
| `POST /messages/{id}/summarize` | — | `MessageOut` | 200 |
| `POST /messages/{id}/reply` | `ReplyForm` + `UploadFile` | `MessageOut` | 200 |
| `POST /messages/{id}/silence` | — | `MessageOut` | 200 |
| `GET /calendar/events` | — | `list[CalendarEventOut]` | 200 |
| `GET /car/state` | — | `CarStateOut` | 200 |
| `PUT /car/state` | `CarStatePatch` | `CarStateOut` | 200 |
| `POST /car/cabin/cool` | — | `CarStateOut` | 200 |
| `POST /nav/geocode` | `GeocodeRequest` | `GeocodeOut` | 200 |
| `POST /nav/route` | `RouteRequest` | `RouteResultOut` | 200 |
| `GET /automations/next-departure` | — | `NextDepartureOut` | 200 |
| `POST /automations/run-late-check` | — | `LateCheckResultOut` | 200 |
| `GET /automations/log` | query params | `list[AutomationLogOut]` | 200 |
| `POST /assistant/command` | `AssistantCommand` | `AssistantResultOut` | 200 |
| `GET /contacts` | — | `list[ContactOut]` | 200 |
| `PATCH /contacts/{id}` | `ContactPatch` | `ContactOut` | 200 |

### 6.0.2 Standardized Error Catalog

All errors share the FastAPI shape `{"detail": "...", "code": "SNAKE_CODE"}` (a custom exception
handler adds `code`). Validation errors (422) use FastAPI's default body. Handlers raise only the
codes below.

| `code` | HTTP | Meaning | Raised by |
|---|---|---|---|
| `NOT_FOUND` | 404 | Message / contact / event id does not exist | any `/{id}` route |
| `INVALID_TRANSITION` | 409 | Status change not allowed by §3.2.1 | reply, silence |
| `NO_TELEGRAM_CHAT` | 409 | Target contact has no `tg_chat_id` to send to | reply |
| `INVALID_AUDIO_TYPE` | 422 | Upload not `audio/webm`/`audio/ogg` | reply |
| `AUDIO_TOO_LARGE` | 413 | Upload > 5 MB | reply |
| `AUDIO_EMPTY` | 422 | Upload < 100 bytes | reply |
| `VALIDATION_ERROR` | 422 | Pydantic body/query validation failed | any typed body |
| `CALENDAR_NOT_AUTHORISED` | 409 | No stored Google token; visit `/calendar/auth` | calendar events |
| `UPSTREAM_TOMTOM` | 502 | TomTom routing/geocode failed | nav routes |
| `UPSTREAM_TELEGRAM` | 502 | Telegram API unreachable (poller logs only; sends set `send_failed`) | nav N/A |
| `SINGLETON_VIOLATION` | 400 | Request body tried to set `id` on a singleton | car/settings PUT |

**Rule:** Gemini failures are **never** surfaced as errors — they degrade gracefully (§8.3) and the
request still returns its normal 2xx model with null AI fields.

---

### 6.1 Health

| Method | Path | Response |
|---|---|---|
| `GET` | `/health` | `{"status":"ok","version":"3.1.0"}` |

---

### 6.2 Messages (F1)

| Method | Path | Request Body | Response | HTTP |
|---|---|---|---|---|
| `POST` | `/api/messages/inject` | `{"tg_chat_id":int,"name":"str","body":"str","received_at":"ISO?"}` | Message object | 201 |
| `GET`  | `/api/messages` | Query: `?status=unread&priority=high&limit=50` | `[Message]` + header `X-Total-Count` | 200 |
| `GET`  | `/api/messages/{id}` | — | Message object | 200 |
| `POST` | `/api/messages/{id}/summarize` | — | Message object (summary + priority populated) | 200 |
| `POST` | `/api/messages/{id}/reply` | Multipart: `audio` (blob) + `approved_text` (str) | Message object with `status="replied"` | 200 |
| `POST` | `/api/messages/{id}/silence` | — | Message object with `status="silenced"` | 200 / 409 |

**`POST /api/messages/{id}/reply` — multipart fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `audio` | File | YES | WebM/Opus or OGG/Opus blob from MediaRecorder |
| `approved_text` | str | YES | Stored in `messages.sent_reply_text` |

**Message object schema:**

| Field | Type | Example |
|---|---|---|
| `id` | int | `3` |
| `contact_id` | int | `1` |
| `contact_name` | str | `"Ahmad Razif"` |
| `tg_chat_id` | int\|null | `987654321` |
| `body` | str | `"Running 10 min late, is that okay?"` |
| `received_at` | ISO str | `"2026-06-25T08:45:00Z"` |
| `priority` | str | `"high"` |
| `status` | str | `"summarized"` |
| `summary` | str\|null | `"Ahmad is asking if a 10-min delay is acceptable."` |
| `suggested_reply` | str\|null | `"Thanks Ahmad, that works fine!"` |
| `sent_reply_text` | str\|null | `"Thanks Ahmad, that works fine!"` |
| `replied_at` | ISO str\|null | `null` |
| `audio_format` | str\|null | `"webm_opus"` |

**Ingest business rules (applies to both long-poll and `/inject`):**
- Upsert contact by `tg_chat_id`. If `relationship IS NULL`, trigger AI inference.
- If contact is in `settings.quiet_contact_ids` OR (`priority="low"` AND `relationship="marketing"`), auto-set `status="silenced"`.
- Only `"private"` chat type messages are processed; group/channel messages are dropped.
- Gemini failure: `priority="normal"`, `summary=null` — message still created.
- Duplicate `tg_update_id`: SQLite `UNIQUE` constraint → `INSERT OR IGNORE` → silently skipped.

---

### 6.3 Google Calendar (F3)

| Method | Path | Response |
|---|---|---|
| `GET` | `/api/calendar/auth` | 302 redirect to Google OAuth consent page |
| `GET` | `/api/calendar/callback` | Exchanges code for tokens; stores in `calendar_token.json`; 302 to dashboard |
| `GET` | `/api/calendar/events` | `[CalendarEvent]` with `source` field |

**CalendarEvent object:**

| Field | Type | Example |
|---|---|---|
| `id` | str | `"abc123xyz"` |
| `title` | str | `"Board Meeting"` |
| `start` | ISO str | `"2026-06-25T10:00:00+08:00"` |
| `end` | ISO str | `"2026-06-25T11:00:00+08:00"` |
| `location` | str\|null | `"Menara Mercedes, KL"` |
| `organizer_email` | str\|null | `"razif@mbm.com"` |
| `attendees` | array | `[{"email":"razif@mbm.com","name":"Dato Razif","responseStatus":"accepted"}]` |
| `cached_at` | ISO str | `"2026-06-25T09:00:00Z"` |
| `source` | str | `"live"` or `"cache"` |

**Google Calendar OAuth flow (one-time per demo setup):**
1. Driver opens `GET /api/calendar/auth` → browser redirects to Google.
2. Driver logs in + grants Calendar read permission.
3. Google redirects to `GET /api/calendar/callback?code=...`.
4. FastAPI exchanges code → stores tokens in `backend/calendar_token.json` (git-ignored).
5. All subsequent `GET /api/calendar/events` calls use the stored token; refresh is automatic via `google-auth-library`.

**Scopes required:** `https://www.googleapis.com/auth/calendar.readonly`

---

### 6.4 Car / Simulator State

| Method | Path | Request Body | Response |
|---|---|---|---|
| `GET`  | `/api/car/state` | — | CarState object (includes computed `resolved_eta`) |
| `PUT`  | `/api/car/state` | Writable CarState fields | Updated CarState |
| `POST` | `/api/car/cabin/cool` | — | Updated CarState with `climate_on=true` |

**CarState response object:**

| Field | Type | Writable | Notes |
|---|---|---|---|
| `location_name` | str | YES | |
| `destination_name` | str\|null | NO | Set by `/nav/route` |
| `current_lat` | float | YES | Simulator input |
| `current_lng` | float | YES | Simulator input |
| `destination_lat/lng` | float\|null | NO | Set by `/nav/route` |
| `route_polyline` | str\|null | NO | Set by `/nav/route`; JSON `"[[lat,lng],...]"` |
| `route_eta_minutes` | int\|null | NO | Set by `/nav/route` |
| `eta_source` | str | YES | `"tomtom"` or `"simulator"` |
| `eta_minutes` | int | YES | Simulator override |
| `resolved_eta` | int\|null | COMPUTED | `get_resolved_eta()` — never stored |
| `cabin_temp_c` | float | YES | |
| `target_temp_c` | float | YES | |
| `climate_on` | bool | NO | Set only by `/car/cabin/cool` |
| `updated_at` | ISO str | — | |

---

### 6.5 Navigation (ETA utility — feeds F2)

`TOMTOM_API_KEY` stays server-side only.

| Method | Path | Request Body | Response |
|---|---|---|---|
| `POST` | `/api/nav/geocode` | `{"query":"Menara Mercedes"}` | `{"lat":3.14,"lng":101.69,"label":"Menara Mercedes, KL"}` |
| `POST` | `/api/nav/route` | `{"origin_lat":f,"origin_lng":f,"dest_lat":f,"dest_lng":f}` | RouteResult |

**RouteResult object:**

| Field | Type | Notes |
|---|---|---|
| `polyline` | `[[lat,lng],...]` | Written to `car_state.route_polyline` |
| `eta_minutes` | int | Written to `car_state.route_eta_minutes`; flips `eta_source="tomtom"` |
| `distance_km` | float | Display only |
| `destination_name` | str | Written to `car_state.destination_name` |

`POST /api/nav/route` side-effects: updates `car_state` fields `destination_lat/lng`,
`destination_name`, `route_polyline`, `route_eta_minutes`, `eta_source="tomtom"`.

TomTom failure → `502`; `car_state` NOT mutated.

> Turn-by-turn maneuvers are **not requested or stored** — TomTom call uses `instructionsType=none`
> to save response size and avoid unused parsing.

---

### 6.6 Automations (F2 + F3)

| Method | Path | Response |
|---|---|---|
| `GET`  | `/api/automations/next-departure` | NextDeparture object |
| `POST` | `/api/automations/run-late-check` | LateCheckResult object |
| `GET`  | `/api/automations/log` | `[AutomationLogRow]` — query: `?limit=20` |

**NextDeparture object:**

| Field | Type | Notes |
|---|---|---|
| `event` | CalendarEvent\|null | Next upcoming event |
| `resolved_eta` | int\|null | From `get_resolved_eta()` |
| `eta_source` | str | `"tomtom"` or `"simulator"` |
| `leave_by` | ISO str\|null | `event.start − resolved_eta − 5 min` |
| `minutes_until_leave` | int\|null | Countdown in minutes (negative = already late to leave) |
| `is_late` | bool | `(now + resolved_eta) ≥ event.start + late_threshold_min` |
| `precool_due` | ISO str\|null | `leave_by − precool_lead_min` |
| `precool_fired` | bool | True if a `cabin_precool` log exists for this event today |

**LateCheckResult object:**

| Field | Type | Notes |
|---|---|---|
| `is_late` | bool | |
| `minutes_late` | int\|null | Null if not late |
| `event` | CalendarEvent\|null | |
| `message_sent_to` | array | `[{"name":"...","tg_chat_id":int,"status":"sent"/"skipped"}]` |
| `log_id` | int | `automation_log.id` |

---

### 6.7 Assistant Voice Command

| Method | Path | Request Body | Response |
|---|---|---|---|
| `POST` | `/api/assistant/command` | `{"transcript":"am I late?"}` | AssistantResult |

**Gemini function tools:**

| Tool | Trigger phrase examples | Action |
|---|---|---|
| `summarize_messages` | "read my messages", "what did I miss?" | Classify+summarize all `unread` messages |
| `late_check` | "am I late?", "will I make it?" | Runs `run-late-check` logic; returns spoken result |
| `cabin_cool` | "cool the cabin", "start AC" | Calls `POST /car/cabin/cool` |
| `navigate_to` | "navigate to the office" | Geocode → route; updates `car_state` |

**AssistantResult:**

| Field | Type | Notes |
|---|---|---|
| `spoken_text` | str | TTS-ready. Always present, even on error. |
| `action` | str\|null | Which tool was called |
| `action_data` | object\|null | Tool output (e.g. LateCheckResult) |

---

### 6.8 Contacts

| Method | Path | Request Body | Response |
|---|---|---|---|
| `GET`   | `/api/contacts` | — | `[Contact]` |
| `PATCH` | `/api/contacts/{id}` | `{"relationship":"boss","email":"razif@mbm.com"}` | Updated Contact |

**Contact object:**

| Field | Type | Example |
|---|---|---|
| `id` | int | `1` |
| `name` | str | `"Dato Razif"` |
| `phone` | str\|null | `"+60121110001"` |
| `email` | str\|null | `"razif@mbm.com"` |
| `tg_chat_id` | int\|null | `987654321` |
| `tg_username` | str\|null | `"ahmadrazif"` |
| `org` | str\|null | `"MBM Executive"` |
| `relationship` | str\|null | `"boss"` |
| `rel_source` | str | `"seed"` |

---

## 7. Backend Module Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI init, CORS, lifespan (Telegram poller task)
│   ├── database.py          # SQLAlchemy engine, session, create_all()
│   ├── models.py            # ORM: 6 tables
│   ├── schemas.py           # Pydantic request/response models
│   ├── seed.py              # Idempotent seed: contacts (with emails), messages, car_state, settings
│   ├── routers/
│   │   ├── messages.py      # F1: ingest, inject, CRUD, mic-reply upload
│   │   ├── calendar.py      # F3: Google OAuth + events
│   │   ├── car.py           # Simulator state CRUD + cabin cool
│   │   ├── navigation.py    # TomTom proxy: geocode + route only
│   │   ├── automations.py   # F2 + F3 orchestration
│   │   ├── assistant.py     # Voice NLU + Gemini function dispatch
│   │   └── contacts.py      # Contact management
│   └── services/
│       ├── telegram.py      # Long-poll loop, ingest_update(), send_voice(), send_message()
│       ├── gemini.py        # Classify, summarize, draft, function-calling
│       ├── tomtom.py        # Geocode + route (no traffic, no maneuvers)
│       ├── google_cal.py    # OAuth token management + Calendar.Events.list()
│       └── eta.py           # get_resolved_eta() — single source of truth
├── audio_replies/           # WebM/Opus voice blobs (git-ignored)
│   └── .gitkeep
├── calendar_token.json      # OAuth token (git-ignored, in .gitignore)
└── tests/
    ├── test_messages.py     # Ingest, inject, classify, silence, state machine
    ├── test_reply.py        # Mic upload, Telegram send_voice, send_failed path
    ├── test_automations.py  # Late-check: is-late, not-late, attendee matching, text send
    ├── test_navigation.py   # Geocode + route + car_state mutation + 502 path
    └── test_eta.py          # get_resolved_eta() simulator and tomtom branches
```

---

## 8. Key Backend Rules

### 8.1 Singleton Enforcement
`car_state` and `settings` use `id=1`. Seed: `INSERT OR REPLACE`. All GETs: `WHERE id=1`.
All PUTs: `UPDATE WHERE id=1`. `id` never appears in request bodies.

### 8.2 ETA — Single Source of Truth
`get_resolved_eta(car_state)` in `services/eta.py` only. No inline `if/else` in routers or automations.

### 8.3 Gemini Failure Isolation
All Gemini calls in `try/except`. On failure: `priority="normal"`, `summary=null`, request returns 200.
Draft failure: `suggested_reply=null`. Function-call failure: `spoken_text="Sorry, I couldn't process that."`, `action=null`.

### 8.4 Telegram Failure Handling
- `send_voice` failure → `status="send_failed"`, delete saved audio file, log error, return 200 to client (don't bubble 500).
- `send_message` (F2 text) failure → log error, mark that attendee as `"status":"failed"` in payload, continue to next attendee.
- Poller connectivity loss → `asyncio.sleep(5)` backoff, resume automatically.

### 8.5 TomTom Failure Handling
`/nav/route` failure → `502`. `car_state` NOT mutated. `eta_source` NOT changed.

### 8.6 Audio Reply File Lifecycle
1. `POST /api/messages/{id}/reply` receives blob.
2. Validate content-type header is `audio/webm` or `audio/ogg`. Reject anything else with `422`.
3. Save to `backend/audio_replies/<message_id>.webm` (use `message_id` as filename — 1:1, no separate table).
4. Call `telegram.send_voice(contact.tg_chat_id, blob_bytes)`.
5. Success: update `messages` (`status="replied"`, `audio_path`, `audio_format`, `sent_reply_text`, `replied_at`). Log `automation_log` row type `"voice_reply"`.
6. Failure: delete saved file; set `messages.status="send_failed"`. Log `automation_log` row with `status="error"`.

### 8.7 F2 Attendee Matching
```python
import json
attendees = json.loads(event.attendees)   # [{"email":"...","name":"...","responseStatus":"..."}]
accepted  = [a for a in attendees if a.get("responseStatus") in ("accepted", "needsAction")]
contacts  = [db.query(Contact).filter_by(email=a["email"]).first() for a in accepted]
contacts  = [c for c in contacts if c is not None]
# Send text to each contact that has a tg_chat_id
# Skip (log as "skipped") contacts where tg_chat_id is null
```

### 8.8 Google Calendar Token Storage
Token stored in `backend/calendar_token.json`. On startup, if file exists, load it. If access
token is expired, `google-auth-library` refreshes it automatically using the stored refresh token.
If file does not exist, `GET /api/calendar/events` returns `{"data":[],"warning":"Calendar not authorised — visit /api/calendar/auth"}`.

### 8.9 Concurrency & Transaction Discipline
- The Telegram poller task and HTTP handlers share one engine with WAL + `busy_timeout` (§3.0.1).
- **Never** hold a DB transaction open across an `await` to Gemini/Telegram/TomTom. Pattern:
  (1) read what you need, commit/close; (2) `await` the external call; (3) open a fresh short
  transaction to persist the result.
- The reply endpoint guards against double-submit by re-reading `status` **inside** the write
  transaction: if already `replied`, raise `409 INVALID_TRANSITION` before saving the file or
  calling Telegram. This makes a double-tap idempotent (first wins, second 409s).
- Each request handler uses one `Session` via FastAPI dependency; the poller opens its own
  `Session` per update and closes it promptly.

### 8.10 Idempotency Summary
| Operation | Idempotency mechanism |
|---|---|
| Inbound Telegram message | `UNIQUE(tg_update_id)` + `INSERT OR IGNORE` |
| Reply send | status guard (`summarized`/`silenced`/`send_failed` → `replied` only once) |
| Cabin cool | If `climate_on` already true, no-op returns 200; log row only on actual change |
| `/nav/route` | Pure overwrite of `car_state` nav fields — safe to repeat |
| Late check | Always writes exactly one log row per call; sends are best-effort per attendee |

### 8.11 Startup Sequence (deterministic boot)
1. Create engine, attach PRAGMA listener (§3.0.1).
2. `Base.metadata.create_all()` — idempotent table creation.
3. `seed()` — only inserts if a table is empty (checks `contacts` count, `car_state` id=1, etc.).
4. Load `calendar_token.json` if present.
5. Launch Telegram poller as a lifespan background task.
6. Mark `/health` ready.

---

## 9. Seed Data

### 9.1 Contacts

| Name | tg_chat_id | email | org | relationship |
|---|---|---|---|---|
| Dato Razif (Boss) | 987654321 | razif@mbm.com | MBM Executive | boss |
| Sarah (Wife) | 987654322 | sarah@family.com | Family | family |
| Amir (Friend) | 987654323 | amir@personal.com | Personal | friend |
| Acme Marketing | null | marketing@acme.com | Acme Corp | marketing |
| James Tan (Colleague) | 987654325 | james@acme.com | Acme Corp Ops | colleague |

> `tg_chat_id` values are fake seeds. Real IDs are set automatically when each person messages the bot.

### 9.2 Messages (Seed Inbox)

| From | Body | Expected priority | Expected status |
|---|---|---|---|
| Dato Razif | "The board meeting has moved to 10 AM, please confirm." | high | unread |
| Sarah | "Can you pick up Mia from school at 3?" | normal | unread |
| Acme Marketing | "Exclusive offer: 50% off premium services this week!" | low | silenced |

### 9.3 `car_state` Seed Row

```
location_name="KL Sentral"  current_lat=3.1319  current_lng=101.6841
destination_name=null  route_polyline=null  route_eta_minutes=null
eta_source="simulator"  eta_minutes=20
cabin_temp_c=28.0  target_temp_c=22.0  climate_on=false
```

### 9.4 `settings` Seed Row

```
target_cabin_temp_c=22.0  late_threshold_min=15  precool_lead_min=10  quiet_contact_ids=[]
```

---

## 10. Testing Contracts

### 10.1 Unit Tests (PyTest — mocked Gemini, TomTom, Telegram)

| Test | Assertion |
|---|---|
| Ingest new contact message | Contact upserted, message `status="unread"` |
| Ingest duplicate `tg_update_id` | `INSERT OR IGNORE` — no duplicate row, no error |
| Ingest group chat message | Message NOT created (dropped silently) |
| Ingest marketing contact | `priority="low"`, `status="silenced"` |
| `POST /messages/{id}/reply` — valid WebM upload | File saved, `status="replied"`, Telegram `send_voice` called |
| `POST /messages/{id}/reply` — Telegram send fails | `status="send_failed"`, file deleted, no 500 |
| `POST /messages/{id}/reply` — invalid content-type | Returns 422 |
| `POST /messages/{id}/silence` — already replied | Returns 409 |
| `get_resolved_eta` — `eta_source=simulator` | Returns `eta_minutes` |
| `get_resolved_eta` — `eta_source=tomtom` | Returns `route_eta_minutes` |
| `POST /automations/run-late-check` — 20 min late | `is_late=True`, attendees notified, log `status="ok"` |
| `POST /automations/run-late-check` — 10 min late (below 15 threshold) | `is_late=False`, log `status="skipped"` |
| `POST /automations/run-late-check` — attendee with no `tg_chat_id` | Skipped in `message_sent_to`, no crash |
| `GET /automations/next-departure` | `leave_by = event.start − resolved_eta − 5 min` |
| `POST /car/cabin/cool` | `climate_on=true`, `automation_log` row `type="cabin_precool"` |
| `POST /nav/route` — mocked TomTom success | `car_state` updated: `route_polyline`, `route_eta_minutes`, `eta_source="tomtom"` |
| `POST /nav/route` — TomTom 502 | Returns 502, `car_state` NOT mutated |

### 10.2 Playwright E2E Flows

| Flow | Steps | Assertions |
|---|---|---|
| F1 — Ingest + mic reply | Inject message via simulator → card appears → driver clicks Reply → mic records → send → | `status="replied"`, `audio_path` set, Telegram `send_voice` stub called, log entry |
| F2 — Late (simulator) | Set `eta_minutes=35`, next event in 20 min → trigger late-check | `is_late=true`, attendees listed, Telegram `sendMessage` stub called |
| F2 — Late (TomTom) | Geocode + route → `eta_source="tomtom"` → trigger late-check | `route_eta_minutes` used, same assertions |
| F3 — Cabin pre-cool | Next event 12 min away → departure card shows → cool cabin → | `climate_on=true`, log row present |
| Google Calendar auth | Visit `/api/calendar/auth` → OAuth flow → callback → `GET /api/calendar/events` returns live events | `source="live"`, events in DB |

---

## 11. Stretch Features

- **Meeting briefing:** `POST /api/ai/briefing` — combines next event + related messages + attendee names → spoken briefing via TTS.
- **Smart reply suggestion edit:** Driver edits Gemini suggested text in a text field before recording, so the mic capture reflects their edits.
- **"Who is this?" prompt:** For unknown contacts, dashboard shows "Tag this contact" → `PATCH /api/contacts/{id}` → `rel_source="user_tagged"`.

---

## 12. Role Mapping

| Member | Primary Areas | Key Responsibilities |
|---|---|---|
| Rhianne | AI / general | `services/gemini.py`: classify, summarize, draft apology, NLU function-calling; relationship inference; `routers/assistant.py` |
| Jia Tong | AI / frontend | Web Speech STT/TTS; mic `getUserMedia` + `MediaRecorder` reply flow; assistant card UI; voice command wiring |
| May | Frontend + BE | MBUX dashboard (Messages card, reply modal, Next Trip card, Map card, Simulator panel); TomTom Maps SDK component; `routers/messages.py` reply endpoint |
| Marcus | Backend / infra | DB schema + seed; `services/telegram.py` (poller + send_voice + send_message); Google Calendar OAuth + token storage; `routers/car.py`; `routers/navigation.py`; `routers/automations.py`; F2 attendee-matching logic |

**Day-one agreement:** Schema + API contracts (§3 + §6) locked before parallel work begins.
Marcus starts the Telegram bot and confirms message ingestion live before P1 begins.

---

## 13. Build Phases

| Phase | Days | Scope | Owner |
|---|---|---|---|
| P0 | 1 | Telegram bot created + polling confirmed; schema + seed; Car Simulator panel; Gemini stub; `audio_replies/` directory | Marcus + all |
| P1 | 1–2 | F1 — ingest pipeline, inject fallback, classify+summarize, mic recording + upload, `send_voice` | May (FE reply modal) + May (BE reply endpoint) + Marcus (telegram service) |
| P2 | 2–3 | Google Calendar OAuth + live events + SQLite cache; F3 departure card + `precool` | Marcus + May (FE next-trip card) |
| P3 | 3–4 | F2 — late-check logic, attendee matching, Telegram `send_message`; nav geocode + route (ETA for F2) | Marcus + Rhianne (Gemini apology draft) |
| P4 | 4–5 | Map card (TomTom SDK polyline render); voice STT/TTS; assistant command routing | May (FE map) + Jia Tong + Rhianne |
| P5 | 5–6 | Integration testing, demo script rehearsal, polish, buffer for breakage | All |
| P6 | 6 (if time) | Stretch: briefing, contact tagging, reply text edit | All |

---

## 14. Environment Variables

| Variable | Where | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Backend env / GitHub Secret | From @BotFather (§0 Step 1) |
| `TELEGRAM_DEMO_CHAT_ID` | Backend env | Driver's Telegram user ID (§0 Step 2) |
| `TOMTOM_API_KEY` | Backend env / GitHub Secret | Never sent to browser |
| `GOOGLE_CLIENT_ID` | Backend env | OAuth 2.0 client (Calendar read scope) |
| `GOOGLE_CLIENT_SECRET` | Backend env | |
| `GOOGLE_REDIRECT_URI` | Backend env | `http://localhost:8000/api/calendar/callback` |
| `GEMINI_API_KEY` | Backend env | |
| `VITE_API_BASE_URL` | Frontend `.env` | `http://localhost:8000` |
| `VITE_TOMTOM_API_KEY` | Frontend `.env` | Maps SDK browser key (separate read-only key, not the server key) |

---

## 15. Verification Checklist

- Telegram bot live: `/start` sent → poller logs the update → `GET /api/messages` shows it.
- Mic reply: browser grants mic → record 3 s → send → Telegram chat shows a voice note bubble.
- Google Calendar: `GET /api/calendar/auth` → OAuth flow completes → `GET /api/calendar/events` returns `source="live"`.
- TomTom route: `POST /api/nav/route` with KL Sentral → Menara Mercedes → `car_state.route_eta_minutes` set → map renders polyline.
- F2 late-check (simulator): set `eta_minutes=35`, event starts in 20 min → `POST /run-late-check` → `is_late=true` → attendees receive Telegram text.
- F2 late-check (TomTom): route computed → `eta_source="tomtom"` → same result.
- F3 cabin cool: `POST /car/cabin/cool` → `climate_on=true` → dashboard updates.
- `pytest` → all unit tests green (Telegram + Gemini + TomTom mocked).
- `npm run build` → no TypeScript errors.
- **Manual demo script:** Send Telegram DM to bot → card appears on dashboard → Gemini summary shown → driver taps Reply → records voice → voice note delivered in Telegram → set ETA 35 min, event in 20 min → tap "Am I late?" → attendees receive apology text in Telegram → next event shown → cabin cool triggered → map shows route polyline + ETA.

---

## 16. Definition of Done (acceptance gate)

The PoC is demo-ready when **all** of the following hold. Each maps to the per-feature criteria in §4.

| Gate | Source | Pass condition |
|---|---|---|
| Data integrity | §3.0 / §3.8 | FK pragma on; all 8 invariants (I1–I8) hold under the test suite |
| Status machine | §3.2.1 | Every disallowed transition returns 409; allowed ones succeed |
| Typed contracts | §6.0 | Every endpoint validates via its Pydantic model; bad bodies → 422 |
| Error catalog | §6.0.2 | Each listed `code` is reachable and returns its stated HTTP status |
| F1 | §4 F1-1…F1-10 | All 10 criteria pass |
| F2 | §4 F2-1…F2-8 | All 8 criteria pass |
| F3 | §4 F3-1…F3-7 | All 7 criteria pass |
| Navigation | §4 N-1…N-4 | All 4 criteria pass |
| Resilience | §8.3–8.5 | Gemini/Telegram/TomTom outages degrade gracefully, never 500 the dashboard |
| Test suite | §10 | `pytest` green; the E2E flows pass with externals mocked |

**One-line gate:** *foolproof data (§3) + typed APIs (§6.0) + every feature's "Done when" table (§4) green = ship.*

