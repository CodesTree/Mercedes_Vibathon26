from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Contact
from ..schemas import ContactOut, ContactPatch

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("/", response_model=list[ContactOut])
def list_contacts(db: Session = Depends(get_db)):
    return db.query(Contact).order_by(Contact.id).all()


@router.patch("/{id}", response_model=ContactOut)
def patch_contact(id: int, patch: ContactPatch, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == id).first()
    if contact is None:
        raise HTTPException(status_code=404, detail=f"Contact {id} not found")

    update_data = patch.model_dump(exclude_unset=True)
    update_data.pop("id", None)

    if "relationship" in update_data or "org" in update_data:
        update_data["rel_source"] = "user_tagged"

    for field, value in update_data.items():
        setattr(contact, field, value)

    db.commit()
    db.refresh(contact)
    return contact
