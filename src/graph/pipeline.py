"""LangGraph pipeline: route -> plan -> retrieve -> extract -> unstructured_extract -> synthesize -> reason -> answer. With citations and tracing."""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.models import AgentState
from src.graph.nodes import (
    route_query,
    plan_step,
    retrieve,
    extract_facilities,
    unstructured_extract,
    synthesize,
    reason_over_data,
    generate_answer,
)
from src.citations import format_trace_for_experiment


def create_graph(checkpointer=None):
    """Build the agent graph (MVP: extraction, synthesis, plan, citations, step traces)."""
    builder = StateGraph(AgentState)

    builder.add_node("route", route_query)
    builder.add_node("plan", plan_step)
    builder.add_node("retrieve", retrieve)
    builder.add_node("extract", extract_facilities)
    builder.add_node("unstructured_extract", unstructured_extract)
    builder.add_node("synthesize", synthesize)
    builder.add_node("reason", reason_over_data)
    builder.add_node("answer", generate_answer)

    builder.set_entry_point("route")
    builder.add_edge("route", "plan")
    builder.add_edge("plan", "retrieve")
    builder.add_edge("retrieve", "extract")
    builder.add_edge("extract", "unstructured_extract")
    builder.add_edge("unstructured_extract", "synthesize")
    builder.add_edge("synthesize", "reason")
    builder.add_edge("reason", "answer")
    builder.add_edge("answer", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())


def run_agent(query: str, graph=None) -> dict:
    """Run the agent; return final state including citations and step traces."""
    if graph is None:
        graph = create_graph()
    config = {"configurable": {"thread_id": "default"}}
    initial: AgentState = {"query": query}
    result = graph.invoke(initial, config=config)
    traces = result.get("step_traces") or []
    return {
        "query": result.get("query"),
        "route": result.get("route"),
        "plan": result.get("plan"),
        "final_answer": result.get("final_answer"),
        "reasoning": result.get("reasoning"),
        "facilities_count": len(result.get("facilities") or []),
        "gaps_count": len(result.get("gaps") or []),
        "row_citations": result.get("row_citations"),
        "step_traces": traces,
        "trace_export": format_trace_for_experiment(traces),
        "synthesis": result.get("synthesis"),
        "error": result.get("error"),
    }
