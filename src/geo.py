"""
Geospatial helpers: non-standard (geodesic) distance and reference points for places.
Uses Haversine for geodesic distance in km; alias geodesic_distance_km for clarity.
"""

import math
import re
from typing import Callable

# Reference points (lat, lon) for "within X km of <place>" queries (fallback only)
PLACE_COORDS = {
    "accra": (5.6037, -0.1870),
    "kumasi": (6.6884, -1.6244),
    "tamale": (9.4039, -0.8430),
    "takoradi": (4.8845, -1.7554),
    "cape coast": (5.1053, -1.2466),
}

_place_cache: dict[str, tuple[float, float] | None] = {}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Geodesic distance in km between two (lat, lon) points (Haversine)."""
    R = 6371  # Earth radius km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# Alias for non-standard / geodesic distance
geodesic_distance_km = haversine_km


def get_place_coords(place: str) -> tuple[float, float] | None:
    """Return (lat, lon) for a place name using geocode API, fallback to static map."""
    key = (place or "").strip().lower()
    if not key:
        return None
    if key in _place_cache:
        return _place_cache[key]
    try:
        from src.geocode_maps import geocode_address
        query = place.strip()
        if "ghana" not in query.lower():
            query = f"{query}, Ghana"
        coords = geocode_address(query)
    except Exception:
        coords = None
    if coords is None:
        coords = PLACE_COORDS.get(key)
    _place_cache[key] = coords
    return coords


def get_row_coords(row: dict) -> tuple[float, float] | None:
    """
    Get (lat, lon) for a facility row. Prefers latitude/longitude columns;
    else parses capability/description for "latitude X longitude Y" or similar.
    """
    lat_s = (row.get("latitude") or row.get("lat") or "").strip()
    lon_s = (row.get("longitude") or row.get("lon") or "").strip()
    if lat_s and lon_s:
        try:
            return (float(lat_s), float(lon_s))
        except ValueError:
            pass
    text = " ".join(str(row.get(c, "")) for c in ("capability", "description"))
    # e.g. "Coordinates: latitude 8.85756, longitude -0.05562" or "5.63286 latitude and -0.24057 longitude"
    for pattern in [
        r"latitude\s+([-\d.]+)\s*[,]\s*longitude\s+([-\d.]+)",
        r"latitude\s+([-\d.]+).*?longitude\s+([-\d.]+)",
        r"([-\d.]+)\s*latitude\s+and\s+([-\d.]+)\s*longitude",
        r"([-\d.]+)\s+latitude\s+and\s+([-\d.]+)\s+longitude",
    ]:
        m = re.search(pattern, text, re.I)
        if m:
            try:
                return (float(m.group(1)), float(m.group(2)))
            except ValueError:
                continue
    return None


def filter_rows_within_km(
    rows: list[dict],
    ref_lat: float,
    ref_lon: float,
    radius_km: float,
    get_coords: Callable[[dict], tuple[float, float] | None] = get_row_coords,
) -> list[dict]:
    """Return rows that have coordinates and are within radius_km of (ref_lat, ref_lon)."""
    out = []
    for row in rows:
        coord = get_coords(row)
        if coord is None:
            continue
        dist = haversine_km(ref_lat, ref_lon, coord[0], coord[1])
        if dist <= radius_km:
            out.append(row)
    return out
