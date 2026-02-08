#!/usr/bin/env python3
"""
Query the Ghana data using only the data document and the Scheme — no OpenAI.
Uses the scheme to explain terminology in the answer.

Run: python3 query_local.py "How many hospitals have cardiology?"
     python3 query_local.py "Which facilities have dialysis?"
"""

import csv
import io
import re
import sys
from typing import Any
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import _find_geocoded_csv, _find_ghana_csv
from src.geo import filter_rows_within_km, get_place_coords, get_row_coords
from src.scheme_terms import explain_relevant_terms, SCHEME_TERMS

# In-memory cache so we don't re-read CSV every query (speeds up Genie Chat / repeated calls)
_csv_cache: dict[tuple[bool, str], tuple[str, list[dict]]] = {}


def load_csv(prefer_geocoded: bool = False):
    """Load Ghana CSV from data/ or Desktop. Uses in-memory cache when path unchanged."""
    global _csv_cache
    path = _find_geocoded_csv() if prefer_geocoded else _find_ghana_csv()
    if not path or not path.exists():
        path = _find_ghana_csv()
    if not path or not path.exists():
        return None, []
    cache_key = (prefer_geocoded, str(path))
    if cache_key in _csv_cache:
        return _csv_cache[cache_key]
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    result = (path.name, rows)
    _csv_cache[cache_key] = result
    return result


# Columns that count as "data points" for richness ranking (non-empty = 1 point)
DATA_RICHNESS_COLS = [
    "name", "description", "capability", "procedure", "equipment", "specialties",
    "address_line1", "address_line2", "address_city", "address_stateOrRegion", "address_country",
    "phone_numbers", "email", "websites", "facilityTypeId", "organization_type",
    "latitude", "longitude",
]

# Columns used for similarity (query-term overlap)
CONTENT_COLS = ["specialties", "procedure", "equipment", "capability", "description", "name"]


def _data_richness_score(row: dict) -> int:
    """Count of non-empty fields; used to rank rows so fullest show first."""
    n = 0
    for col in DATA_RICHNESS_COLS:
        v = (row.get(col) or "").strip()
        if v and v.lower() not in ("null", "[]", ""):
            n += 1
    return n


def _similarity_score(row: dict, query: str) -> int:
    """Lexical similarity: count of query-term occurrences in row content. Higher = more relevant."""
    if not query or not query.strip():
        return 0
    text = " ".join(str(row.get(c, "")) for c in CONTENT_COLS).lower()
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
    if not words:
        return 0
    return sum(text.count(w) for w in words)


def sort_rows_by_richness_then_similarity(rows: list[dict], query: str | None = None) -> list[dict]:
    """Sort by data richness (desc), then by similarity to query (desc). If no query, richness only."""
    if not query or not query.strip():
        return sorted(rows, key=_data_richness_score, reverse=True)
    return sorted(
        rows,
        key=lambda r: (_data_richness_score(r), _similarity_score(r, query)),
        reverse=True,
    )


def sort_rows_by_data_richness(rows: list[dict], query: str | None = None) -> list[dict]:
    """Sort by richness first, then by similarity to query when provided."""
    return sort_rows_by_richness_then_similarity(rows, query)


def search_rows(
    rows: list[dict],
    capability_keywords: list[str],
    facility_type: str | None = None,
    query: str | None = None,
) -> list[dict]:
    """
    Find rows where any of the capability_keywords appear in specialties, procedure, equipment, capability, or description.
    If facility_type is set (e.g. 'hospital'), filter to facilityTypeId == facility_type.
    Returns matches sorted by richness (most complete first), then by similarity to query.
    """
    content_cols = ["specialties", "procedure", "equipment", "capability", "description"]
    out = []
    kw_lower = [k.lower() for k in capability_keywords]
    for row in rows:
        if facility_type:
            ft = (row.get("facilityTypeId") or "").strip().lower()
            if ft != facility_type.lower():
                continue
        text = " ".join(str(row.get(c, "")) for c in content_cols).lower()
        if any(k in text for k in kw_lower):
            out.append(row)
    return sort_rows_by_richness_then_similarity(out, query)


EMPTY_LABEL = "N/A"


def _rank_facilities(rows: list[dict], limit: int = 5, prefer_hospitals: bool = False) -> tuple[list[tuple[dict, Any]], int]:
    """Return top facilities ranked by documentation quality (risk_score)."""
    if not rows:
        return [], 0
    filtered = rows
    if prefer_hospitals:
        hospitals = [r for r in rows if (r.get("facilityTypeId") or "").strip().lower() == "hospital"]
        filtered = hospitals or rows
    try:
        from src.risk_rating import compute_risk
    except Exception:
        return [], 0
    results = [(r, compute_risk(r)) for r in filtered]
    results.sort(key=lambda x: (-x[1].risk_score, (x[0].get("name") or "")))
    top = results[:limit]
    remaining = max(0, len(results) - len(top))
    return top, remaining


def _print_ranked_list(pr, rows: list[dict], label: str, limit: int = 5, prefer_hospitals: bool = False) -> None:
    """Print ranked facility list with Trust/Risk factors."""
    top, remaining = _rank_facilities(rows, limit=limit, prefer_hospitals=prefer_hospitals)
    if not top:
        pr("No facilities found.")
        return
    pr(label)
    for r, res in top:
        nm = (r.get("name") or "Unknown").strip()
        gaps = ", ".join(s.title() for s in res.critical_missing) or "None"
        pr(f"  - {nm} — Trust Factor: {res.tier} | Risk Factor: {res.risk_band} | Key gaps: {gaps}")
    if remaining > 0:
        pr(f"  ... and {remaining} more options.")


