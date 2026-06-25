from sqlalchemy.orm import Session

from .models import Contact, Message, CarState, Settings


def seed(db: Session) -> None:
    # Only seed if contacts table is empty
    if db.query(Contact).count() > 0:
        return

    # --- Contacts ---
    contacts = [
        Contact(
            name="Dato Razif",
            tg_chat_id=987654321,
            email="razif@mbm.com",
            org="MBM Executive",
            relationship="boss",
            rel_source="seed",
        ),
        Contact(
            name="Sarah",
            tg_chat_id=987654322,
            email="sarah@family.com",
            org="Family",
            relationship="family",
            rel_source="seed",
        ),
        Contact(
            name="Amir",
            tg_chat_id=987654323,
            email="amir@personal.com",
            org="Personal",
            relationship="friend",
            rel_source="seed",
        ),
        Contact(
            name="Acme Marketing",
            tg_chat_id=None,
            email="marketing@acme.com",
            org="Acme Corp",
            relationship="marketing",
            rel_source="seed",
        ),
        Contact(
            name="James Tan",
            tg_chat_id=987654325,
            email="james@acme.com",
            org="Acme Corp Ops",
            relationship="colleague",
            rel_source="seed",
        ),
    ]
    db.add_all(contacts)
    db.flush()  # assign IDs before referencing them in messages

    # Build lookup by name
    contact_map = {c.name: c for c in contacts}

    # --- Messages ---
    messages = [
        Message(
            contact_id=contact_map["Dato Razif"].id,
            body="The board meeting has moved to 10 AM, please confirm.",
            priority="high",
            status="unread",
        ),
        Message(
            contact_id=contact_map["Sarah"].id,
            body="Can you pick up Mia from school at 3?",
            priority="normal",
            status="unread",
        ),
        Message(
            contact_id=contact_map["Acme Marketing"].id,
            body="Exclusive offer: 50% off premium services this week!",
            priority="low",
            status="silenced",
        ),
    ]
    db.add_all(messages)

    # --- CarState singleton ---
    if db.get(CarState, 1) is None:
        db.add(CarState(
            id=1,
            location_name="KL Sentral",
            current_lat=3.1319,
            current_lng=101.6841,
            eta_source="simulator",
            eta_minutes=20,
            cabin_temp_c=28.0,
            target_temp_c=22.0,
            climate_on=0,
        ))

    # --- Settings singleton ---
    if db.get(Settings, 1) is None:
        db.add(Settings(
            id=1,
            target_cabin_temp_c=22.0,
            late_threshold_min=15,
            precool_lead_min=10,
            quiet_contact_ids="[]",
            voice_reply_enabled=0,
        ))

    db.commit()
