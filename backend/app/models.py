from sqlalchemy import Column, Integer, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship as orm_relationship

from .database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    phone = Column(Text, unique=True, nullable=True)
    email = Column(Text, unique=True, nullable=True)
    tg_chat_id = Column(Integer, unique=True, nullable=True)
    tg_username = Column(Text, nullable=True)
    org = Column(Text, nullable=True)
    relationship = Column(Text, nullable=True)
    rel_source = Column(Text, nullable=False, default="unknown")
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    messages = orm_relationship("Message", back_populates="contact")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    tg_update_id = Column(Integer, unique=True, nullable=True)
    tg_message_id = Column(Integer, nullable=True)
    body = Column(Text, nullable=False)
    received_at = Column(DateTime, nullable=False, default=func.now())
    priority = Column(Text, nullable=False, default="normal")
    status = Column(Text, nullable=False, default="unread")
    summary = Column(Text, nullable=True)
    suggested_reply = Column(Text, nullable=True)
    reply_mode = Column(Text, nullable=True)
    sent_reply_text = Column(Text, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    audio_path = Column(Text, nullable=True)
    audio_format = Column(Text, nullable=True)

    contact = orm_relationship("Contact", back_populates="messages")


class CarState(Base):
    __tablename__ = "car_state"

    id = Column(Integer, primary_key=True, default=1)
    location_name = Column(Text, nullable=False, default="KL Sentral")
    destination_name = Column(Text, nullable=True)
    current_lat = Column(Float, nullable=False, default=3.1319)
    current_lng = Column(Float, nullable=False, default=101.6841)
    destination_lat = Column(Float, nullable=True)
    destination_lng = Column(Float, nullable=True)
    route_polyline = Column(Text, nullable=True)
    route_eta_minutes = Column(Integer, nullable=True)
    eta_source = Column(Text, nullable=False, default="simulator")
    eta_minutes = Column(Integer, nullable=False, default=20)
    cabin_temp_c = Column(Float, nullable=False, default=28.0)
    target_temp_c = Column(Float, nullable=False, default=22.0)
    climate_on = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    start = Column(Text, nullable=False)
    end = Column(Text, nullable=False)
    location = Column(Text, nullable=True)
    organizer_email = Column(Text, nullable=True)
    attendees = Column(Text, nullable=False, default="[]")
    cached_at = Column(DateTime, nullable=False, default=func.now())


class AutomationLog(Base):
    __tablename__ = "automation_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Text, nullable=False)
    trigger_at = Column(DateTime, nullable=False, default=func.now())
    payload = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="ok")
    error_msg = Column(Text, nullable=True)


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)
    target_cabin_temp_c = Column(Float, nullable=False, default=22.0)
    late_threshold_min = Column(Integer, nullable=False, default=15)
    precool_lead_min = Column(Integer, nullable=False, default=10)
    quiet_contact_ids = Column(Text, nullable=False, default="[]")
    voice_reply_enabled = Column(Integer, nullable=False, default=0)