def find_facility_by_name(rows: list[dict], facility_name: str) -> dict | None:
    """Find first row where name contains facility_name (case-insensitive)."""
    name_lower = facility_name.lower().strip()
    for row in rows:
        n = (row.get("name") or "").lower()
        if name_lower in n or n in name_lower:
            return row
    # Token overlap
    tokens = set(re.findall(r"\w+", name_lower))
    for row in rows:
        n = (row.get("name") or "").lower()
        if len(tokens & set(re.findall(r"\w+", n))) >= 2:
            return row
    return None


def format_services(row: dict) -> str:
    """Format facility services; use N/A for empty fields."""
    def _parse_list_value(v: str) -> list[str] | None:
        raw = (v or "").strip()
        if not raw or raw in ("null", "[]"):
            return None
        if not (raw.startswith("[") and raw.endswith("]")):
            return None
        try:
            import json
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        try:
            import ast
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            return None
        return None

    def _val(key: str, max_len: int = 1200) -> str:
        v = (row.get(key) or "").strip()
        if not v or v in ("null", "[]"):
            return EMPTY_LABEL
        return v[:max_len] + ("..." if len(v) > max_len else "")

    def _pretty_field(key: str, max_len: int) -> str:
        v = (row.get(key) or "").strip()
        items = _parse_list_value(v)
        if items:
            return "\n".join(f"- {i}" for i in items)
        return _val(key, max_len)

    lines = [
        "**Description:** " + _val("description", 1500),
        "**Capabilities:**\n" + _pretty_field("capability", 800),
        "**Procedures:**\n" + _pretty_field("procedure", 800),
        "**Equipment:**\n" + _pretty_field("equipment", 600),
        "**Specialties:**\n" + _pretty_field("specialties", 500),
    ]
    return "\n".join(lines)


def parse_query(query: str) -> tuple[str | None, list[str]]:
    """
    Simple parse: "how many hospitals have X" -> (hospital, [x])
    "which facilities have X" -> (None, [x])
    "facilities with X" -> (None, [x])
    """
    q = query.lower().strip()
    facility_type = None
    if "hospital" in q:
        facility_type = "hospital"
    elif "clinic" in q:
        facility_type = "clinic"
    elif "pharmacy" in q:
        facility_type = "pharmacy"

    # Extract capability/specialty: "have cardiology" -> cardiology, "with dialysis" -> dialysis
    for pattern in [
        r"how many \w+ have (\w+(?:\s+\w+)?)",
        r"which \w+ have (\w+(?:\s+\w+)?)",
        r"facilities with (\w+(?:\s+\w+)?)",
        r"have (\w+(?:\s+\w+)?)",
        r"with (\w+(?:\s+\w+)?)",
        r"(\w+(?:\s+\w+)?)\s*\??\s*$",
    ]:
        m = re.search(pattern, q)
        if m:
            cap = m.group(1).strip()
            if cap and len(cap) > 2:
                return facility_type, [cap]
    return facility_type, []


def parse_facility_services_query(query: str) -> str | None:
    """If query is 'what services does X offer' / 'what does X offer', return facility name."""
    q = query.lower().strip()
    for pattern in [
        r"what services does (.+?) offer",
        r"what does (.+?) offer",
        r"what services (.+?) offer",
        r"services (.+?) offer",
        r"what (.+?) offer",
    ]:
        m = re.search(pattern, q, re.I)
        if m:
            return m.group(1).strip()
    return None


def parse_within_km_query(query: str) -> tuple[float, str] | None:
    """If query is 'within X km of Y' / 'within X km of Y', return (radius_km, place_name)."""
    q = query.lower().strip()
    m = re.search(r"within\s+(\d+(?:\.\d+)?)\s*km\s+of\s+(\w+(?:\s+\w+)?)", q, re.I)
    if m:
        return (float(m.group(1)), m.group(2).strip())
    return None


def parse_care_near_me_query(query: str) -> tuple[list[str], str] | None:
    """E.g. 'I'm pregnant, where should I go? I live in Accra' -> (['maternity', 'prenatal'], 'Accra')."""
    q = query.lower().strip()
    # Map phrases to search keywords
    care_map = [
        (["pregnant", "pregnancy", "maternity", "prenatal", "antenatal", "obstetric", "delivery", "birth"], ["maternity", "prenatal", "antenatal", "obstetric", "gynecology"]),
        (["child", "pediatric", "paediatric", "baby", "infant"], ["pediatrics", "paediatric"]),
        (["heart", "cardiac", "cardiology"], ["cardiology", "cardiac"]),
        (["dialysis", "kidney"], ["dialysis"]),
        (["mental", "psychiatry", "psychiatric"], ["psychiatry", "mental"]),
        (["eye", "vision", "ophthalmology"], ["ophthalmology"]),
    ]
    care_keywords = None
    for triggers, keywords in care_map:
        if any(t in q for t in triggers):
            care_keywords = keywords
            break
    if not care_keywords:
        return None
    # Extract location: "I live in Accra", "in Accra", "I'm in Kumasi", "based in Accra"
    place = None
    for pattern in [
        r"(?:i )?live in ([a-z\s\-]+?)(?:\?|\.|$)",
        r"(?:i'?m )?in ([a-z\s\-]+?)(?:\?|\.|$)",
        r"based in ([a-z\s\-]+?)(?:\?|\.|$)",
        r"(?:in|near) (accra|kumasi|tamale|takoradi|cape coast|sunyani|bolgatanga|ho|wa|techiman)\b",
    ]:
        m = re.search(pattern, q, re.I)
        if m:
            place = m.group(1).strip()
            if place and len(place) > 1:
                break
    if not place:
        return None
    return (care_keywords, place)


