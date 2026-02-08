"""
Risk Rating System for facilities (0–100 scale).
Rewards completeness (specialties, capability, location); penalizes critical gaps
(contact, facility type, clinical details); handles missing data gracefully.

Risk bands: 0–30 High (Red), 31–60 Medium (Yellow), 61–100 Low (Green).
Tier A/B/C/D from combinations of critical vs moderate missing fields.
"""

from dataclasses import dataclass
from typing import Any

# --- Helpers: "is this field present?" (non-empty, not null/[]) ---


def _present(row: dict, *keys: str) -> bool:
    v = ""
    for k in keys:
        v = (row.get(k) or "").strip()
        if v and str(v).lower() not in ("null", "[]", ""):
            return True
    return False


# Critical indicators (higher weight) — missing = more risk
def _has_contact(row: dict) -> bool:
    return _present(row, "phone_numbers", "email", "websites")


def _has_facility_type(row: dict) -> bool:
    return _present(row, "facilityTypeId")


def _has_specialties(row: dict) -> bool:
    return _present(row, "specialties")


def _has_location(row: dict) -> bool:
    return _present(row, "address_line1", "address_city", "address_stateOrRegion")


# Moderate indicators (medium weight)
def _has_capability(row: dict) -> bool:
    return _present(row, "capability")


def _has_operator_type(row: dict) -> bool:
    return _present(row, "organization_type")


def _has_procedures_or_equipment(row: dict) -> bool:
    return _present(row, "procedure", "equipment")


def _has_complete_address(row: dict) -> bool:
    has_region = _present(row, "address_stateOrRegion")
    has_line_or_city = _present(row, "address_line1", "address_city")
    return bool(has_region and has_line_or_city)


# Low indicators (lower weight)
def _has_description(row: dict) -> bool:
    return _present(row, "description")


_SOCIAL_KEYS = ("social_media", "facebook", "twitter", "instagram", "linkedin")


def _has_social_media(row: dict) -> bool:
    # Don't penalize if dataset has no social columns
    if not any(k in row for k in _SOCIAL_KEYS):
        return True
    return _present(row, *_SOCIAL_KEYS)


def _has_capacity(row: dict) -> bool:
    return _present(row, "capacity")


# --- Weights (points deducted when missing) ---
CRITICAL_WEIGHT = 12   # per critical gap (4 items → 48 max)
MODERATE_WEIGHT = 8    # per moderate gap (4 items → 32 max)
LOW_WEIGHT_DESC = 4
LOW_WEIGHT_SOCIAL = 4
LOW_WEIGHT_CAPACITY = 2   # 97%+ missing — don't over-penalize

CRITICAL_CHECKS = [
    ("contact", _has_contact),
    ("facility_type", _has_facility_type),
    ("specialties", _has_specialties),
    ("location", _has_location),
]
MODERATE_CHECKS = [
    ("capability", _has_capability),
    ("operator_type", _has_operator_type),
    ("procedures_equipment", _has_procedures_or_equipment),
    ("complete_address", _has_complete_address),
]
LOW_CHECKS = [
    ("description", _has_description),
    ("social_media", _has_social_media),
    ("capacity", _has_capacity),
]

# Fields used for data completeness (% present)
COMPLETENESS_FIELDS = [
    "name", "description", "capability", "procedure", "equipment", "specialties",
    "address_line1", "address_city", "address_stateOrRegion", "address_country",
    "phone_numbers", "email", "websites", "facilityTypeId", "organization_type",
    "capacity",
]


@dataclass
class RiskResult:
    """Per-facility risk and completeness."""
    risk_score: int          # 0–100 (100 = best documented, low risk)
    completeness_score: int # 0–100 (% of COMPLETENESS_FIELDS present)
    risk_band: str           # "High" | "Medium" | "Low"
    risk_color: str          # "Red" | "Yellow" | "Green"
    tier: str                # "A" | "B" | "C" | "D"
    critical_missing: list[str]
    moderate_missing: list[str]
    low_missing: list[str]


def _risk_band(score: int) -> tuple[str, str]:
    if score <= 30:
        return "High", "Red"
    if score <= 60:
        return "Medium", "Yellow"
    return "Low", "Green"


def _tier(critical_missing: list[str], moderate_missing: list[str], risk_score: int) -> str:
    c = len(critical_missing)
    m = len(moderate_missing)
    if c >= 3:
        return "D"
    if c == 2:
        return "C"
    if c == 1:
        return "C" if m >= 2 else "B"
    # c == 0
    if m >= 2:
        return "B"
    if m == 1:
        return "A"
    return "A"


def compute_risk(row: dict) -> RiskResult:
    """
    Compute risk score (0–100), data completeness (0–100), band (High/Medium/Low),
    color (Red/Yellow/Green), and tier (A/B/C/D) for one facility row.
    """
    critical_missing = [name for name, fn in CRITICAL_CHECKS if not fn(row)]
    moderate_missing = [name for name, fn in MODERATE_CHECKS if not fn(row)]
    low_missing = [name for name, fn in LOW_CHECKS if not fn(row)]

    deduction = (
        len(critical_missing) * CRITICAL_WEIGHT
        + len(moderate_missing) * MODERATE_WEIGHT
        + (LOW_WEIGHT_DESC if "description" in low_missing else 0)
        + (LOW_WEIGHT_SOCIAL if "social_media" in low_missing else 0)
        + (LOW_WEIGHT_CAPACITY if "capacity" in low_missing else 0)
    )
    risk_score = max(0, min(100, 100 - deduction))

    present_count = sum(
        1 for col in COMPLETENESS_FIELDS
        if _present(row, col)
    )
    completeness_score = round(100 * present_count / len(COMPLETENESS_FIELDS)) if COMPLETENESS_FIELDS else 0

    band, color = _risk_band(risk_score)
    tier = _tier(critical_missing, moderate_missing, risk_score)

    return RiskResult(
        risk_score=risk_score,
        completeness_score=completeness_score,
        risk_band=band,
        risk_color=color,
        tier=tier,
        critical_missing=critical_missing,
        moderate_missing=moderate_missing,
        low_missing=low_missing,
    )


def compute_risk_all(rows: list[dict]) -> list[tuple[dict, RiskResult]]:
    """Return (row, RiskResult) for each row."""
    return [(row, compute_risk(row)) for row in rows]


def risk_summary(rows: list[dict]) -> dict[str, Any]:
    """
    Aggregate summary: counts by band, tier, and average scores.
    """
    results = compute_risk_all(rows)
    by_band: dict[str, int] = {"High": 0, "Medium": 0, "Low": 0}
    by_tier: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}
    total_risk = 0
    total_completeness = 0
    n = len(results)
    for _row, r in results:
        by_band[r.risk_band] = by_band.get(r.risk_band, 0) + 1
        by_tier[r.tier] = by_tier.get(r.tier, 0) + 1
        total_risk += r.risk_score
        total_completeness += r.completeness_score
    return {
        "total_facilities": n,
        "by_risk_band": by_band,
        "by_tier": by_tier,
        "avg_risk_score": round(total_risk / n, 1) if n else 0,
        "avg_completeness_score": round(total_completeness / n, 1) if n else 0,
        "risk_bands": {"0-30": "High (Red)", "31-60": "Medium (Yellow)", "61-100": "Low (Green)"},
        "tiers": {"A": "Best documented", "B": "Some gaps", "C": "Notable gaps", "D": "Critical gaps"},
    }
