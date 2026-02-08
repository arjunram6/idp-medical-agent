#!/usr/bin/env python3
"""
Guided planning: easy for all experience levels and age groups.
Menu-driven flow — pick what you want to do, then we run the agent with the right query.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.planning import GUIDED_OPTIONS, get_guided_prompt
from src.config import DATA_DIR, OPENAI_API_KEY
from src.data.loaders import load_documents, build_index
from src.graph.pipeline import run_agent


def main():
    print("IDP Medical Agent – Guided planning\n")
    print("What would you like to do?\n")
    for i, opt in enumerate(GUIDED_OPTIONS, 1):
        print(f"  {i}. {opt['label']}: {opt['short']}")
    print(f"  {len(GUIDED_OPTIONS) + 1}. Exit")
    print()
    try:
        choice = input("Enter number (1–{}): ".format(len(GUIDED_OPTIONS) + 1)).strip()
        idx = int(choice)
        if idx < 1 or idx > len(GUIDED_OPTIONS) + 1:
            print("Invalid number.")
            return
        if idx == len(GUIDED_OPTIONS) + 1:
            print("Bye.")
            return
        opt = GUIDED_OPTIONS[idx - 1]
        choice_id = opt["id"]
        extra = ""
        if choice_id == "custom":
            extra = input("Type your question: ").strip()
            query = get_guided_prompt(choice_id, extra)
        elif choice_id == "care_near_me":
            care = input("Type of care (e.g. maternity, pregnant, pediatric, dialysis) [maternity]: ").strip() or "maternity"
            city = input("City or region you're in (e.g. Accra, Kumasi) [Accra]: ").strip() or "Accra"
            if "pregnant" in care.lower() or "maternity" in care.lower():
                query = f"I'm pregnant, where should I go? I live in {city}"
            else:
                query = f"I need {care} care, where should I go? I live in {city}"
        elif choice_id in ("gaps", "find", "regional"):
            extra = input("Capability or region (e.g. dialysis, Accra) [optional]: ").strip()
            if extra and choice_id == "gaps":
                extra = f"Which regions lack {extra}?"
            elif extra and choice_id == "find":
                extra = f"Facilities with {extra}"
            elif extra and choice_id == "regional":
                extra = f"What capabilities exist in {extra}?"
            query = get_guided_prompt(choice_id, extra)
        else:
            query = get_guided_prompt(choice_id, extra)
    except (ValueError, EOFError, KeyboardInterrupt):
        print("Cancelled.")
        return

    print(f"\nRunning: \"{query}\"\n")
    from query_local import can_handle_locally, run_query
    if can_handle_locally(query):
        run_query(query, sys.stdout)
    else:
        docs = load_documents()
        if docs:
            build_index(docs)
        else:
            build_index()
        result = run_agent(query)
        print(result.get("final_answer", result.get("error", "No output.")))
        if result.get("plan"):
            print("\n(Plan used:", len(result["plan"]), "steps)")


if __name__ == "__main__":
    main()
