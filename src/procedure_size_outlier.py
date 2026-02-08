"""
Identify facilities that claim an unrealistic number of procedures relative to their size.
Size proxy: facility type (hospital > clinic > doctor/dentist > pharmacy) and capacity when present.
Procedure count: heuristic from procedure (and optionally capability/equipment) text.
"""

import re
from dataclasses import dataclass
from typing import Any

# Facility type → size proxy (higher = larger expected capacity for procedures)
TYPE_SIZE = {
    "hospital": 4,
    "clinic": 3,
    "doctor": 2,
    "dentist": 2,
    "pharmacy": 1,
}


def _procedure_count(row: dict) -> int:
    """
    Estimate number of distinct procedures/services from procedure field.
    Splits on comma, semicolon, " and ", newline, numbered list; counts non-empty segments.
    """
    text = (row.get("procedure") or "").strip()
    if not text or text.lower() in ("null", "[]", ""):
        return 0
    # Normalize: replace common list separators with pipe, then split
    text = re.sub(r"\s+and\s+", "|", text, flags=re.I)
    text = re.sub(r"[,;]", "|", text)
    text = re.sub(r"\n+", "|", text)
    # Numbered items: "1. X 2. Y" or "1) X 2) Y"
    text = re.sub(r"\d+[.)]\s*", "|", text)
    parts = [p.strip() for p in text.split("|") if p.strip() and len(p.strip()) > 2]
    # Dedupe by lowercasing and take unique
    seen = set()
    count = 0
    for p in parts:
        key = p.lower()[:50]
        if key not in seen:
            seen.add(key)
            count += 1
    return max(count, 1 if text else 0)


def _size_proxy(row: dict) -> float:
    """
    Size proxy: facility type rank (1-4) plus optional capacity boost.
    Capacity is rarely present; when present, use log-scale to avoid one huge value dominating.
    """
    ft = (row.get("facilityTypeId") or "").strip().lower()
    base = TYPE_SIZE.get(ft, 2)  # default medium-small
    cap_raw = (row.get("capacity") or "").strip()
    if cap_raw:
        try:
            cap = int(re.sub(r"[^\d]", "", cap_raw)[:6] or 0)
            if cap > 0:
                import math
                base = base + min(2.0, math.log10(cap + 1) / 2)  # cap adds up to ~2
        except (ValueError, TypeError):
            pass
    return base


@dataclass
class ProcedureSizeRow:
    name: str
    facility_type: str
    procedure_count: int
    size_proxy: float
    ratio: float
    is_outlier: bool


def _is_outlier(ratio: float, ratios: list[float], top_pct: float = 0.92) -> bool:
    """True if ratio is in the top (1 - top_pct) of all ratios (e.g. top 8%)."""
    if not ratios:
        return False
    sorted_r = sorted(ratios, reverse=True)
    idx = max(0, int(len(sorted_r) * (1 - (1 - top_pct))) - 1)
    threshold = sorted_r[min(idx, len(sorted_r) - 1)] if sorted_r else 0
    return ratio >= threshold and ratio > 0


def procedure_size_outliers(rows: list[dict], *, top_percent: float = 8.0, min_procedures: int = 5) -> list[tuple[dict, ProcedureSizeRow]]:
    """
    Return (row, ProcedureSizeRow) for facilities with procedure count high relative to size.
    top_percent: flag facilities in the top X% of procedure_count/size_proxy (default top 8%).
    min_procedures: only consider facilities that list at least this many procedures.
    """
    results: list[tuple[dict, ProcedureSizeRow]] = []
    ratios: list[float] = []
    for row in rows:
        pc = _procedure_count(row)
        size = _size_proxy(row)
        ratio = pc / size if size > 0 else 0
        ratios.append(ratio)
        results.append((row, ProcedureSizeRow(
            name=(row.get("name") or "Unknown").strip(),
            facility_type=(row.get("facilityTypeId") or "").strip() or "unknown",
            procedure_count=pc,
            size_proxy=round(size, 2),
            ratio=round(ratio, 2),
            is_outlier=False,
        )))
    # Mark outliers: top top_percent% by ratio (e.g. top 8% = highest procedure/size ratio)
    sorted_by_ratio = sorted(ratios, reverse=True)
    n = len(sorted_by_ratio)
    k = max(0, min(int(n * top_percent / 100.0 + 0.5), n) - 1)
    cutoff = sorted_by_ratio[k] if k < n and n else 0
    out: list[tuple[dict, ProcedureSizeRow]] = []
    for row, rec in results:
        is_out = (rec.ratio >= cutoff and rec.procedure_count >= min_procedures and rec.ratio > 0)
        if is_out:
            out.append((row, ProcedureSizeRow(
                name=rec.name,
                facility_type=rec.facility_type,
                procedure_count=rec.procedure_count,
                size_proxy=rec.size_proxy,
                ratio=rec.ratio,
                is_outlier=True,
            )))
    return sorted(out, key=lambda x: -x[1].ratio)
