from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------

class ContactOut(ORMModel):
    id: int
    name: str
    phone: str | None
    email: str | None
    tg_chat_id: int | None
    tg_username: str | None
    org: str | None
    relationship: str | None
    rel_source: str
    created_at: datetime
    updated_at: datetime


class ContactPatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    tg_chat_id: int | None = None
    tg_username: str | None = None
    org: str | None = None
    relationship: str | None = None
    rel_source: str | None = None


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class MessageOut(ORMModel):
    id: int
    contact_id: int
    contact_name: str
    tg_chat_id: int | None
    tg_update_id: int | None
    tg_message_id: int | None
    body: str
    received_at: datetime
    priority: str
    status: str
    summary: str | None
    suggested_reply: str | None
    reply_mode: str | None
    sent_reply_text: str | None
    replied_at: datetime | None
    audio_path: str | None
    audio_format: str | None

    @classmethod
    def from_orm_with_contact(cls, msg: Any) -> "MessageOut":
        return cls(
            id=msg.id,
            contact_id=msg.contact_id,
            contact_name=msg.contact.name,
            tg_chat_id=msg.contact.tg_chat_id,
            tg_update_id=msg.tg_update_id,
            tg_message_id=msg.tg_message_id,
            body=msg.body,
            received_at=msg.received_at,
            priority=msg.priority,
            status=msg.status,
            summary=msg.summary,
            suggested_reply=msg.suggested_reply,
            reply_mode=msg.reply_mode,
            sent_reply_text=msg.sent_reply_text,
            replied_at=msg.replied_at,
            audio_path=msg.audio_path,
            audio_format=msg.audio_format,
        )


class MessageListOut(BaseModel):
    messages: list[MessageOut]
    total: int


class InjectRequest(BaseModel):
    tg_chat_id: int
    body: str


class TextReplyRequest(BaseModel):
    transcript: str

    @field_validator("transcript")
    @classmethod
    def transcript_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("transcript must not be blank")
        return v


class VoiceReplyForm(BaseModel):
    audio_format: str = "webm_opus"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingsOut(ORMModel):
    id: int
    target_cabin_temp_c: float
    late_threshold_min: int
    precool_lead_min: int
    quiet_contact_ids: str
    voice_reply_enabled: int


class SettingsPatch(BaseModel):
    target_cabin_temp_c: float | None = None
    late_threshold_min: int | None = None
    precool_lead_min: int | None = None
    quiet_contact_ids: str | None = None
    voice_reply_enabled: int | None = None


# ---------------------------------------------------------------------------
# CarState
# ---------------------------------------------------------------------------

class CarStateOut(ORMModel):
    id: int
    location_name: str
    destination_name: str | None
    current_lat: float
    current_lng: float
    destination_lat: float | None
    destination_lng: float | None
    route_polyline: str | None
    route_eta_minutes: int | None
    eta_source: str
    eta_minutes: int
    cabin_temp_c: float
    target_temp_c: float
    climate_on: int
    updated_at: datetime


class CarStatePatch(BaseModel):
    location_name: str | None = None
    destination_name: str | None = None
    current_lat: float | None = None
    current_lng: float | None = None
    destination_lat: float | None = None
    destination_lng: float | None = None
    eta_source: str | None = None
    eta_minutes: int | None = None
    cabin_temp_c: float | None = None
    target_temp_c: float | None = None
    climate_on: int | None = None


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

class Attendee(BaseModel):
    email: str
    name: str | None = None


class CalendarEventOut(ORMModel):
    id: str
    title: str
    start: str
    end: str
    location: str | None
    organizer_email: str | None
    attendees: str
    cached_at: datetime


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

class GeocodeRequest(BaseModel):
    query: str


class GeocodeOut(BaseModel):
    lat: float
    lng: float
    display_name: str


class RouteRequest(BaseModel):
    origin_lat: float
    origin_lng: float
    destination_lat: float
    destination_lng: float


class RouteResultOut(BaseModel):
    eta_minutes: int
    eta_source: str
    route_polyline: str | None = None


# ---------------------------------------------------------------------------
# Automations
# ---------------------------------------------------------------------------

class NotifiedTarget(BaseModel):
    contact_id: int
    contact_name: str
    tg_chat_id: int
    message_sent: str


class NextDepartureOut(BaseModel):
    event_id: str | None
    event_title: str | None
    event_start: str | None
    leave_by: str | None
    precool_due: str | None
    precool_fired: bool
    mins_until_leave: int | None
    is_late: bool


class LateCheckResultOut(BaseModel):
    triggered: bool
    mins_late: int | None
    notified: list[NotifiedTarget]
    log_id: int | None
    status: str


class AutomationLogOut(ORMModel):
    id: int
    type: str
    trigger_at: datetime
    payload: str
    status: str
    error_msg: str | None


# ---------------------------------------------------------------------------
# Assistant
# ---------------------------------------------------------------------------

class AssistantCommand(BaseModel):
    command: str


class AssistantResultOut(BaseModel):
    response: str
    actions_taken: list[str] = []