def parse_where_practicing_query(query: str) -> list[str] | None:
    """If query is 'where is/are X practicing' / 'where is cardiology offered', return keywords (e.g. [cardiology])."""
    q = query.lower().strip()
    if not ("where" in q and ("practicing" in q or "practicing" in q or "located" in q or "offered" in q or "available" in q or "workforce" in q)):
        return None
    # Extract specialty/capability: "workforce for cardiology" -> cardiology, "cardiology ... practicing" -> cardiology
    for pattern in [
        r"workforce for (\w+)",
        r"where (?:is|are) .*?(\w+)(?:\s+actually)?\s+practicing",
        r"where (?:is|are) (\w+) (?:practicing|located|offered|available)",
        r"(\w+)\s+(?:practicing|located|offered)",
    ]:
        m = re.search(pattern, q, re.I)
        if m:
            kw = m.group(1).strip()
            if len(kw) > 2 and kw not in ("the", "and", "for", "are", "how"):
                return [kw]
    # Fallback: take a likely medical term from the query
    medical = ["cardiology", "dialysis", "maternity", "pediatrics", "surgery", "psychiatry", "ophthalmology", "radiology"]
    for term in medical:
        if term in q:
            return [term]
    return None


def parse_regions_lack_query(query: str) -> list[str] | None:
    """E.g. 'which regions lack dialysis?' -> ['dialysis']. For gaps analysis."""
    q = query.lower().strip()
    if "which region" not in q and "regions lack" not in q and "regions that lack" not in q:
        return None
    m = re.search(r"regions?\s+(?:that\s+)?lack\s+(.+?)\??\s*$", q, re.I)
    if not m:
        return None
    cap = m.group(1).strip()
    keywords = [w for w in re.findall(r"\w+", cap.lower()) if len(w) > 2][:3]
    return keywords if keywords else [cap[:30]]


# Default "required equipment" when query says "lack equipment" for a service
CLAIM_BUT_LACK_DEFAULTS = {
    "surgery": ["operating", "theatre", "theater", "or room", "surgical", "operation room", "operating room"],
    "dialysis": ["dialysis", "hemodialysis", "dialys"],
    "maternity": ["delivery", "maternity", "obstetric", "labour", "labor"],
}


def parse_claim_but_lack_query(query: str) -> tuple[list[str], list[str]] | None:
    """E.g. 'facilities claim to offer surgery but lack basic equipment' -> (['surgery'], equipment_keywords)."""
    q = query.lower().strip()
    if "claim" not in q and "but lack" not in q and "lack the" not in q:
        return None
    # Detect service: "offer surgery", "offer X"
    claim_kw = []
    for pattern in [
        r"offer\s+(\w+(?:\s+\w+)?)\s+but",
        r"claim to offer\s+(\w+(?:\s+\w+)?)\s+but",
        r"(\w+)\s+but lack",
    ]:
        m = re.search(pattern, q, re.I)
        if m:
            claim_kw = [m.group(1).strip().lower()]
            break
    if not claim_kw and "surgery" in q:
        claim_kw = ["surgery", "surgical"]
    if not claim_kw:
        return None
    # What they lack: "lack the basic equipment", "lack equipment"
    lack_kw = []
    if "equipment" in q:
        service = "surgery" if any(s in q for s in ["surgery", "surgical"]) else ("dialysis" if "dialysis" in q else ("maternity" if "maternity" in q else None))
        lack_kw = CLAIM_BUT_LACK_DEFAULTS.get(service, ["equipment"])
    if not lack_kw:
        lack_kw = CLAIM_BUT_LACK_DEFAULTS.get("surgery", ["operating", "theatre", "surgical"])
    return (claim_kw, lack_kw)


def _row_claims_service(row: dict, keywords: list[str]) -> bool:
    """True if row's content (procedure, capability, description, specialties) mentions any keyword."""
    content = " ".join(str(row.get(c, "")) for c in ["procedure", "capability", "description", "specialties"]).lower()
    return any(k in content for k in keywords)


def _row_has_equipment(row: dict, equipment_keywords: list[str]) -> bool:
    """True if row's equipment/capability/procedure text contains any of the required terms."""
    text = " ".join(str(row.get(c, "")) for c in ["equipment", "capability", "procedure"]).lower()
    return any(k in text for k in equipment_keywords)


def parse_facility_in_place_with_capability(query: str) -> tuple[str, str, list[str]] | None:
    """E.g. 'clinics in Accra that do emergency services' -> (clinic, Accra, [emergency, services])."""
    q = query.lower().strip()
    # "any clinics in Accra that do emergency services?" / "hospitals in Kumasi that offer X"
    m = re.search(
        r"(?:any\s+)?(hospitals?|clinics?|pharmacies)\s+in\s+(\w+(?:\s+\w+)?)\s+that\s+(?:do|offer|have|provide)\s+(.+?)\??\s*$",
        q,
        re.I,
    )
    if not m:
        return None
    ft = m.group(1).strip().lower().rstrip("s")  # clinics -> clinic
    place = m.group(2).strip()
    cap_text = m.group(3).strip()
    keywords = [w for w in re.findall(r"\w+", cap_text.lower()) if len(w) > 2][:5]
    if not keywords:
        keywords = [cap_text[:50]]
    return (ft, place, keywords)


