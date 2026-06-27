from unittest.mock import AsyncMock, patch


def test_route_updates_car_state(client, db_session):
    """POST /nav/route updates car_state with polyline, eta_minutes, eta_source=tomtom."""
    mock_result = {
        "eta_minutes": 25,
        "polyline": [[3.1319, 101.6841], [3.1500, 101.7000]],
        "distance_km": 5.2,
        "destination_name": "Menara Mercedes",
    }
    with patch("app.routers.navigation.get_route", new=AsyncMock(return_value=mock_result)):
        resp = client.post("/api/nav/route", json={
            "origin_lat": 3.1319, "origin_lng": 101.6841,
            "dest_lat": 3.15, "dest_lng": 101.7
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["eta_minutes"] == 25
    assert data["destination_name"] == "Menara Mercedes"
    from app.models import CarState
    car = db_session.get(CarState, 1)
    db_session.refresh(car)
    assert car.route_eta_minutes == 25
    assert car.eta_source == "tomtom"


def test_route_tomtom_502_does_not_mutate_car_state(client, db_session):
    """TomTom 502 → returns 502, car_state NOT mutated."""
    from fastapi import HTTPException
    from app.models import CarState
    original_eta = db_session.get(CarState, 1).route_eta_minutes
    with patch("app.routers.navigation.get_route", new=AsyncMock(side_effect=HTTPException(502, "TomTom error"))):
        resp = client.post("/api/nav/route", json={
            "origin_lat": 3.1319, "origin_lng": 101.6841,
            "dest_lat": 3.15, "dest_lng": 101.7
        })
    assert resp.status_code == 502
    car = db_session.get(CarState, 1)
    db_session.refresh(car)
    assert car.route_eta_minutes == original_eta
    assert car.eta_source == "simulator"
