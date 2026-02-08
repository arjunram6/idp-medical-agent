"""Data models for facilities and agent state."""

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class FacilityCapability(BaseModel):
    """A single capability or procedure attributed to a facility."""
    name: str
    category: Literal["capability", "procedure", "equipment", "specialty"] = "capability"
    raw_text: str = ""
    confidence: float = 1.0


class MedicalFacility(BaseModel):
    """Structured view of a medical facility from extracted data."""
    name: str
    facility_id: str = ""
    addresses: list[str] = Field(default_factory=list)
    capabilities: list[FacilityCapability] = Field(default_factory=list)
    contact: dict[str, list[str]] = Field(default_factory=dict)
    capacity: dict[str, int | None] = Field(default_factory=lambda: {"beds": None, "doctors": None})
    region: str = ""
    source_ref: str = ""
    raw_excerpt: str = ""


class GapResult(BaseModel):
    """A region or area lacking a specific capability."""
    region: str
    missing_capability: str
    facilities_with_capability_elsewhere: list[str] = Field(default_factory=list)


# --- Citations & tracing (row-level + step-level) ---


class RowCitation(TypedDict, total=False):
    """Row-level citation: which data supported a claim."""
    ref_id: int
    source: str
    row_id: str
    row_name: str
    fields_used: list[str]
    excerpt: str


class StepTrace(TypedDict, total=False):
    """Agentic-step trace: which step used which data (for transparency)."""
    step_id: int
    step_name: str
    citation_refs: list[int]
    inputs_summary: str
    outputs_summary: str


class AgentState(TypedDict, total=False):
    """State passed through the LangGraph pipeline (partial updates allowed)."""
    query: str
    route: str
    plan: list[str]
    messages: list[dict[str, Any]]
    retrieved_docs: list[dict[str, Any]]
    facilities: list[dict[str, Any]]
    extracted_medical: list[dict[str, Any]]
    synthesis: dict[str, Any]
    gaps: list[dict[str, Any]]
    reasoning: list[str]
    row_citations: list[dict[str, Any]]
    step_traces: list[dict[str, Any]]
    final_answer: str
    error: str
