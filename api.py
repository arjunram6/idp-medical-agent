#!/usr/bin/env python3
"""
IDP Medical Agent – REST API for use with any frontend (e.g. Lovable, React, Vue).
Run: uvicorn api:app --reload --host 0.0.0.0 --port 8000
Then the frontend calls POST /api/query, POST /api/chat, GET /api/guided-options, etc.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project root is on path (same as main.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import OPENAI_API_KEY

API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT_SECONDS", "55"))
PREBUILD_INDEX = os.getenv("PREBUILD_INDEX", "true").lower() in ("1", "true", "yes", "y")

app = FastAPI(
    title="IDP Medical Agent API",
    description="Backend for Ghana facility queries: single query, chat, guided options. Use with any frontend (e.g. Lovable).",
    version="1.0.1",
)

# Allow any frontend origin (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response models ---

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language question")


class QueryResponse(BaseModel):
    answer: str
    intent: str | None = None
    sub_agent: str | None = None
    used_medical_reasoning: bool = False


class ChatMessageRequest(BaseModel):
    message: str | None = Field(None, min_length=1)
    query: str | None = Field(None, min_length=1)
    session_id: str | None = None  # optional; frontend can manage session

    @staticmethod
    def _pick_message(message: str | None, query: str | None) -> str | None:
        return (message or "").strip() or (query or "").strip() or None

    def get_message(self) -> str:
        msg = self._pick_message(self.message, self.query)
        if not msg:
            raise ValueError("Chat message must not be empty.")
        return msg


class ChatMessageResponse(BaseModel):
    reply: str
    intent: str | None = None
    sub_agent: str | None = None


def _run_query(query: str) -> tuple[str, str | None, str | None, bool]:
    """Run query through Supervisor; return (answer, intent, sub_agent, used_medical_reasoning)."""
    from src.agents.supervisor import classify_intent, dispatch, should_use_medical_reasoning

    q = (query or "").strip()
    if not q:
        raise ValueError("Query must not be empty.")

    result = classify_intent(q)
    intent = result.get("intent")
    sub_agent = result.get("sub_agent")
    use_med = should_use_medical_reasoning(q, intent, sub_agent)

    if sub_agent == "rag" and not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set; this query requires RAG/LLM.")

    answer = dispatch(q, sub_agent, use_medical_reasoning=use_med)
    if not answer:
        raise ValueError("No answer generated for this query.")

    return answer, intent, sub_agent, use_med


def _run_query_with_timeout(query: str, timeout_seconds: int = API_TIMEOUT_SECONDS):
    """Run query with a timeout to avoid long-hanging requests."""
    if timeout_seconds <= 0:
        return _run_query(query)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_query, query)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as e:
            raise ValueError(f"Query timed out after {timeout_seconds}s.") from e


# --- Endpoints ---

@app.on_event("startup")
def _startup() -> None:
    """Prebuild vector index to avoid long first request."""
    if not PREBUILD_INDEX:
        return
    try:
        from src.config import STORAGE_DIR
        from src.data.loaders import build_index, load_documents
        try:
            build_index(None, persist_dir=STORAGE_DIR)
        except Exception:
            docs = load_documents()
            build_index(docs, persist_dir=STORAGE_DIR)
    except Exception:
        # Startup should not crash the server; query path can rebuild on demand
        pass

@app.get("/api/health")
def health():
    """Health check for load balancers / frontend."""
    return {"status": "ok", "service": "idp-medical-agent"}


@app.get("/health")
def health_legacy():
    return health()


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """Single-shot question. Use this for one-off queries from your UI."""
    try:
        answer, intent, sub_agent, use_med = _run_query_with_timeout(req.query)
        return QueryResponse(
            answer=answer,
            intent=intent,
            sub_agent=sub_agent,
            used_medical_reasoning=use_med,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {e}")


@app.post("/query", response_model=QueryResponse)
def query_legacy(req: QueryRequest):
    return query(req)


@app.post("/api/chat", response_model=ChatMessageResponse)
def chat(req: ChatMessageRequest):
    """One chat turn. Frontend can send each user message here; optional session_id for server-side history (not required)."""
    try:
        reply, intent, sub_agent, _ = _run_query_with_timeout(req.get_message())
        return ChatMessageResponse(reply=reply, intent=intent, sub_agent=sub_agent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {e}")


@app.get("/api/guided-options")
def guided_options():
    """Return the guided planning menu options (for building a UI menu instead of CLI)."""
    from src.planning import GUIDED_OPTIONS
    return {"options": GUIDED_OPTIONS}


@app.post("/api/guided-query", response_model=QueryResponse)
def guided_query(req: QueryRequest):
    """Run a query that was built from the guided menu (e.g. 'Which regions lack dialysis?'). Same as /api/query."""
    return query(req)


@app.get("/api/regions/summary")
def regions_summary() -> dict[str, Any]:
    """Regional capabilities summary across all facilities."""
    try:
        from src.data.loaders import load_documents, get_schema_text
        from src.extraction import extract_medical_from_docs
        from src.synthesis import synthesize_regional_capabilities

        docs = load_documents()
        if not docs:
            raise HTTPException(status_code=404, detail="No data files found (CSV/TXT missing).")

        doc_dicts: list[dict[str, Any]] = []
        facilities: list[dict[str, Any]] = []
        for d in docs:
            meta = getattr(d, "metadata", {}) or {}
            if meta.get("type") == "schema":
                continue
            if hasattr(d, "get_content"):
                text = d.get_content()
            else:
                text = getattr(d, "text", "")
            doc_dicts.append({"text": text, "metadata": meta})
            facilities.append({"name": meta.get("name", "Unknown"), "metadata": meta})

        extracted = extract_medical_from_docs(doc_dicts)
        summary = synthesize_regional_capabilities(extracted, facilities, schema_context=get_schema_text())
        return {
            "summary": summary,
            "regions_count": len(summary.get("by_region", {})),
            "total_procedures": len(summary.get("all_procedures", [])),
            "total_equipment": len(summary.get("all_equipment", [])),
            "total_capabilities": len(summary.get("all_capabilities", [])),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Regions summary error: {e}")


@app.get("/regions/summary")
def regions_summary_legacy() -> dict[str, Any]:
    return regions_summary()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
