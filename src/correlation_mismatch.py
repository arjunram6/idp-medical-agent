"""
Detect facilities where expected correlated features don't match (abnormal patterns).
E.g. pharmacy claiming surgery; specialty listed but no related procedure; hospital with no capability.
"""

import re
from dataclasses import dataclass
from typing import Any


def _text(row: dict, *keys: str) -> str:
    return " ".join(str(row.get(k) or "") for k in keys).lower()


def _has_any(row: dict, keys: tuple[str, ...], *phrases: str) -> bool:
    text = _text(row, *keys)
    return any(p in text for p in phrases)


# Pharmacy should not claim surgical/inpatient/hospital-level services
PHARMACY_INCONSISTENT = (
    "surgery", "surgical", "operating room", "or theatre", "inpatient", "icu", "nicu",
    "emergency surgery", "major surgery", "laparotomy", "cesarean", "c-section",
)

# Dentist: typically dental only; "general surgery" or "cardiology" without dental context is odd
DENTIST_INCONSISTENT = (
    "cardiology", "general surgery", "obstetric", "pediatric ward", "icu", "nicu",
)

# Clinic vs hospital: hospital expected to have broader capability; clinic with "tertiary" "referral" without size is notable
CLINIC_HOSPITAL_LEVEL = ("tertiary", "referral center", "teaching hospital", "regional hospital", "national referral")


@dataclass
class Mismatch:
    kind: str
    description: str


def correlation_mismatches(row: dict) -> list[Mismatch]:
    """
    Return list of mismatches for one facility: expected correlations that don't hold.
    """
    out: list[Mismatch] = []
    ft = (row.get("facilityTypeId") or "").strip().lower()
    content = _text(row, "procedure", "capability", "equipment", "description", "specialties")
    has_capability = bool((row.get("capability") or "").strip())
    has_procedure = bool((row.get("procedure") or "").strip())
    has_specialties = bool((row.get("specialties") or "").strip())
    contact_count = sum(
        1 for k in ("phone_numbers", "email", "websites")
        if (row.get(k) or "").strip() and str(row.get(k)).lower() not in ("null", "[]", "")
    )

    # 1. Pharmacy claiming surgical/inpatient services
    if ft == "pharmacy" and _has_any(row, ("procedure", "capability", "description"), *PHARMACY_INCONSISTENT):
        out.append(Mismatch("pharmacy_claims_hospital_services", "Pharmacy lists surgery/inpatient/ICU-type services."))

    # 2. Dentist listing non-dental major services (without dental context)
    if ft == "dentist":
        if _has_any(row, ("procedure", "capability"), *DENTIST_INCONSISTENT):
            # Allow if also clearly dental
            if "dental" not in content and "dentist" not in content and "tooth" not in content:
                out.append(Mismatch("dentist_non_dental_services", "Dentist lists cardiology/surgery/ICU without dental context."))

    # 3. Hospital with no capability/procedure text (expected to have clinical description)
    if ft == "hospital" and not has_capability and not has_procedure:
        out.append(Mismatch("hospital_no_clinical", "Hospital has no capability or procedure text."))

    # 4. Specialties listed but no overlapping procedure/capability (specialty–procedure mismatch)
    if has_specialties and (has_capability or has_procedure):
        specialties_text = (row.get("specialties") or "").lower()
        # Common specialty keywords that should appear in procedure/capability
        specialty_keywords = [
            "cardiology", "surgery", "pediatric", "obstetric", "gynecolog", "orthopedic",
            "ophthalmolog", "dentist", "emergency", "internal medicine", "family medicine",
        ]
        for kw in specialty_keywords:
            if kw in specialties_text:
                if kw not in content and not (kw == "surgery" and "surgical" in content):
                    out.append(Mismatch("specialty_no_matching_procedure", f"Specialty suggests '{kw}' but procedure/capability has no matching terms."))
                break  # one mismatch per row for this rule

    # 5. Rich contact but no clinical data (contact vs. clinical mismatch)
    if contact_count >= 2 and not has_capability and not has_procedure and not has_specialties:
        out.append(Mismatch("rich_contact_no_clinical", "Phone/email/website present but no capability, procedure, or specialties."))

    # 6. Clinic described as tertiary/referral/teaching (scale mismatch)
    if ft == "clinic" and _has_any(row, ("description", "capability"), *CLINIC_HOSPITAL_LEVEL):
        out.append(Mismatch("clinic_described_as_hospital_level", "Clinic described as tertiary/referral/teaching hospital."))

    return out


def facilities_with_abnormal_patterns(rows: list[dict]) -> list[tuple[dict, list[Mismatch]]]:
    """Return (row, list of Mismatch) for every row that has at least one correlation mismatch."""
    result: list[tuple[dict, list[Mismatch]]] = []
    for row in rows:
        mismatches = correlation_mismatches(row)
        if mismatches:
            result.append((row, mismatches))
    return result