def parse_in_place_query(query: str) -> tuple[str | None, str] | None:
    """If query is 'how many X (are) in Y' / 'hospitals in Accra', return (facility_type, place_name)."""
    q = query.lower().strip()
    if parse_care_near_me_query(query) or parse_where_practicing_query(query) or parse_facility_in_place_with_capability(query):
        return None
    place = None
    for pattern in [
        r"how many (hospitals|clinics|pharmacies) (?:are )?in (\w+(?:\s+\w+)?)\??\s*$",
        r"(hospitals|clinics|pharmacies) in (\w+(?:\s+\w+)?)\??\s*$",
        r"in (accra|kumasi|tamale|takoradi|cape coast|sunyani|bolgatanga|greater accra|ashanti|eastern|western)\??\s*$",
        r"in (\w+)\??\s*$",
    ]:
        m = re.search(pattern, q, re.I)
        if m:
            if len(m.groups()) == 2:
                facility_type = m.group(1).strip() if m.group(1) else None
                place = m.group(2).strip()
            else:
                facility_type = "hospital" if "hospital" in q else ("clinic" if "clinic" in q else ("pharmacy" if "pharmacy" in q else None))
                place = m.group(1).strip()
            if place and len(place) > 1:
                return (facility_type, place)
    return None


def in_place_city(row: dict, place: str) -> bool:
    """True if row's address_city or address_stateOrRegion matches place."""
    place_lower = place.lower()
    city = (row.get("address_city") or "").strip().lower()
    region = (row.get("address_stateOrRegion") or "").strip().lower()
    return place_lower in city or place_lower in region or (place_lower == "accra" and "accra" in region)


def in_region(row: dict, region_name: str) -> bool:
    """True if row is in the given region (e.g. Greater Accra)."""
    r = region_name.lower().strip()
    city = (row.get("address_city") or "").strip().lower()
    state = (row.get("address_stateOrRegion") or "").strip().lower()
    if r in city or r in state:
        return True
    if "greater accra" in r or "accra" in r:
        return "accra" in city or "accra" in state or "greater accra" in state
    return False


def parse_highest_risk_in_region_query(query: str) -> tuple[int, list[str], str] | None:
    """
    If query is 'identify the N highest-risk [capability] facilities in [region]', return (n, keywords, region).
    E.g. 'identify the 3 highest-risk cardiac care facilities in the Greater Accra region' -> (3, ['cardiac','cardiology','heart'], 'Greater Accra').
    """
    q = query.lower().strip()
    if "highest-risk" not in q and "highest risk" not in q:
        return None
    if "facilities" not in q and "hospitals" not in q:
        return None
    # N
    n = 3
    m = re.search(r"(?:identify|find|list|the)\s+(?:top\s+)?(\d+)\s+(?:highest-risk|highest risk)", q, re.I)
    if m:
        n = int(m.group(1))
    # Region: "in the Greater Accra region", "in Greater Accra", "in the X region"
    region = ""
    for pat in [
        r"in the (\w+(?:\s+\w+)?)\s+region",
        r"in (\w+(?:\s+\w+)?)\s+region",
        r"in the (\w+(?:\s+\w+)?)\s*\.?\s*$",
        r"in (\w+(?:\s+\w+)?)\s*\.?\s*$",
    ]:
        m = re.search(pat, q, re.I)
        if m:
            region = m.group(1).strip()
            break
    if not region:
        return None
    # Capability: "cardiac care" -> cardiac, cardiology, heart; "dialysis" -> dialysis; etc.
    capability_map = [
        ("cardiac", ["cardiac", "cardiology", "heart"]),
        ("dialysis", ["dialysis"]),
        ("maternity", ["maternity", "obstetric", "prenatal", "gynecolog"]),
        ("surgery", ["surgery", "surgical"]),
        ("emergency", ["emergency"]),
    ]
    keywords = ["cardiac", "cardiology", "heart"]
    for term, kws in capability_map:
        if term in q:
            keywords = kws
            break
    return (n, keywords, region)


def parse_unrealistic_procedures_query(query: str) -> bool:
    """True if asking for facilities that claim an unrealistic number of procedures relative to size."""
    q = query.lower().strip()
    return any(
        x in q
        for x in (
            "unrealistic number of procedures",
            "procedures relative to their size",
            "procedures relative to size",
            "too many procedures for",
            "claim an unrealistic",
        )
    )


def parse_risk_query(query: str) -> str | None:
    """
    If query is about risk categories/rating, return type: 'summary' | 'high_risk' | 'tier_d' | 'tier_c' | 'risk_report'.
    """
    q = query.lower().strip()
    if not any(x in q for x in ("risk", "tier", "data completeness", "verification")):
        return None
    if "tier d" in q or "tier d facilities" in q or "worst documented" in q:
        return "tier_d"
    if "tier c" in q:
        return "tier_c"
    if "high risk" in q or "red risk" in q or "critical risk" in q or "facilities with high risk" in q:
        return "high_risk"
    if "risk categor" in q or "risk rating" in q or "risk score" in q or "risk report" in q or "risk summary" in q or "data completeness" in q:
        return "summary"
    return "summary"


def parse_abnormal_patterns_query(query: str) -> bool:
    """True if asking for facilities where expected correlated features don't match."""
    q = query.lower().strip()
    return any(
        x in q
        for x in (
            "abnormal patterns",
            "correlated features don't match",
            "correlated features do not match",
            "expected correlated",
            "features don't match",
            "mismatch",
            "inconsistent",
            "don't match",
        )
    )


