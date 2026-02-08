#!/usr/bin/env python3
"""
IDP Medical Agent – entrypoint.
Architecture runs by default (no prompt): Supervisor routes by intent; Genie, geospatial,
Medical Reasoning, external data, and vector search with filtering are used when the question warrants it.

Run: python main.py "Which regions lack dialysis?"
      python main.py --chat     # Genie Chat (same architecture per message)
      python main.py --guided   # menu-driven planning
      python main.py --no-supervisor "query"   # skip supervisor (direct path)
Requires: data in ./data or Desktop (Ghana CSV + Scheme TXT); OPENAI_API_KEY for RAG + Medical Reasoning.
"""

import argparse
import io
import json
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import DATA_DIR, STORAGE_DIR
from src.data.loaders import load_documents, build_index
from src.graph.pipeline import run_agent

PROJECT_ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="IDP Medical Agent")
    parser.add_argument("query", nargs="*", help="Your question (or use --guided)")
    parser.add_argument("--guided", action="store_true", help="Use guided planning menu")
    parser.add_argument("--chat", action="store_true", help="Genie Chat (multi-turn conversation)")
    parser.add_argument("--trace", metavar="QUERY", help="Run query and write step trace to trace.json")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild of vector index (ignore cache)")
    parser.add_argument("--no-supervisor", action="store_true", help="Skip supervisor; run query directly (local or RAG). Default is to use supervisor.")
    parser.add_argument("--medical-reasoning", action="store_true", help="Force Medical Reasoning Agent on (add context, reason over results)")
    parser.add_argument("--no-medical-reasoning", action="store_true", help="Disable auto Medical Reasoning even when question purpose warrants it")
    parser.add_argument("--risk", action="store_true", help="Show risk categories summary (0-100 score, tier A/B/C/D)")
    parser.add_argument("--risk-export", metavar="CSV", help="Export risk scores to CSV (name, risk_score, completeness_score, tier, risk_band)")
    args = parser.parse_args()

    if args.risk or args.risk_export:
        from query_local import load_csv
        from src.risk_rating import compute_risk_all, risk_summary
        _name, rows = load_csv()
        if not rows:
            print("No Ghana CSV found in data/ or Desktop.")
            return
        if args.risk_export:
            import csv
            results = compute_risk_all(rows)
            out_path = Path(args.risk_export)
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["name", "risk_score", "completeness_score", "tier", "risk_band", "risk_color", "critical_missing", "moderate_missing"])
                for row, res in results:
                    w.writerow([
                        (row.get("name") or "").strip(),
                        res.risk_score,
                        res.completeness_score,
                        res.tier,
                        res.risk_band,
                        res.risk_color,
                        ";".join(res.critical_missing),
                        ";".join(res.moderate_missing),
                    ])
            print(f"Exported risk scores for {len(results)} facilities to {out_path}")
        else:
            from query_local import run_query
            print(run_query("risk categories and data completeness", io.StringIO()))
        return

    if args.guided:
        from run_guided import main as guided_main
        return guided_main()
    if args.chat:
        from genie_chat import main as chat_main
        return chat_main()

    query = " ".join(args.query) if args.query else (args.trace or "Where are facilities with maternity care?")
    if args.trace:
        query = args.trace

    # Default: run through Supervisor (classify intent → dispatch). Use Medical Reasoning when question purpose warrants it.
    use_supervisor = not args.no_supervisor
    if use_supervisor:
        from src.agents.supervisor import classify_intent, dispatch, should_use_medical_reasoning
        result = classify_intent(query)
        use_med = args.medical_reasoning or (not args.no_medical_reasoning and should_use_medical_reasoning(query, result["intent"], result["sub_agent"]))
        if use_med:
            print(f"Intent: {result['intent']} → {result['sub_agent']} (+ Medical Reasoning)\n")
        else:
            print(f"Intent: {result['intent']} → {result['sub_agent']} ({result['confidence']})\n")
        answer = dispatch(query, result["sub_agent"], use_medical_reasoning=use_med)
        print(answer)
        return

    # --no-supervisor: direct path (legacy)
    from query_local import can_handle_locally, run_query
    if can_handle_locally(query):
        output = run_query(query, io.StringIO())
        print(output)
        return

    print(f"Query: {query}\n")

    # Build or load cached vector index (reuse storage to avoid re-embedding every run)
    if args.rebuild and STORAGE_DIR.exists():
        import shutil
        shutil.rmtree(STORAGE_DIR, ignore_errors=True)
    if not args.rebuild and STORAGE_DIR.exists():
        try:
            build_index(None, persist_dir=STORAGE_DIR)
            print("Using cached index (storage/).")
        except Exception:
            docs = load_documents()
            if docs:
                build_index(docs, persist_dir=STORAGE_DIR)
            else:
                build_index(persist_dir=STORAGE_DIR)
    else:
        docs = load_documents()
        if docs:
            print(f"Loaded {len(docs)} documents (Ghana facilities + Scheme if found).")
            build_index(docs, persist_dir=STORAGE_DIR)
        else:
            print("No Ghana CSV or Scheme TXT found in data/ or Desktop. Using placeholder index.")
            build_index(persist_dir=STORAGE_DIR)

    result = run_agent(query)
    print("\n--- Answer ---")
    print(result.get("final_answer", result.get("error", "No output.")))
    print("\n--- Meta ---")
    print(f"Route: {result.get('route')} | Facilities: {result.get('facilities_count')} | Gaps: {result.get('gaps_count')}")
    if result.get("reasoning"):
        print("Reasoning:", " | ".join(result["reasoning"]))

    if args.trace:
        trace_path = Path(__file__).parent / "trace.json"
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump({
                "query": result.get("query"),
                "route": result.get("route"),
                "trace_export": result.get("trace_export"),
                "row_citations_count": len(result.get("row_citations") or []),
            }, f, indent=2)
        print(f"\nTrace written to {trace_path}")


if __name__ == "__main__":
    main()
