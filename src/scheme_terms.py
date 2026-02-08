"""
Use the Virtue Foundation Scheme Documentation to explain data terminology.
No API calls — schema text only.
"""

from pathlib import Path


def _find_schema_path() -> Path | None:
    from src.config import DATA_DIR
    for name in ["Virtue Foundation Scheme Documentation.txt", "SCHEMA.md"]:
        p = DATA_DIR / name
        if p.exists():
            return p
        p = Path.home() / "Desktop" / name
        if p.exists():
            return p
    return None


def get_scheme_text() -> str:
    """Return full scheme document text."""
    path = _find_schema_path()
    if not path:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


# Key terms from the scheme → plain-language explanation (for answers)
SCHEME_TERMS = {
    "specialties": "Medical specialties (e.g. cardiology, pediatrics, generalSurgery) — from the scheme: 'The medical specialties associated with the organization. Must use exact case-sensitive matches from the specialty hierarchy (e.g., internalMedicine, familyMedicine, pediatrics, cardiology, generalSurgery, emergencyMedicine, gynecologyAndObstetrics, orthopedicSurgery, dentistry, ophthalmology).'",
    "procedure": "Specific clinical services — from the scheme: 'Medical/surgical interventions and diagnostic procedures (e.g., operations, endoscopy, imaging- or lab-based tests). Each fact a clear, declarative statement; include quantities when available.'",
    "equipment": "Physical medical devices — from the scheme: 'Imaging machines (MRI/CT/X-ray), surgical/OR technologies, laboratory analyzers, critical utilities (e.g., piped oxygen, backup power). Include specific models when available.'",
    "capability": "Level and types of clinical care — from the scheme: 'Trauma/emergency care levels, specialized units (ICU/NICU/burn unit), clinical programs (stroke care, IVF), diagnostic capabilities, accreditations, care setting (inpatient/outpatient), staffing, patient capacity. Excludes addresses, contact, hours, pricing.'",
    "facilityTypeId": "Type of facility — from the scheme: 'Levels: hospital, pharmacy, doctor, clinic, dentist.'",
    "name": "Official name of the organization (complete, proper capitalization, no Ltd/LLC/Inc).",
    "address_city": "City or town of the organization.",
    "address_stateOrRegion": "State, region, or province.",
    "description": "A brief paragraph describing the facility's services and/or history.",
}


def explain_term(term: str) -> str:
    """Return scheme-based explanation for a data term."""
    key = term.lower().replace(" ", "_")
    if key in SCHEME_TERMS:
        return SCHEME_TERMS[key]
    for k, v in SCHEME_TERMS.items():
        if k.lower() == key:
            return v
    return ""


def explain_relevant_terms(columns_used: list[str]) -> str:
    """Return a short 'According to the scheme' block for the columns used."""
    lines = ["**Terminology (Virtue Foundation Scheme):**"]
    for col in columns_used:
        ex = explain_term(col)
        if ex:
            lines.append(f"- **{col}**: {ex}")
    return "\n".join(lines) if len(lines) > 1 else ""