def can_handle_locally(query: str) -> bool:
    """True if this query can be answered by local CSV + scheme (no LLM/RAG)."""
    q = query.lower().strip()
    if parse_highest_risk_in_region_query(query):
        return True
    if parse_abnormal_patterns_query(query):
        return True
    if parse_risk_query(query):
        return True
    if parse_unrealistic_procedures_query(query):
        return True
    if parse_facility_services_query(query):
        return True
    if parse_within_km_query(query):
        return True
    if parse_care_near_me_query(query):
        return True
    if parse_where_practicing_query(query):
        return True
    if parse_in_place_query(query):
        return True
    if parse_claim_but_lack_query(query):
        return True
    if parse_facility_in_place_with_capability(query):
        return True
    if parse_regions_lack_query(query):
        return True
    if any(x in q for x in ("how many", "which facilities", "which hospitals", "which clinics", "facilities with", "hospitals with", "list facilities", "where is", "where are", "claim", "lack", "any .* in .* that")):
        return True
    return False


def run_query(query: str, out: io.TextIOBase | None = None) -> str:
    """Run the local query pipeline; write to out (default stdout). Returns full output as string if out is a StringIO."""
    stream = out or sys.stdout
    _main_body(query, stream)
    if isinstance(stream, io.StringIO):
        return stream.getvalue()
    return ""


