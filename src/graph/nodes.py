"""LangGraph nodes: route, plan, retrieve, extract, unstructured_extract, synthesize, reason, answer. With citations and step traces."""

from typing import Any

from src.config import TOP_K_RETRIEVAL
from src.data.loaders import query_index, get_schema_text, infer_metadata_filters_from_query
from src.models import AgentState
from src.citations import (
    assign_ref_ids,
    append_step_trace,
    format_row_citations,
    format_step_traces,
)
from src.extraction import extract_medical_from_docs
from src.synthesis import synthesize_regional_capabilities
from src.planning import build_plan


def route_query(state: AgentState) -> AgentState:
    """Classify the query and set route. Record step trace."""
    query = (state.get("query") or "").strip().lower()
    route = "rag"
    if any(x in query for x in ["lack", "gap", "missing", "without", "which region", "where is there no"]):
        route = "gaps"
    elif any(x in query for x in ["verify", "really do", "can .* actually", "claim"]):
        route = "verify"
    elif any(x in query for x in ["medical desert", "underserved", "no hospital", "access risk"]):
        route = "deserts"
    elif any(x in query for x in ["list", "find", "facilities with", "where can", "who has"]):
        route = "rag"
    reasoning = [f"Routed to: {route}"]
    traces = append_step_trace(
        state.get("step_traces") or [],
        step_id=1,
        step_name="route",
        citation_refs=[],
        inputs_summary=f"query: {state.get('query', '')[:80]}",
        outputs_summary=f"route={route}",
    )
    return {"route": route, "reasoning": reasoning, "step_traces": traces}


def plan_step(state: AgentState) -> AgentState:
    """Produce a short plan (human-readable steps) for transparency."""
    route = state.get("route") or "rag"
    query = state.get("query") or ""
    plan = build_plan(query, route)
    traces = append_step_trace(
        state.get("step_traces") or [],
        step_id=2,
        step_name="plan",
        citation_refs=[],
        inputs_summary=f"route={route}",
        outputs_summary=f"{len(plan)} steps",
    )
    return {"plan": plan, "step_traces": traces}


def retrieve(state: AgentState) -> AgentState:
    """Retrieve relevant chunks (vector search + optional metadata filtering); assign ref IDs and row citations."""
    query = state.get("query") or ""
    metadata_filters = infer_metadata_filters_from_query(query)
    try:
        docs = query_index(query, top_k=TOP_K_RETRIEVAL, metadata_filters=metadata_filters or None)
    except Exception as e:
        traces = append_step_trace(
            state.get("step_traces") or [],
            step_id=3,
            step_name="retrieve",
            citation_refs=[],
            outputs_summary=f"error: {e}",
        )
        return {"retrieved_docs": [], "row_citations": [], "error": str(e), "step_traces": traces}
    docs, row_citations = assign_ref_ids(docs)
    refs = [c["ref_id"] for c in row_citations]
    reasoning = (state.get("reasoning") or []) + [f"Retrieved {len(docs)} chunks (refs {refs})."]
    traces = append_step_trace(
        state.get("step_traces") or [],
        step_id=3,
        step_name="retrieve",
        citation_refs=refs,
        inputs_summary=f"query: {query[:60]}",
        outputs_summary=f"{len(docs)} docs, refs {refs}",
    )
    return {"retrieved_docs": docs, "row_citations": row_citations, "reasoning": reasoning, "step_traces": traces}


def extract_facilities(state: AgentState) -> AgentState:
    """Turn retrieved docs into facility-like dicts. Record step trace."""
    docs = state.get("retrieved_docs") or []
    facilities = []
    for d in docs:
        meta = d.get("metadata") or {}
        name = meta.get("name") or meta.get("facility") or meta.get("organization") or "Unknown"
        facilities.append({
            "name": name,
            "text": d.get("text", ""),
            "metadata": meta,
            "source_ref": meta.get("source", ""),
            "ref_id": d.get("ref_id"),
        })
    refs = [d.get("ref_id") for d in docs if d.get("ref_id")]
    reasoning = (state.get("reasoning") or []) + [f"Extracted {len(facilities)} facility references."]
    traces = append_step_trace(
        state.get("step_traces") or [],
        step_id=4,
        step_name="extract_facilities",
        citation_refs=refs,
        outputs_summary=f"{len(facilities)} facilities",
    )
    return {"facilities": facilities, "reasoning": reasoning, "step_traces": traces}


