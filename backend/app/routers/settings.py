import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Settings
from ..schemas import SettingsOut, SettingsPatch

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _get_or_create_settings(db: Session) -> Settings:
    settings = db.query(Settings).filter(Settings.id == 1).first()
    if settings is None:
        settings = Settings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _settings_to_out(settings: Settings) -> SettingsOut:
    return SettingsOut(
        id=settings.id,
        target_cabin_temp_c=settings.target_cabin_temp_c,
        late_threshold_min=settings.late_threshold_min,
        precool_lead_min=settings.precool_lead_min,
        quiet_contact_ids=settings.quiet_contact_ids or "[]",
        voice_reply_enabled=bool(settings.voice_reply_enabled),
    )


@router.get("/", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    settings = _get_or_create_settings(db)
    return _settings_to_out(settings)


@router.patch("/", response_model=SettingsOut)
def patch_settings(patch: SettingsPatch, db: Session = Depends(get_db)):
    settings = _get_or_create_settings(db)
    update_data = patch.model_dump(exclude_unset=True)
    update_data.pop("id", None)

    for field, value in update_data.items():
        if field == "voice_reply_enabled":
            setattr(settings, field, 1 if value else 0)
        else:
            setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return _settings_to_out(settings)
