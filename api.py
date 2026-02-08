#!/usr/bin/env python3
"""
IDP Medical Agent – REST API for use with any frontend (e.g. Lovable, React, Vue).
Run: uvicorn api:app --reload --host 0.0.0.0 --port 8000
Then the frontend calls POST /api/query, POST /api/chat, GET /api/guided-options, etc.
"""

import sys
from pathlib import Path

# Ensure project root is on path (same as main.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="IDP Medical Agent API",
    description="Backend for Ghana facility queries: single query, chat, guided options. Use with any frontend (e.g. Lovable).",
    version="1.0.0",
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
    message: str = Field(..., min_length=1)
    session_id: str | None = None  # optional; frontend can manage session


class ChatMessageResponse(BaseModel):
    reply: str
    intent: str | None = None
    sub_agent: str | None = None


# --- In-memory chat session (optional; frontend can also manage history)
_chat_sessions: dict[str, list[dict]] = {}


def _run_query(query: str) -> tuple[str, str | None, str | None, bool]:
    """Run query through Supervisor; return (answer, intent, sub_agent, used_medical_reasoning)."""
    from src.agents.supervisor import classify_intent, dispatch, should_use_medical_reasoning
    result = classify_intent(query)
    use_med = should_use_medical_reasoning(query, result["intent"], result["sub_agent"])
    answer = dispatch(query, result["sub_agent"], use_medical_reasoning=use_med)
    return answer, result.get("intent"), result.get("sub_agent"), use_med


# --- Endpoints ---

@app.get("/api/health")
def health():
    """Health check for load balancers / frontend."""
    return {"status": "ok", "service": "idp-medical-agent"}


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """Single-shot question. Use this for one-off queries from your UI."""
    try:
        answer, intent, sub_agent, use_med = _run_query(req.query.strip())
        return QueryResponse(
            answer=answer,
            intent=intent,
            sub_agent=sub_agent,
            used_medical_reasoning=use_med,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatMessageResponse)
def chat(req: ChatMessageRequest):
    """One chat turn. Frontend can send each user message here; optional session_id for server-side history (not required)."""
    try:
        from genie_chat import answer_query
        reply = answer_query(req.message.strip(), use_supervisor=True)
        from src.agents.supervisor import classify_intent
        result = classify_intent(req.message.strip())
        return ChatMessageResponse(
            reply=reply,
            intent=result.get("intent"),
            sub_agent=result.get("sub_agent"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/guided-options")
def guided_options():
    """Return the guided planning menu options (for building a UI menu instead of CLI)."""
    from src.planning import GUIDED_OPTIONS
    return {"options": GUIDED_OPTIONS}


@app.post("/api/guided-query", response_model=QueryResponse)
def guided_query(req: QueryRequest):
    """Run a query that was built from the guided menu (e.g. 'Which regions lack dialysis?'). Same as /api/query."""
    return query(req)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
