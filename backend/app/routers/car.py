import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..enums import AutoType, AutoStatus
from ..models import AutomationLog, CarState
from ..schemas import CarStateOut, CarStatePatch
from ..services.eta import get_resolved_eta

router = APIRouter(prefix="/api/car", tags=["car"])


def _get_or_create_car(db: Session) -> CarState:
    car = db.query(CarState).filter(CarState.id == 1).first()
    if car is None:
        car = CarState(id=1)
        db.add(car)
        db.commit()
        db.refresh(car)
    return car


def _car_to_out(car: CarState) -> CarStateOut:
    return CarStateOut(
        id=car.id,
        location_name=car.location_name,
        destination_name=car.destination_name,
        current_lat=car.current_lat,
        current_lng=car.current_lng,
        destination_lat=car.destination_lat,
        destination_lng=car.destination_lng,
        route_polyline=car.route_polyline,
        route_eta_minutes=car.route_eta_minutes,
        eta_source=car.eta_source,
        eta_minutes=car.eta_minutes,
        cabin_temp_c=car.cabin_temp_c,
        target_temp_c=car.target_temp_c,
        climate_on=car.climate_on,
        updated_at=car.updated_at,
    )


@router.get("/state", response_model=CarStateOut)
def get_car_state(db: Session = Depends(get_db)):
    car = _get_or_create_car(db)
    return _car_to_out(car)


@router.put("/state", response_model=CarStateOut)
def update_car_state(patch: CarStatePatch, db: Session = Depends(get_db)):
    car = _get_or_create_car(db)
    update_data = patch.model_dump(exclude_unset=True)
    update_data.pop("id", None)
    for field, value in update_data.items():
        setattr(car, field, value)
    db.commit()
    db.refresh(car)
    return _car_to_out(car)


@router.post("/cabin/cool", response_model=CarStateOut)
def cabin_cool(db: Session = Depends(get_db)):
    car = _get_or_create_car(db)
    if bool(car.climate_on):
        return _car_to_out(car)
    car.climate_on = 1
    db.commit()
    log = AutomationLog(
        type=AutoType.PRECOOL,
        trigger_at=datetime.now(timezone.utc).replace(tzinfo=None),
        payload=json.dumps({"action": "cabin_cool"}),
        status=AutoStatus.OK,
    )
    db.add(log)
    db.commit()
    db.refresh(car)
    return _car_to_out(car)
