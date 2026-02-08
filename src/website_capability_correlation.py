"""
Correlation between website/contact quality indicators and actual facility capabilities.
Uses CSV fields: websites, phone_numbers, email (indicators) vs capability, procedure, equipment, specialties (capabilities).
"""

from typing import Any


def _present(row: dict, key: str) -> bool:
    v = (row.get(key) or "").strip()
    return bool(v and str(v).lower() not in ("null", "[]", ""))


def _capability_richness(row: dict) -> float:
    """Score 0–4: count of non-empty capability, procedure, equipment, specialties."""
    cols = ["capability", "procedure", "equipment", "specialties"]
    return sum(1 for c in cols if _present(row, c))


def _capability_content_length(row: dict) -> float:
    """Total character length of capability-related fields (proxy for detail)."""
    total = 0
    for c in ["capability", "procedure", "equipment", "specialties", "description"]:
        v = (row.get(c) or "").strip()
        if v and str(v).lower() not in ("null", "[]", ""):
            total += len(v)
    return float(total)


def _website_indicator(row: dict) -> int:
    """1 if has website, 0 otherwise."""
    return 1 if _present(row, "websites") else 0


def _contact_richness(row: dict) -> int:
    """0–3: count of phone, email, website present."""
    return sum(1 for k in ("phone_numbers", "email", "websites") if _present(row, k))


def correlation(x: list[float], y: list[float]) -> float:
    """Pearson correlation. Returns 0 if variance is zero."""
    n = len(x)
    if n != len(y) or n < 2:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    sx = sum((a - mx) ** 2 for a in x) ** 0.5
    sy = sum((b - my) ** 2 for b in y) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    r = sum((x[i] - mx) * (y[i] - my) for i in range(n)) / (sx * sy)
    return round(r, 4)


def analyze(rows: list[dict]) -> dict[str, Any]:
    """
    Compute correlations between website/contact indicators and capability measures.
    Returns dict with correlation coefficients, counts, and interpretation.
    """
    n = len(rows)
    has_web = [_website_indicator(r) for r in rows]
    contact_rich = [_contact_richness(r) for r in rows]
    cap_rich = [_capability_richness(r) for r in rows]
    cap_len = [_capability_content_length(r) for r in rows]

    r_web_cap_rich = correlation(has_web, cap_rich)
    r_web_cap_len = correlation(has_web, cap_len)
    r_contact_cap_rich = correlation(contact_rich, cap_rich)
    r_contact_cap_len = correlation(contact_rich, cap_len)

    n_with_website = sum(has_web)
    avg_cap_rich_with_web = sum(cap_rich[i] for i in range(n) if has_web[i]) / n_with_website if n_with_website else 0
    avg_cap_rich_no_web = sum(cap_rich[i] for i in range(n) if not has_web[i]) / (n - n_with_website) if (n - n_with_website) else 0

    return {
        "n_facilities": n,
        "n_with_website": n_with_website,
        "pct_with_website": round(100 * n_with_website / n, 1) if n else 0,
        "correlation_website_vs_capability_richness": r_web_cap_rich,
        "correlation_website_vs_capability_content_length": r_web_cap_len,
        "correlation_contact_richness_vs_capability_richness": r_contact_cap_rich,
        "correlation_contact_richness_vs_capability_content_length": r_contact_cap_len,
        "avg_capability_richness_with_website": round(avg_cap_rich_with_web, 2),
        "avg_capability_richness_without_website": round(avg_cap_rich_no_web, 2),
        "interpretation": _interpret(r_web_cap_rich, r_contact_cap_rich, avg_cap_rich_with_web, avg_cap_rich_no_web),
    }


def _interpret(r_web: float, r_contact: float, avg_with: float, avg_without: float) -> str:
    parts = []
    if abs(r_web) < 0.1:
        parts.append("Website presence (yes/no) shows weak or no linear correlation with capability richness in this dataset.")
    elif r_web > 0:
        parts.append(f"Facilities with a website tend to have slightly higher capability documentation (r={r_web}).")
    else:
        parts.append(f"Facilities with a website tend to have slightly lower capability documentation (r={r_web}).")
    if abs(r_contact) >= 0.15:
        parts.append(f"Contact richness (phone+email+website) correlates more with capability completeness (r={r_contact}).")
    if avg_with > avg_without:
        parts.append(f"On average, facilities with a website document {avg_with:.1f} capability areas (of 4) vs {avg_without:.1f} without—suggesting better-documented facilities also invest in contact/web presence.")
    elif avg_with < avg_without:
        parts.append(f"Facilities without a website average {avg_without:.1f} capability areas vs {avg_with:.1f} with; possible reporting bias or different population.")
    return " ".join(parts)
