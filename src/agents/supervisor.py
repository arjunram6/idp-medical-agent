"""
Supervisor Agent: Recognizes intent and delegates user queries to the appropriate sub-agent.
Sub-agents: local_csv, geospatial, text_to_sql, rag, medical_reasoning, external_data.
Medical Reasoning is auto-enabled when the question purpose is verification, risk, clinical care, or data quality.
"""

from typing import TypedDict


def should_use_medical_reasoning(query: str, intent: str, sub_agent: str) -> bool:
    """
    Return True when the question's core purpose benefits from medical context or reasoning.
    Used to run Medical Reasoning Agent without the user having to pass a flag.
    """
    q = (query or "").strip().lower()
    if any(x in q for x in ("risk", "tier", "verification", "unrealistic", "data quality", "data completeness")):
        return True
    if any(x in q for x in ("claim", "lack", "regions lack", "procedures relative")):
        return True
    if any(x in q for x in ("abnormal patterns", "mismatch", "correlated features", "features don't match", "inconsistent")):
        return True
    if any(x in q for x in ("where should i", "where can i go", "i'm pregnant", "i am pregnant", "need care", "recommend", "best place")):
        return True
    # Regional medical prominence / specialties (use RAG + Medical Reasoning)
    if any(x in q for x in ("prominent", "type of medicine", "which medicine", "specialties by region", "more common in", "what medicine", "what care")):
        return True
    return False


class SupervisorResult(TypedDict):
    intent: str
    sub_agent: str
    confidence: str
    hint: str


def _warrants_text_to_sql(query: str) -> bool:
    """True when the question is analytical/SQL-style and warrants Genie text-to-SQL."""
    q = (query or "").strip().lower()
    if " as sql" in q or " sql query" in q or "convert to sql" in q:
        return True
    # Analytical: count by, group by, aggregate, total, sum, average
    if any(x in q for x in ("count by", "group by", "total number of", "aggregate", "sum of", "average number")):
        return True
    if "by region" in q or "by type" in q or "by facility type" in q:
        return True
    return False


def _warrants_external_data(query: str) -> bool:
    """True when the question is about data outside FDR."""
    q = (query or "").strip().lower()
    return any(
        x in q
        for x in (
            "external data",
            "not in the data",
            "not in FDR",
            "real-time",
            "live data",
            "outside FDR",
            "outside the data",
            "foundational data refresh",
        )
    )


def _warrants_geospatial(query: str) -> bool:
    """True when the question warrants geodesic/distance calculation."""
    q = (query or "").strip().lower()
    return "within" in q and "km" in q and " of " in q


def classify_intent(query: str) -> SupervisorResult:
    """
    Classify user query and return which sub-agent should handle it.
    All routing is by question intent; no user prompt required.
    Returns: { intent, sub_agent, confidence, hint }.
    """
    q = (query or "").strip().lower()

    # Geospatial: geodesic distance (within X km of Y)
    if _warrants_geospatial(query):
        return {
            "intent": "geospatial_distance",
            "sub_agent": "geospatial",
            "confidence": "high",
            "hint": "Geospatial: geodesic distance (Haversine); prefers geocoded CSV.",
        }

    # Text-to-SQL (Genie): plaintext English → SQL when analytical
    if _warrants_text_to_sql(query):
        return {
            "intent": "text_to_sql",
            "sub_agent": "text_to_sql",
            "confidence": "high",
            "hint": "Genie text-to-SQL: convert to SQL and run (DuckDB or Databricks).",
        }

    # External data: outside FDR
    if _warrants_external_data(query):
        return {
            "intent": "external_data",
            "sub_agent": "external_data",
            "confidence": "medium",
            "hint": "External data: outside Foundational Data Refresh; add to workspace or query in real time.",
        }

    # Regional prominence / type of medicine (needs RAG synthesis + LLM, not just local filter)
    if any(x in q for x in ("prominent", "type of medicine", "which medicine", "more common in", "what medicine", "what care", "specialties by region")):
        return {
            "intent": "rag_regional_prominence",
            "sub_agent": "rag",
            "confidence": "medium",
            "hint": "RAG: regional synthesis + LLM for prominence / type of medicine by region.",
        }

    # Local CSV: counts, locations, services, gaps, risk, unrealistic procedures
    try:
        from query_local import can_handle_locally
        if can_handle_locally(query):
            return {
                "intent": "local_facility_query",
                "sub_agent": "local_csv",
                "confidence": "high",
                "hint": "Answer from Ghana CSV + scheme (no LLM).",
            }
    except Exception:
        pass

    # Default: RAG = vector search with optional metadata filtering
    return {
        "intent": "rag_semantic",
        "sub_agent": "rag",
        "confidence": "medium",
        "hint": "Vector search on plaintext + metadata-based filtering; synthesize and cite.",
    }


def dispatch(query: str, sub_agent: str, *, use_medical_reasoning: bool = False) -> str:
    """
    Run the appropriate sub-agent and return answer text.
    If use_medical_reasoning, wrap with Medical Reasoning Agent (enhance query / reason over results).
    """
    from src.agents import medical_reasoning
    if use_medical_reasoning:
        query = medical_reasoning.enhance_query(query) or query

    if sub_agent == "local_csv" or sub_agent == "geospatial":
        import io
        from query_local import run_query
        buf = io.StringIO()
        run_query(query, buf)
        out = buf.getvalue()
    elif sub_agent == "text_to_sql":
        from src.agents.text_to_sql import run_text_to_sql
        out = run_text_to_sql(query)
    elif sub_agent == "external_data":
        from src.external_data import query_external_and_merge
        out = query_external_and_merge(query)
    else:
        # rag
        from src.config import STORAGE_DIR
        from src.data.loaders import load_documents, build_index
        from src.graph.pipeline import run_agent
        try:
            build_index(None, persist_dir=STORAGE_DIR)
        except Exception:
            docs = load_documents()
            build_index(docs, persist_dir=STORAGE_DIR)
        result = run_agent(query)
        out = result.get("final_answer", result.get("error", "No output."))
        if use_medical_reasoning:
            out = medical_reasoning.reason_over_results(query, out) or out
        return out

    if use_medical_reasoning:
        out = medical_reasoning.reason_over_results(query, out) or out
    return out