def _main_body(query: str, out: io.TextIOBase) -> None:
    """Core logic: load CSV, dispatch by query type, write answer to out."""
    def _fix_case(text: str) -> str:
        if not text:
            return text
        first = text[0]
        if first.isalpha() and first.islower():
            return first.upper() + text[1:]
        return text

    def pr(*args, **kwargs):
        if args and isinstance(args[0], str):
            args = (_fix_case(args[0]),) + args[1:]
        print(*args, file=out, **kwargs)

    name, rows = load_csv()
    if not rows:
        pr("No Ghana CSV found in data/ or Desktop.")
        return

    # "Identify the N highest-risk [capability] facilities in [region]; explain reasoning; recommend additional data"
    parsed = parse_highest_risk_in_region_query(query)
    if parsed:
        n, capability_keywords, region_name = parsed
        from src.risk_rating import compute_risk
        # Step 1: Filter to region (citation: address fields)
        step1_rows = [r for r in rows if in_region(r, region_name)]
        pr("**Answer**")
        pr(f"**Step 1 (region filter)** — *Citation: used `address_city` and `address_stateOrRegion` from {name}.*")
        pr(f"  Filtered to facilities in **{region_name}**: **{len(step1_rows)}** rows.")
        if not step1_rows:
            pr("\nNo facilities found in that region. Try another region name (e.g. Greater Accra, Ashanti).")
            return
        # Step 2: Filter to capability (citation: content fields)
        step2_rows = search_rows(step1_rows, capability_keywords, facility_type=None, query=query)
        pr(f"\n**Step 2 (capability filter)** — *Citation: used `specialties`, `procedure`, `capability`, `description`.*")
        pr(f"  Filtered to facilities mentioning **{', '.join(capability_keywords)}**: **{len(step2_rows)}** facilities.")
        if not step2_rows:
            pr(f"\nNo facilities in {region_name} mention {capability_keywords[0]} in the dataset.")
            return
        # Step 3: Compute risk for each (citation: risk_rating weights)
        step3 = [(r, compute_risk(r)) for r in step2_rows]
        pr(f"\n**Step 3 (risk scoring)** — *Citation: used risk_rating (weights: contact, facility type, specialties, location, capability, operator, procedures, address).*")
        pr(f"  Computed documentation quality for each of the **{len(step3)}** facilities.")
        # Step 4: Rank by documentation (lowest documentation = highest risk), take top N
        step4 = sorted(step3, key=lambda x: x[1].risk_score)[:n]
        pr(f"\n**Step 4 (ranking)** — *Citation: sorted by documentation quality; took top **{n}** (highest risk = lowest documentation).*")
        pr(f"\n--- **Top {n} highest-risk {capability_keywords[0]} facilities in {region_name}** ---\n")
        all_critical = []
        all_moderate = []
        for i, (row, res) in enumerate(step4, 1):
            pr(f"**{i}. {(row.get('name') or 'Unknown').strip()}**")
            pr(f"   Trust Factor: **{res.tier}**  |  Risk Factor: **{res.risk_band}**")
            key_gaps = ", ".join(s.title() for s in res.critical_missing) or "None"
            pr(f"   Key gaps: {key_gaps}")
            extra_gaps = ", ".join(s.title() for s in res.moderate_missing) or "None"
            pr(f"   Additional gaps: {extra_gaps}")
            all_critical.extend(res.critical_missing)
            all_moderate.extend(res.moderate_missing)
            pr("")
        # Reasoning
        pr("**Reasoning:**")
        pr(f"  We restricted to **{region_name}** (Step 1), then to facilities that list **{capability_keywords[0]}**-related services (Step 2).")
        pr(f"  Documentation quality was computed from contact info, facility type, specialties, location, capability, operator type, procedures/equipment, and address completeness (Step 3).")
        pr(f"  The **{n}** facilities with the **lowest** documentation are the highest-risk; they have the most critical/moderate gaps (e.g. no contact, unknown facility type, missing specialties or location).")
        # Recommendation: additional data that would reduce risk most
        from collections import Counter
        crit = Counter(all_critical)
        mod = Counter(all_moderate)
        pr("\n**Recommendation — additional data that would reduce risk the most:**")
        if crit:
            top_crit = [k for k, _ in crit.most_common(4)]
            pr(f"  - **Critical:** Collect and add **{', '.join(top_crit)}** for these facilities. Each missing critical field costs 12 points; adding contact, facility type, specialties, or location would raise scores the most.")
        if mod:
            top_mod = [k for k, _ in mod.most_common(3)]
            pr(f"  - **Moderate:** Add **{', '.join(top_mod)}** where missing (8 points each).")
        pr("\n  Prioritize **contact information** (phone, email, or website) and **facility type** first, then **specialties** and **location** details; that would move the most facilities out of High/Medium risk.")
        pr("\n*(Step-level citations: each step above states which data was used.)*")
        return

    # Risk categories / risk rating / data completeness
    risk_type = parse_risk_query(query)
    if risk_type:
        from src.risk_rating import compute_risk_all, risk_summary
        results = compute_risk_all(rows)
        summary = risk_summary(rows)
        pr("**Risk rating**")
        pr("- **Trust Factor**: A (best documented) → D (largest gaps)")
        pr("- **Risk Factor**: Low / Medium / High (data completeness risk)")
        pr("")
        pr("**Summary**")
        pr(f"  Facilities: **{summary['total_facilities']}**")
        pr(f"  Avg data completeness: **{summary['avg_completeness_score']}%**")
        pr("  By risk band:", summary["by_risk_band"])
        pr("  By tier (A=best → D=critical gaps):", summary["by_tier"])
        subset = []
        if risk_type == "high_risk":
            subset = [(r, res) for r, res in results if res.risk_band == "High"]
        elif risk_type == "tier_d":
            subset = [(r, res) for r, res in results if res.tier == "D"]
        elif risk_type == "tier_c":
            subset = [(r, res) for r, res in results if res.tier == "C"]
        if subset:
            label = {"high_risk": "High Risk (Red)", "tier_d": "Tier D", "tier_c": "Tier C"}.get(risk_type, "list")
            pr(f"\n**Facilities: {label}** ({len(subset)}):")
            for row, res in sorted(subset, key=lambda x: x[1].risk_score)[:30]:
                missing = ", ".join(s.title() for s in res.critical_missing[:3]) + ("..." if len(res.critical_missing) > 3 else "")
                pr(f"  - {(row.get('name') or 'Unknown')[:50]} (Trust Factor: {res.tier}, Risk Factor: {res.risk_band}, Key gaps: {missing or 'None'})")
            if len(subset) > 30:
                pr(f"  ... and {len(subset) - 30} more.")
        elif risk_type in ("high_risk", "tier_d", "tier_c"):
            pr(f"\nNo facilities in {risk_type.replace('_', ' ').title()}.")
        pr("\n(Weights: critical=contact/facility type/specialties/location; moderate=capability/operator/procedures/address; low=description/social/capacity.)")
        return

    # Abnormal patterns: facilities where expected correlated features don't match
    if parse_abnormal_patterns_query(query):
        from src.correlation_mismatch import facilities_with_abnormal_patterns
        abnormal = facilities_with_abnormal_patterns(rows)
        pr("**Answer**")
        pr(f"Facilities with **abnormal patterns** (expected correlated features don't match): **{len(abnormal)}**.")
        pr("\nChecks: pharmacy claiming surgery/inpatient; dentist listing non-dental services; hospital with no clinical text; specialty without matching procedure; rich contact but no clinical data; clinic described as tertiary/referral.")
        if abnormal:
            pr("\nExamples:")
            for row, mismatches in abnormal[:25]:
                name = (row.get("name") or "Unknown")[:50]
                types = "; ".join(m.kind for m in mismatches[:3])
                pr(f"  - **{name}** — {types}")
                for m in mismatches[:2]:
                    pr(f"      ({m.description})")
            if len(abnormal) > 25:
                pr(f"  ... and {len(abnormal) - 25} more.")
        else:
            pr("\nNo facilities flagged for these correlation mismatches in the dataset.")
        pr("\n(Based on facility type vs. procedure/capability, specialty vs. procedure, contact vs. clinical completeness.)")
        return

    # "Unrealistic number of procedures relative to size" -> procedure/size outlier list
    if parse_unrealistic_procedures_query(query):
        from src.procedure_size_outlier import procedure_size_outliers
        outliers = procedure_size_outliers(rows, top_percent=8.0, min_procedures=5)
        pr("**Answer**")
        pr(f"Facilities that claim a **high number of procedures relative to their size** (top ~8% by procedure-count/size proxy): **{len(outliers)}**.")
        pr("\nSize proxy uses facility type (hospital > clinic > doctor/dentist > pharmacy) and capacity when present.")
        if outliers:
            pr("\nExamples (procedure count / size proxy = ratio):")
            for row, rec in outliers[:25]:
                pr(f"  - **{rec.name[:55]}** — type: {rec.facility_type}, procedures: {rec.procedure_count}, size: {rec.size_proxy}, ratio: {rec.ratio}")
            if len(outliers) > 25:
                pr(f"  ... and {len(outliers) - 25} more.")
        else:
            pr("\nNo facilities met the threshold (top 8% ratio with at least 5 procedures listed).")
        pr("\n(Based on procedure field list length and facilityTypeId/capacity.)")
        return

    # "What services does X offer?" -> facility lookup, show services with N/A for empty
    facility_name = parse_facility_services_query(query)
    if facility_name:
        row = find_facility_by_name(rows, facility_name)
        if row:
            pr("**" + (row.get("name") or "Facility") + "**\n")
            pr(format_services(row))
            # Terminology block removed for cleaner user-facing responses
        else:
            pr("No facility found matching \"" + facility_name + "\".")
        return

    # "I'm pregnant, where should I go? I live in Accra" -> care type + location
    care_near = parse_care_near_me_query(query)
    if care_near:
        care_keywords, place_name = care_near
        matches = search_rows(rows, care_keywords, facility_type=None, query=query)
        in_place = [r for r in matches if in_place_city(r, place_name)]
        pr("**Answer**")
        if in_place:
            pr(f"Top hospitals for **{care_keywords[0]}** care in **{place_name.title()}** (ranked by documentation quality):")
            _print_ranked_list(pr, in_place, "", limit=5, prefer_hospitals=True)
        else:
            pr("No facilities with that type of care found in that location in the dataset. Try a nearby city or a broader search.")
        return

    # "Where is/are X practicing?" -> facilities with that specialty, grouped by location
    where_kw = parse_where_practicing_query(query)
    if where_kw:
        matches = search_rows(rows, where_kw, facility_type=None, query=query)
        by_region = {}
        for r in matches:
            region = (r.get("address_stateOrRegion") or "").strip() or ""
            city = (r.get("address_city") or "").strip() or ""
            if region and city and region != city and region.lower() != "null" and city.lower() != "null":
                loc = f"{city}, {region}"
            elif city and city.lower() != "null":
                loc = city
            elif region and region.lower() != "null":
                loc = region
            else:
                loc = "Unknown / not specified"
            by_region.setdefault(loc, []).append(r)
        for loc in by_region:
            by_region[loc] = sort_rows_by_richness_then_similarity(by_region[loc], query)
        pr("**Answer**")
        pr(f"Facilities offering **{', '.join(where_kw)}** in Ghana: **{len(matches)}**.")
        if matches:
            pr("\nTop facilities (ranked by documentation quality):")
            _print_ranked_list(pr, matches, "", limit=5, prefer_hospitals=False)
        # Terminology block removed for cleaner user-facing responses
        return

    # "Which facilities claim to offer X but lack Y?" (e.g. surgery but lack equipment)
    claim_lack = parse_claim_but_lack_query(query)
    if claim_lack:
        claim_kw, lack_kw = claim_lack
        claimers = [r for r in rows if _row_claims_service(r, claim_kw)]
        missing = [r for r in claimers if not _row_has_equipment(r, lack_kw)]
        missing = sort_rows_by_richness_then_similarity(missing, query)
        pr("**Answer**")
        pr(f"Facilities that **mention {', '.join(claim_kw)}** but **do not list** basic required terms ({', '.join(lack_kw[:5])}{'...' if len(lack_kw) > 5 else ''}) in equipment/capability/procedure: **{len(missing)}**.")
        if missing:
            pr("\nTop facilities (ranked by documentation quality):")
            _print_ranked_list(pr, missing, "", limit=5, prefer_hospitals=False)
        else:
            pr("\nNo such facilities found in the dataset (or all facilities that mention the service also list relevant equipment).")
        pr("\n(Based on procedure, capability, description, specialties for “claim”; equipment, capability, procedure for “has equipment”.)")
        return

    # "Which regions lack [capability]?" (gaps by region)
    regions_lack_kw = parse_regions_lack_query(query)
    if regions_lack_kw:
        has_cap = search_rows(rows, regions_lack_kw, facility_type=None, query=query)
        regions_with = set()
        for r in has_cap:
            reg = (r.get("address_stateOrRegion") or r.get("address_city") or "").strip()
            if reg and reg.lower() not in ("null", ""):
                regions_with.add(reg)
        all_regions = set()
        for r in rows:
            reg = (r.get("address_stateOrRegion") or r.get("address_city") or "").strip()
            if reg and reg.lower() not in ("null", ""):
                all_regions.add(reg)
        regions_lacking = sorted(all_regions - regions_with, key=lambda x: x.lower())
        pr("**Answer**")
        pr(f"Regions with **no** facilities that mention **{', '.join(regions_lack_kw)}** in the dataset: **{len(regions_lacking)}**.")
        if len(has_cap) > 0 and len(regions_with) == 0:
            pr(f"\n(Note: {len(has_cap)} facility(ies) mention this capability but have no region/city recorded, so they are not counted under any region.)")
        if regions_lacking:
            pr("\n**Regions that lack " + ", ".join(regions_lack_kw) + ":**")
            pr(", ".join(regions_lacking))
        else:
            pr("\nEvery region in the dataset has at least one facility mentioning that capability.")
        pr(f"\n(Regions with the capability: {len(regions_with)}. Compared to {len(all_regions)} regions total in the data.)")
        return

    # "Within X km of Y" (e.g. hospitals treating heart disease within 5 km of Accra)
    within_km = parse_within_km_query(query)
    if within_km is not None:
        radius_km, place_name = within_km
        name_geo, rows_geo = load_csv(prefer_geocoded=True)
        if not rows_geo:
            pr("No Ghana CSV found.")
            return
        ref = get_place_coords(place_name)
        if ref is None:
            pr(f"Unknown place \"{place_name}\". Known places: Accra, Kumasi, Tamale, Takoradi, Cape Coast.")
            return
        facility_type, keywords = parse_query(query)
        if not keywords:
            keywords = [w for w in query.split() if len(w) > 3 and "km" not in w.lower() and "within" not in w.lower()][:3]
        if not keywords:
            keywords = ["cardiology", "heart", "cardiac"]
        elif any(k in query.lower() for k in ("heart", "cardiac", "cardiology")):
            keywords = ["cardiology", "heart", "cardiac"]
        candidates = search_rows(rows_geo, keywords, facility_type, query=query)
        within = filter_rows_within_km(rows_geo, ref[0], ref[1], radius_km)
        within_set = {id(r) for r in within}
        within_with_heart = [r for r in candidates if id(r) in within_set]
        unique_names = list(dict.fromkeys((r.get("name") or "Unknown").strip() for r in within_with_heart))
        pr("**Answer**")
        pr(f"Hospitals treating heart disease within **{radius_km:.0f} km** of **{place_name.title()}**: **{len(within_with_heart)}** (unique names: **{len(unique_names)}**).")
        if unique_names:
            pr("\nFacilities:", ", ".join(unique_names[:20]))
            if len(unique_names) > 20:
                pr("... and", len(unique_names) - 20, "more.")
        if len(within_with_heart) == 0:
            # Fallback: count in city (no distance) when we have no coords for geo filter
            in_place = [r for r in candidates if in_place_city(r, place_name)]
            in_place_names = list(dict.fromkeys((r.get("name") or "Unknown").strip() for r in in_place))
            if in_place_names:
                pr(f"\n(No coordinates in the dataset for distance filter. Using **address_city** only: **{len(in_place_names)}** such hospitals in **{place_name.title()}**: {', '.join(in_place_names[:15])}{'...' if len(in_place_names) > 15 else ''}.)")
            else:
                pr("\n(No coordinates in the dataset for distance filter. Run `python geocode_facilities.py` to add lat/lon, then re-run this query.)")
        else:
            pr(f"\n(Data: {name_geo}; distance from {place_name.title()} centre {ref[0]:.4f}, {ref[1]:.4f}.)")
        return

    # "Clinics in Accra that do emergency services?" -> facility type + place + capability
    cap_in_place = parse_facility_in_place_with_capability(query)
    if cap_in_place:
        ft_id, place_name, cap_keywords = cap_in_place
        ft_map = {"hospitals": "hospital", "clinics": "clinic", "pharmacies": "pharmacy"}
        ft_id = ft_map.get(ft_id, ft_id)
        candidates = search_rows(rows, cap_keywords, facility_type=ft_id, query=query)
        in_place_rows = sort_rows_by_richness_then_similarity([r for r in candidates if in_place_city(r, place_name)], query)
        pr("**Answer**")
        if in_place_rows:
            pr(f"Yes. **{len(in_place_rows)}** {ft_id}(s) in **{place_name.title()}** that mention **{', '.join(cap_keywords[:3])}**.")
            pr("\nTop facilities (ranked by documentation quality):")
            _print_ranked_list(pr, in_place_rows, "", limit=5, prefer_hospitals=(ft_id == "hospital"))
        else:
            pr(f"No {ft_id}s in **{place_name.title()}** in the dataset that list **{', '.join(cap_keywords[:3])}** in their capability/procedure/description.")
        pr(f"\n(Based on facilityTypeId, address_city/region, and content match.)")
        return

    # "How many hospitals are in Accra?" / "hospitals in Accra" -> count by address
    in_place = parse_in_place_query(query)
    if in_place is not None:
        facility_type, place_name = in_place
        ft_map = {"hospitals": "hospital", "clinics": "clinic", "pharmacies": "pharmacy"}
        ft_id = ft_map.get((facility_type or "").lower(), facility_type or "").lower() or None
        if ft_id:
            filtered = [r for r in rows if (r.get("facilityTypeId") or "").strip().lower() == ft_id]
        else:
            filtered = rows
        in_place_rows = sort_rows_by_richness_then_similarity([r for r in filtered if in_place_city(r, place_name)], query)
        ft_label = ft_id or facility_type or "facilities"
        pr("**Answer**")
        plural = "s" if len(in_place_rows) != 1 and (ft_label == "hospital" or ft_label == "clinic" or ft_label == "pharmacy") else ""
        pr(f"**{len(in_place_rows)}** {ft_label}{plural} in **{place_name.title()}**.")
        if in_place_rows:
            pr("\nTop facilities (ranked by documentation quality):")
            _print_ranked_list(pr, in_place_rows, "", limit=5, prefer_hospitals=(ft_label == "hospital"))
        pr(f"\n(Based on address_city and address_stateOrRegion.)")
        return

    facility_type, keywords = parse_query(query)
    if not keywords:
        keywords = [w for w in query.split() if len(w) > 3][:3]
    if not keywords:
        keywords = ["cardiology"]

    # Per scheme: we look in specialties, procedure, equipment, capability, description
    matches = search_rows(rows, keywords, facility_type, query=query)

    # Build answer using scheme terminology
    ft_label = f" with facilityTypeId = '{facility_type}'" if facility_type else ""
    pr("**Answer**")
    if facility_type:
        pr(f"Count of facilities{ft_label} that mention '{' or '.join(keywords)}' in specialties, procedure, equipment, capability, or description: **{len(matches)}**.")
    else:
        pr(f"Count of facilities that mention '{' or '.join(keywords)}': **{len(matches)}**.")
    if matches:
        pr("\nTop facilities (ranked by documentation quality):")
        _print_ranked_list(pr, matches, "", limit=5, prefer_hospitals=(facility_type == "hospital"))

    # Terminology from the scheme
    columns_used = ["specialties", "procedure", "equipment", "capability", "description", "facilityTypeId"]
    # Terminology block removed for cleaner user-facing responses


def main():
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "How many hospitals have cardiology?"
    _main_body(query, sys.stdout)


if __name__ == "__main__":
    main()
