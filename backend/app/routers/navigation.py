import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CarState
from ..schemas import GeocodeOut, GeocodeRequest, RouteRequest, RouteResultOut
from ..services.tomtom import geocode, get_route

router = APIRouter(prefix="/api/nav", tags=["navigation"])


@router.post("/geocode", response_model=GeocodeOut)
async def geocode_query(query: GeocodeRequest):
    result = await geocode(query.query)
    return GeocodeOut(
        lat=result["lat"],
        lng=result["lng"],
        display_name=result.get("label", ""),
    )


@router.post("/route", response_model=RouteResultOut)
async def compute_route(req: RouteRequest, db: Session = Depends(get_db)):
    result = await get_route(req.origin_lat, req.origin_lng, req.destination_lat, req.destination_lng)

    car = db.query(CarState).filter(CarState.id == 1).first()
    if car is None:
        car = CarState(id=1)
        db.add(car)

    car.destination_lat = req.destination_lat
    car.destination_lng = req.destination_lng
    car.route_polyline = json.dumps(result["polyline"])
    car.route_eta_minutes = result["eta_minutes"]
    car.eta_source = "tomtom"
    car.destination_name = result.get("destination_name", "")
    db.commit()

    return RouteResultOut(
        eta_minutes=result["eta_minutes"],
        eta_source="tomtom",
        route_polyline=json.dumps(result["polyline"]),
    )
