"""
External Data: Data not in the Foundational Data Refresh (FDR).
Sources can be added to the Virtue Foundation workspace or queried in real time.
"""

from pathlib import Path
from typing import Any

from src.config import DATA_DIR, PROJECT_ROOT

# Config: list of external sources (paths or URLs). Extend for real-time APIs.
EXTERNAL_SOURCES: list[dict[str, Any]] = [
    # Example: {"type": "csv", "path": PROJECT_ROOT / "data" / "external_supply.csv", "name": "supply"},
    # {"type": "url", "url": "https://example.com/api/facilities", "name": "live_api"},
    {"type": "csv", "path": Path.home() / "Desktop" / "health_indicators_gha.csv", "name": "health_indicators_gha"},
]


def list_sources() -> list[dict[str, Any]]:
    """Return configured external sources."""
    return list(EXTERNAL_SOURCES)


def load_external_sources() -> list[dict[str, Any]]:
    """
    Load all external sources that are local files.
    Returns list of {"name": str, "rows": list[dict]} or {"name": str, "error": str}.
    """
    import csv
    out = []
    for src in EXTERNAL_SOURCES:
        t = src.get("type") or "csv"
        name = src.get("name", "unknown")
        if t == "csv":
            path = src.get("path")
            if isinstance(path, str):
                path = Path(path)
            if not path or not Path(path).exists():
                out.append({"name": name, "error": f"Path not found: {path}"})
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    rows = list(csv.DictReader(f))
                out.append({"name": name, "rows": rows})
            except Exception as e:
                out.append({"name": name, "error": str(e)})
        else:
            out.append({"name": name, "error": f"Unsupported type: {t}"})
    return out


def query_external_and_merge(query: str) -> str:
    """
    Query or use external data and return an answer. If no external sources are configured,
    returns a message. Otherwise loads external data and runs a simple keyword match or
    delegates to LLM to answer from the loaded data.
    """
    sources = load_external_sources()
    if not sources:
        return "No external data sources are configured. Add paths or URLs to EXTERNAL_SOURCES in src/external_data.py (or via config) to query data outside the Foundational Data Refresh."

    errors = [s for s in sources if s.get("error")]
    data = [s for s in sources if s.get("rows")]
    if not data:
        return "External data is configured but failed to load: " + "; ".join(e.get("error", "") for e in errors)

    # Simple path: if we have rows, we could run a quick LLM answer over them
    try:
        from openai import OpenAI
        from src.config import OPENAI_API_KEY, LLM_MODEL
        if OPENAI_API_KEY and data:
            client = OpenAI(api_key=OPENAI_API_KEY)
            summary = []
            for d in data:
                rows = d.get("rows", [])[:30]
                summary.append(f"Source {d['name']}: {len(rows)} rows (sample: {list(rows[0].keys()) if rows else []})")
            text = "\n".join(summary)
            r = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You answer briefly from the provided external data summary. If the question cannot be answered from it, say so."},
                    {"role": "user", "content": f"External data summary:\n{text}\n\nQuestion: {query}"},
                ],
                max_tokens=300,
            )
            return (r.choices[0].message.content or "No response.").strip()
    except Exception as e:
        return f"External data loaded but query failed: {e}. Sources: {[d['name'] for d in data]}."

    return "External data loaded; no LLM available to answer. Configure OPENAI_API_KEY or add a custom query path in query_external_and_merge."
