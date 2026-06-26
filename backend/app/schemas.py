from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    phone: str | None = None
    email: str | None = None
    tg_chat_id: int | None = None
    tg_username: str | None = None
    org: str | None = None
    relationship: str | None = None
    rel_source: str


class ContactPatch(BaseModel):
    relationship: str | None = None
    email: str | None = None
    org: str | None = Field(default=None, max_length=120)


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class MessageOut(ORMModel):
    id: int
    contact_id: int
    contact_name: str           # joined from contacts.name
    tg_chat_id: int | None = None  # joined from contacts.tg_chat_id
    body: str
    received_at: datetime
    priority: str
    status: str
    summary: str | None = None
    suggested_reply: str | None = None
    # reply fields
    reply_mode: str | None = None
    sent_reply_text: str | None = None
    replied_at: datetime | None = None
    # stretch-only voice fields
    audio_format: str | None = None
    # audio_path is intentionally NOT exposed (server-internal path)

    @classmethod
    def from_orm_with_contact(cls, msg: Any) -> "MessageOut":
        return cls(
            id=msg.id,
            contact_id=msg.contact_id,
            contact_name=msg.contact.name,
            tg_chat_id=msg.contact.tg_chat_id,
            body=msg.body,
            received_at=msg.received_at,
            priority=msg.priority,
            status=msg.status,
            summary=msg.summary,
            suggested_reply=msg.suggested_reply,
            reply_mode=msg.reply_mode,
            sent_reply_text=msg.sent_reply_text,
            replied_at=msg.replied_at,
            audio_format=msg.audio_format,
        )


class MessageListOut(BaseModel):
    items: list[MessageOut]
    count: int


class InjectRequest(BaseModel):
    tg_chat_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=120)
    body: str = Field(..., min_length=1, max_length=4096)
    received_at: datetime | None = None
    email: str | None = None


class TextReplyRequest(BaseModel):
    reply_mode: Literal["text"]
    transcript: str = Field(..., min_length=1, max_length=1000)

    @field_validator("transcript")
    @classmethod
    def transcript_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("transcript must not be whitespace-only")
        return v.strip()


class VoiceReplyForm(BaseModel):
    reply_mode: Literal["voice"]
    transcript: str = Field(..., min_length=1, max_length=1000)

    @field_validator("transcript")
    @classmethod
    def transcript_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("transcript must not be whitespace-only")
        return v.strip()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingsOut(BaseModel):
    target_cabin_temp_c: float
    late_threshold_min: int
    precool_lead_min: int
    quiet_contact_ids: list[int]
    voice_reply_enabled: bool


class SettingsPatch(BaseModel):
    target_cabin_temp_c: float | None = Field(default=None, ge=16.0, le=30.0)
    late_threshold_min: int | None = Field(default=None, ge=0, le=180)
    precool_lead_min: int | None = Field(default=None, ge=0, le=60)
    quiet_contact_ids: list[int] | None = None
    voice_reply_enabled: bool | None = None


# ---------------------------------------------------------------------------
# CarState
# ---------------------------------------------------------------------------

class CarStateOut(BaseModel):
    location_name: str
    destination_name: str | None = None
    current_lat: float
    current_lng: float
    destination_lat: float | None = None
    destination_lng: float | None = None
    route_polyline: str | None = None
    route_eta_minutes: int | None = None
    eta_source: str
    eta_minutes: int
    resolved_eta: int | None = None   # computed, injected by handler
    cabin_temp_c: float
    target_temp_c: float
    climate_on: bool
    updated_at: datetime


class CarStatePatch(BaseModel):
    location_name: str | None = Field(default=None, max_length=120)
    current_lat: float | None = Field(default=None, ge=-90, le=90)
    current_lng: float | None = Field(default=None, ge=-180, le=180)
    eta_source: str | None = None
    eta_minutes: int | None = Field(default=None, ge=0, le=600)
    cabin_temp_c: float | None = Field(default=None, ge=14.0, le=40.0)
    target_temp_c: float | None = Field(default=None, ge=16.0, le=30.0)


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

class Attendee(BaseModel):
    email: str
    name: str | None = None
    responseStatus: str | None = None


class CalendarEventOut(BaseModel):
    id: str
    title: str
    start: str
    end: str
    location: str | None = None
    organizer_email: str | None = None
    attendees: list[Attendee] = []
    cached_at: datetime
    source: str   # "live" | "cache", injected by handler


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Automations
# ---------------------------------------------------------------------------

class NotifiedTarget(BaseModel):
    name: str
    tg_chat_id: int | None = None
    status: str   # "sent" | "skipped" | "failed"


class NextDepartureOut(BaseModel):
    event: CalendarEventOut | None = None
    resolved_eta: int | None = None
    eta_source: str
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


class AutomationLogOut(BaseModel):
    id: int
    type: str
    trigger_at: datetime
    payload: dict   # parsed from JSON TEXT
    status: str
    error_msg: str | None = None


# ---------------------------------------------------------------------------
# Assistant
# ---------------------------------------------------------------------------

class AssistantCommand(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=300)


class AssistantResultOut(BaseModel):
    spoken_text: str
    action: str | None = None
    action_data: dict | None = None
