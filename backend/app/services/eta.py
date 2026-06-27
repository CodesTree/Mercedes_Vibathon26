from ..models import CarState
from ..enums import EtaSource


def get_resolved_eta(car: CarState) -> int | None:
    """Single source of truth for ETA resolution. Never call inline if/else — always use this."""
    if car.eta_source == EtaSource.SIMULATOR:
        return car.eta_minutes
    return car.route_eta_minutes   # None if no TomTom route computed yet
