"""
Unstructured feature extraction: process free-form procedure, equipment, capability
(and related) columns to identify specific medical data.
"""

import re
from typing import Any

# Patterns for common medical terms (extend as needed)
PROCEDURE_PATTERNS = [
    r"\b(surgery|surgical|operation|hemodialysis|dialysis|cesarean|c-section|endoscopy|biopsy)\b",
    r"\b(consultation|screening|testing|vaccination|immunization)\b",
    r"\b(laboratory|lab)\s+(test|service)\b",
    r"\b(antenatal|prenatal|maternal|obstetric)\b",
    r"\b(mental\s+health|psychiatry|psychiatric)\b",
    r"\b(hiv|aids|tb|pmtct|testing\s+and\s+counseling)\b",
]
EQUIPMENT_PATTERNS = [
    r"\b(x-?ray|ultrasound|ct\s+scan|mri|ecg|ventilator)\b",
    r"\b(operating\s+theatre|theater|or\s+room)\b",
    r"\b(dialysis\s+machine|oxygen)\b",
    r"\b(laboratory|lab)\b",
]
CAPABILITY_PATTERNS = [
    r"\b(24/7|emergency|inpatient|outpatient|opd)\b",
    r"\b(icu|nicu|trauma|referral)\b",
    r"\b(accredited|nhis|insurance)\b",
    r"\b(maternity|pediatric|paediatric)\b",
]


def extract_from_text(text: str) -> dict[str, list[str]]:
    """Extract procedures, equipment, and capabilities from free-form text."""
    if not text or not isinstance(text, str):
        return {"procedures": [], "equipment": [], "capabilities": []}
    t = text.lower()
    out = {"procedures": [], "equipment": [], "capabilities": []}
    for pat in PROCEDURE_PATTERNS:
        for m in re.finditer(pat, t, re.I):
            out["procedures"].append(m.group(0).strip())
    for pat in EQUIPMENT_PATTERNS:
        for m in re.finditer(pat, t, re.I):
            out["equipment"].append(m.group(0).strip())
    for pat in CAPABILITY_PATTERNS:
        for m in re.finditer(pat, t, re.I):
            out["capabilities"].append(m.group(0).strip())
    # Dedupe and limit
    for k in out:
        out[k] = list(dict.fromkeys(out[k]))[:15]
    return out


def extract_medical_from_docs(docs: list[dict]) -> list[dict[str, Any]]:
    """Run extraction on each retrieved doc; return list of {ref_id, name, procedures, equipment, capabilities}."""
    results = []
    for d in docs:
        text = d.get("text", "")
        meta = d.get("metadata") or {}
        extracted = extract_from_text(text)
        results.append({
            "ref_id": d.get("ref_id"),
            "name": meta.get("name", "Unknown"),
            "region": meta.get("region") or meta.get("address_city") or meta.get("address_stateOrRegion") or "",
            "procedures": extracted["procedures"],
            "equipment": extracted["equipment"],
            "capabilities": extracted["capabilities"],
            "source": meta.get("source", ""),
        })
    return results