def unstructured_extract(state: AgentState) -> AgentState:
    """Unstructured feature extraction: procedure, equipment, capability from each doc. Record step trace."""
    docs = state.get("retrieved_docs") or []
    extracted_medical = extract_medical_from_docs(docs)
    refs = [d.get("ref_id") for d in docs if d.get("ref_id")]
    reasoning = (state.get("reasoning") or []) + ["Extracted procedures, equipment, capabilities from free-form text."]
    traces = append_step_trace(
        state.get("step_traces") or [],
        step_id=5,
        step_name="unstructured_extract",
        citation_refs=refs,
        outputs_summary=f"{len(extracted_medical)} records with medical features",
    )
    return {"extracted_medical": extracted_medical, "reasoning": reasoning, "step_traces": traces}


def synthesize(state: AgentState) -> AgentState:
    """Intelligent synthesis: regional capabilities view from extracted + schema. Record step trace."""
    extracted_medical = state.get("extracted_medical") or []
    facilities = state.get("facilities") or []
    schema_context = get_schema_text()
    synthesis = synthesize_regional_capabilities(extracted_medical, facilities, schema_context)
    refs = list({e.get("ref_id") for e in extracted_medical if e.get("ref_id")})
    reasoning = (state.get("reasoning") or []) + ["Synthesized regional view from unstructured + structured data."]
    traces = append_step_trace(
        state.get("step_traces") or [],
        step_id=6,
        step_name="synthesize",
        citation_refs=refs,
        outputs_summary=f"{len(synthesis.get('by_region', {}))} regions",
    )
    return {"synthesis": synthesis, "reasoning": reasoning, "step_traces": traces}


def reason_over_data(state: AgentState) -> AgentState:
    """Reason over facilities for gaps/deserts/verify. Record step trace."""
    route = state.get("route") or "rag"
    query = state.get("query") or ""
    facilities = state.get("facilities") or []
    synthesis = state.get("synthesis") or {}
    reasoning = list(state.get("reasoning") or [])
    refs = [f.get("ref_id") for f in facilities if f.get("ref_id")]

    if route == "gaps":
        by_region = synthesis.get("by_region", {})
        query_lower = query.lower()
        gaps = []
        for region, data in by_region.items():
            procs = " ".join(data.get("procedures", [])).lower()
            caps = " ".join(data.get("capabilities", [])).lower()
            combined = procs + " " + caps
            if not combined.strip():
                gaps.append({"region": region, "missing_capability": query, "facilities_with_capability_elsewhere": []})
            else:
                words = [w for w in query_lower.split() if len(w) > 3]
                if words and not any(w in combined for w in words):
                    gaps.append({"region": region, "missing_capability": query, "facilities_with_capability_elsewhere": data.get("facilities", [])[:5]})
        reasoning.append("Computed gap regions from synthesis.")
        traces = append_step_trace(
            state.get("step_traces") or [],
            step_id=7,
            step_name="reason",
            citation_refs=refs,
            outputs_summary=f"{len(gaps)} gaps",
        )
        return {"gaps": gaps[:15], "reasoning": reasoning, "step_traces": traces}

    if route == "deserts":
        # Desert analysis: regions with no capability and no facility within 20 km
        query_lower = query.lower()
        stop = {"which", "where", "what", "have", "with", "lack", "lacking", "without", "no", "the", "and", "for", "within", "km", "care"}
        words = [w for w in query_lower.split() if len(w) > 3 and w not in stop]
        capability_label = " ".join(words) if words else query
        deserts: list[dict[str, Any]] = []

        # 1) Regions with zero facilities for a capability (from synthesis)
        by_region = synthesis.get("by_region") or {}
        for region, data in by_region.items():
            procs = " ".join(data.get("procedures", [])).lower()
            caps = " ".join(data.get("capabilities", [])).lower()
            combined = (procs + " " + caps).strip()
            if not combined:
                deserts.append({"region": region, "missing_capability": capability_label, "facilities_with_capability_elsewhere": []})
            elif words and not any(w in combined for w in words):
                deserts.append({"region": region, "missing_capability": capability_label, "facilities_with_capability_elsewhere": data.get("facilities", [])[:5]})

        # 2) Regions with no facility within 20 km (geodesic distance), when coords exist
        try:
            from query_local import load_csv, search_rows
            from src.geo import haversine_km, get_row_coords
            _name, rows = load_csv(prefer_geocoded=True)
            cap_rows = search_rows(rows, words or [capability_label], facility_type=None, query=query)
            cap_coords = [get_row_coords(r) for r in cap_rows]
            cap_coords = [c for c in cap_coords if c]
            if cap_coords:
                # group facility coords by region
                region_coords: dict[str, list[tuple[float, float]]] = {}
                for r in rows:
                    coord = get_row_coords(r)
                    if not coord:
                        continue
                    region = (r.get("address_stateOrRegion") or r.get("address_city") or "Unknown").strip() or "Unknown"
                    region_coords.setdefault(region, []).append(coord)
                for region, coords in region_coords.items():
                    # if no coord is within 20 km of any capability facility, mark desert
                    within = False
                    for c in coords:
                        if any(haversine_km(c[0], c[1], cc[0], cc[1]) <= 20.0 for cc in cap_coords):
                            within = True
                            break
                    if not within:
                        deserts.append({"region": region, "missing_capability": f"{capability_label} within 20 km", "facilities_with_capability_elsewhere": []})
        except Exception:
            pass

        reasoning.append("Computed medical desert regions (zero capability or no facility within 20 km).")
        traces = append_step_trace(
            state.get("step_traces") or [],
            step_id=7,
            step_name="reason",
            citation_refs=refs,
            outputs_summary=f"{len(deserts)} deserts",
        )
        return {"gaps": deserts[:15], "reasoning": reasoning, "step_traces": traces}
    else:
        reasoning.append("RAG: using retrieved facilities and synthesis as evidence.")
    traces = append_step_trace(
        state.get("step_traces") or [],
        step_id=7,
        step_name="reason",
        citation_refs=refs,
        outputs_summary=route,
    )
    return {"reasoning": reasoning, "step_traces": traces}


