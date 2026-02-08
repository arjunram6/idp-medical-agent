"""
Geocode addresses using geocode.maps.co (Nominatim-compatible).
Used to add latitude/longitude to facility rows for distance queries.
"""

import json
import time
import urllib.parse
import urllib.request

from src.config import GEOCODE_API_KEY, GEOCODE_BASE_URL


def geocode_address(address: str, api_key: str | None = None) -> tuple[float, float] | None:
    """
    Geocode a single address. Returns (lat, lon) or None if not found or on error.
    """
    key = (api_key or "").strip() or GEOCODE_API_KEY
    if not key:
        return None
    q = address.strip()
    if not q:
        return None
    params = {"q": q, "api_key": key}
    url = f"{GEOCODE_BASE_URL}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read().decode()
    except Exception:
        return None
    try:
        results = json.loads(data)
        if not results or not isinstance(results, list):
            return None
        first = results[0]
        lat = first.get("lat")
        lon = first.get("lon")
        if lat is None or lon is None:
            return None
        return (float(lat), float(lon))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def build_address_from_row(row: dict) -> str:
    """Build a single-line address from CSV row for geocoding."""
    parts = []
    for key in ("address_line1", "address_line2", "address_line3", "address_city", "address_stateOrRegion"):
        v = (row.get(key) or "").strip()
        if v and v.lower() != "null":
            parts.append(v)
    if not any("ghana" in p.lower() for p in parts):
        parts.append("Ghana")
    return ", ".join(parts) if parts else ""


def geocode_with_rate_limit(address: str, api_key: str | None = None, delay_seconds: float = 1.0) -> tuple[float, float] | None:
    """
    Geocode and sleep to respect rate limits. Call this in a loop when batch geocoding.
    """
    result = geocode_address(address, api_key=api_key)
    time.sleep(delay_seconds)
    return result
