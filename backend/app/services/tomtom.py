import os
from urllib.parse import quote

import httpx
from fastapi import HTTPException

TOMTOM_BASE = "https://api.tomtom.com"
_TOMTOM_ERROR_HEADERS = {"X-Error-Code": "UPSTREAM_TOMTOM"}


def _api_key() -> str:
    return os.environ.get("TOMTOM_API_KEY", "")


async def geocode(query: str) -> dict:
    encoded = quote(query, safe="")
    url = f"{TOMTOM_BASE}/search/2/geocode/{encoded}.json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"key": _api_key()})
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results", [])
        if not results:
            raise HTTPException(502, detail="Geocode failed", headers=_TOMTOM_ERROR_HEADERS)
        first = results[0]
        position = first["position"]
        label = first.get("address", {}).get("freeformAddress", query)
        return {"lat": position["lat"], "lng": position["lon"], "label": label}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, detail="Geocode failed", headers=_TOMTOM_ERROR_HEADERS)


async def get_route(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> dict:
    url = (
        f"{TOMTOM_BASE}/routing/1/calculateRoute/"
        f"{origin_lat},{origin_lng}:{dest_lat},{dest_lng}/json"
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params={"key": _api_key(), "instructionsType": "none"})
            resp.raise_for_status()
            data = resp.json()
        routes = data.get("routes", [])
        if not routes:
            raise HTTPException(502, detail="Route failed", headers=_TOMTOM_ERROR_HEADERS)
        summary = routes[0]["summary"]
        eta_minutes = summary["travelTimeInSeconds"] // 60
        distance_km = summary["lengthInMeters"] / 1000.0
        points = routes[0]["legs"][0]["points"]
        polyline = [[p["latitude"], p["longitude"]] for p in points]
        return {"eta_minutes": eta_minutes, "polyline": polyline, "distance_km": distance_km}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, detail="Route failed", headers=_TOMTOM_ERROR_HEADERS)
