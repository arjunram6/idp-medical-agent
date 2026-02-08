#!/usr/bin/env python3
"""
Genie Chat – conversational interface for the IDP Medical Agent.
Multi-turn chat: ask questions about Ghana facilities; answers use the same
pipeline as main.py (local fast path or full RAG + LLM when needed).

Run: python genie_chat.py
      python genie_chat.py --rebuild   # force rebuild index on first agent query
"""

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

PROJECT_ROOT = Path(__file__).resolve().parent
STORAGE_DIR = PROJECT_ROOT / "storage"

_index_ready = False


def _ensure_index(rebuild: bool = False):
    """Build or load vector index once per session (for full-agent queries)."""
    global _index_ready
    if _index_ready:
        return
    from src.config import DATA_DIR
    from src.data.loaders import load_documents, build_index

    if rebuild and STORAGE_DIR.exists():
        import shutil
        shutil.rmtree(STORAGE_DIR, ignore_errors=True)
    if not rebuild and STORAGE_DIR.exists():
        try:
            build_index(None, persist_dir=STORAGE_DIR)
            print("(Using cached index.)\n")
        except Exception:
            docs = load_documents()
            if docs:
                build_index(docs, persist_dir=STORAGE_DIR)
            else:
                build_index(persist_dir=STORAGE_DIR)
    else:
        docs = load_documents()
        if docs:
            print(f"(Loaded {len(docs)} documents, building index…)\n")
            build_index(docs, persist_dir=STORAGE_DIR)
        else:
            build_index(persist_dir=STORAGE_DIR)
    _index_ready = True


def answer_query(query: str, rebuild: bool = False, use_supervisor: bool = True) -> str:
    """Run one query through the pipeline; return answer text. Uses Supervisor + auto Medical Reasoning by default."""
    if not query or not query.strip():
        return "Please type a question."

    if use_supervisor:
        from src.agents.supervisor import classify_intent, dispatch, should_use_medical_reasoning
        result = classify_intent(query.strip())
        use_med = should_use_medical_reasoning(query, result["intent"], result["sub_agent"])
        answer = dispatch(query.strip(), result["sub_agent"], use_medical_reasoning=use_med)
        return answer

    from query_local import can_handle_locally, run_query
    from src.data.loaders import build_index
    from src.graph.pipeline import run_agent

    if can_handle_locally(query):
        buf = io.StringIO()
        run_query(query.strip(), buf)
        return buf.getvalue()

    _ensure_index(rebuild)
    result = run_agent(query.strip())
    answer = result.get("final_answer", result.get("error", "No output."))
    meta = result.get("facilities_count"), result.get("gaps_count")
    return f"{answer}\n\n--- Meta: facilities={meta[0]}, gaps={meta[1]} ---"


def main():
    import argparse
    p = argparse.ArgumentParser(description="Genie Chat – IDP Medical Agent")
    p.add_argument("--rebuild", action="store_true", help="Force rebuild index on first agent query")
    args = p.parse_args()

    print("Genie Chat – IDP Medical Agent")
    print("Ask about Ghana facilities (counts, locations, services, gaps). Type 'quit' or 'exit' to end.\n")

    while True:
        try:
            line = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not line:
            continue
        if line.lower() in ("quit", "exit", "bye", "q"):
            print("Bye.")
            break
        print("\nGenie:")
        try:
            out = answer_query(line, rebuild=args.rebuild)
            print(out)
        except Exception as e:
            print(f"Error: {e}")
        print()


if __name__ == "__main__":
    main()