def generate_answer(state: AgentState) -> AgentState:
    """Produce final answer with row-level and step-level citations. Record step trace."""
    from src.config import OPENAI_API_KEY
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    query = state.get("query") or ""
    route = state.get("route") or "rag"
    facilities = state.get("facilities") or []
    gaps = state.get("gaps") or []
    synthesis = state.get("synthesis") or {}
    reasoning = state.get("reasoning") or []
    row_citations = state.get("row_citations") or []
    step_traces = state.get("step_traces") or []
    plan = state.get("plan") or []

    context_parts = []
    if synthesis.get("by_region"):
        context_parts.append("Regional capabilities (synthesis):\n" + "\n".join(
            f"- {r}: {list(d.get('procedures', [])[:2])} {list(d.get('capabilities', [])[:2])}"
            for r, d in list(synthesis["by_region"].items())[:10]
        ))
    if facilities:
        context_parts.append("Retrieved facilities (with ref IDs):\n" + "\n---\n".join(
            f"[{f.get('ref_id')}] {f.get('name', '')}: {f.get('text', '')[:250]}"
            for f in facilities[:8]
        ))
    if gaps:
        context_parts.append("Gaps:\n" + "\n".join(
            f"- {g.get('region', '')}: missing {g.get('missing_capability', '')}"
            for g in gaps
        ))
    context = "\n\n".join(context_parts) or "No context."
    sys = (
        "You are an IDP medical agent. Use the context to answer. "
        "When you mention a facility or finding, cite the ref ID in square brackets, e.g. [1], [2]. "
        "Be concise. Say where care exists and where it is missing."
    )
    user = f"Context:\n{context}\n\nUser query: {query}"

    if OPENAI_API_KEY:
        try:
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, timeout=15, max_retries=1)
            out = llm.invoke([SystemMessage(content=sys), HumanMessage(content=user)])
            final = out.content if hasattr(out, "content") else str(out)
        except Exception as e:
            final = f"Error: {e}. Reasoning: {'; '.join(reasoning)}."
    else:
        final = f"Route: {route}. Facilities: {len(facilities)}. Gaps: {len(gaps)}. Set OPENAI_API_KEY for full answer."

    refs_used = list({f.get("ref_id") for f in facilities if f.get("ref_id")})
    traces = append_step_trace(
        step_traces,
        step_id=8,
        step_name="answer",
        citation_refs=refs_used,
        outputs_summary=f"answer length {len(final)}",
    )

    if plan:
        final = "**Plan:**\n" + "\n".join(plan) + "\n\n---\n\n**Answer:**\n" + final
    final = final + "\n\n" + format_row_citations(row_citations)
    final = final + "\n\n" + format_step_traces(traces)

    return {"final_answer": final, "step_traces": traces}
