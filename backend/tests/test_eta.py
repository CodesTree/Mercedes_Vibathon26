def test_get_resolved_eta_simulator():
    """eta_source=simulator returns eta_minutes."""
    from app.services.eta import get_resolved_eta
    from app.models import CarState
    car = CarState(eta_source="simulator", eta_minutes=20, route_eta_minutes=None)
    assert get_resolved_eta(car) == 20


def test_get_resolved_eta_tomtom():
    """eta_source=tomtom returns route_eta_minutes."""
    from app.services.eta import get_resolved_eta
    from app.models import CarState
    car = CarState(eta_source="tomtom", eta_minutes=20, route_eta_minutes=35)
    assert get_resolved_eta(car) == 35


def test_get_resolved_eta_tomtom_no_route():
    """eta_source=tomtom with no route computed returns None."""
    from app.services.eta import get_resolved_eta
    from app.models import CarState
    car = CarState(eta_source="tomtom", eta_minutes=20, route_eta_minutes=None)
    assert get_resolved_eta(car) is None
