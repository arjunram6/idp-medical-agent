"""
Row-level and step-level citations + tracing.
- Row citations: which source row/fields supported each claim.
- Step traces: which data each agent step used (inputs/outputs summary + citation refs).
"""

from typing import Any


def assign_ref_ids(docs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Assign ref IDs to retrieved docs and build row_citations. Returns (docs_with_refs, row_citations)."""
    citations = []
    for i, d in enumerate(docs, 1):
        meta = d.get("metadata") or {}
        citations.append({
            "ref_id": i,
            "source": meta.get("source", "unknown"),
            "row_id": str(meta.get("row_id", meta.get("pk_unique_id", i))),
            "row_name": (meta.get("name") or "Unknown")[:80],
            "fields_used": _infer_fields_from_text(d.get("text", "")),
            "excerpt": (d.get("text", "")[:200] + "..." if len(d.get("text", "")) > 200 else d.get("text", "")),
        })
        d["ref_id"] = i
    return docs, citations


def _infer_fields_from_text(text: str) -> list[str]:
    """Infer which columns likely contributed (procedure, equipment, capability, etc.)."""
    if not text:
        return []
    t = text.lower()
    out = []
    for field in ["name", "description", "capability", "procedure", "equipment", "specialties", "address_city", "region"]:
        if field.replace("_", " ") in t or field in t:
            out.append(field)
    return out[:6] or ["text"]


def append_step_trace(
    step_traces: list[dict],
    step_id: int,
    step_name: str,
    citation_refs: list[int],
    inputs_summary: str = "",
    outputs_summary: str = "",
) -> list[dict]:
    """Append a step trace for transparency."""
    step_traces = list(step_traces or [])
    step_traces.append({
        "step_id": step_id,
        "step_name": step_name,
        "citation_refs": citation_refs,
        "inputs_summary": inputs_summary,
        "outputs_summary": outputs_summary,
    })
    return step_traces


def format_row_citations(citations: list[dict]) -> str:
    """Format row citations for display: [ref_id] row_name (fields)."""
    if not citations:
        return ""
    lines = ["**References:**"]
    for c in citations:
        ref = c.get("ref_id", "?")
        name = c.get("row_name", "—")
        fields = ", ".join(c.get("fields_used", [])[:5])
        lines.append(f"  [{ref}] {name} — {fields}")
    return "\n".join(lines)


def format_step_traces(step_traces: list[dict]) -> str:
    """Format step-level citations: which step used which refs."""
    if not step_traces:
        return ""
    lines = ["**Step-level citations:**"]
    for t in step_traces:
        step_name = t.get("step_name", "?")
        refs = t.get("citation_refs", [])
        ref_str = ", ".join(f"[{r}]" for r in refs) if refs else "—"
        lines.append(f"  {t.get('step_id', '?')}. {step_name}: used {ref_str}")
    return "\n".join(lines)


def format_trace_for_experiment(traces: list[dict]) -> dict[str, Any]:
    """Produce a single dict suitable for experiment tracking (e.g. log to file or MLflow)."""
    return {
        "steps": [
            {
                "step_id": t.get("step_id"),
                "step_name": t.get("step_name"),
                "citation_refs": t.get("citation_refs"),
                "inputs": t.get("inputs_summary"),
                "outputs": t.get("outputs_summary"),
            }
            for t in (traces or [])
        ],
    }
