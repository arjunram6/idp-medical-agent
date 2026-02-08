"""
Intelligent synthesis: combine unstructured extracted insights with structured
facility/schema to provide a comprehensive view of regional capabilities.
"""

from collections import defaultdict
from typing import Any


def synthesize_regional_capabilities(
    extracted_medical: list[dict],
    facilities: list[dict],
    schema_context: str = "",
) -> dict[str, Any]:
    """
    Build a regional view: by region, what procedures/equipment/capabilities exist.
    Uses extracted_medical (unstructured) + facility metadata (structured).
    """
    by_region: dict[str, dict[str, Any]] = defaultdict(lambda: {"facilities": [], "procedures": set(), "equipment": set(), "capabilities": set()})
    all_procedures = set()
    all_equipment = set()
    all_capabilities = set()

    for e in extracted_medical:
        region = (e.get("region") or "").strip() or "Unknown"
        by_region[region]["facilities"].append(e.get("name", "Unknown"))
        for p in e.get("procedures", []):
            by_region[region]["procedures"].add(p)
            all_procedures.add(p)
        for q in e.get("equipment", []):
            by_region[region]["equipment"].add(q)
            all_equipment.add(q)
        for c in e.get("capabilities", []):
            by_region[region]["capabilities"].add(c)
            all_capabilities.add(c)

    # Also fold in facility names from facilities that might not be in extracted_medical
    seen_names = {e.get("name") for e in extracted_medical}
    for f in facilities:
        name = f.get("name", "Unknown")
        if name in seen_names:
            continue
        meta = f.get("metadata") or {}
        region = (meta.get("region") or meta.get("address_city") or "").strip() or "Unknown"
        by_region[region]["facilities"].append(name)

    # Convert sets to sorted lists for JSON-friendly output
    summary = {
        "by_region": {},
        "all_procedures": sorted(all_procedures),
        "all_equipment": sorted(all_equipment),
        "all_capabilities": sorted(all_capabilities),
        "schema_used": bool(schema_context),
    }
    for region, data in by_region.items():
        summary["by_region"][region] = {
            "facilities": list(dict.fromkeys(data["facilities"])),
            "procedures": sorted(data["procedures"]),
            "equipment": sorted(data["equipment"]),
            "capabilities": sorted(data["capabilities"]),
        }
    return summary
