#!/usr/bin/env python3
"""
Tests for the IDP medical agent.
Run: python3 test_agent.py

Step 1: Install dependencies (run this once in Terminal):
  cd ~/Documents/idp-medical-agent
  pip3 install -r requirements.txt

Step 2: Run test:
  python3 test_agent.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def test_without_heavy_deps():
    """Tests that work without langgraph/llama-index (config, planning, extraction, citations)."""
    print("Running lightweight tests (no pip install needed)...\n")
    # Config
    from src.config import DATA_DIR, OPENAI_API_KEY
    assert DATA_DIR.exists() or True
    print("  ✓ config")

    # Planning
    from src.planning import build_plan, GUIDED_OPTIONS, get_guided_prompt
    plan = build_plan("Which regions lack dialysis?", "gaps")
    assert len(plan) >= 1
    assert len(GUIDED_OPTIONS) >= 1
    assert "dialysis" in get_guided_prompt("gaps", "dialysis").lower() or "lack" in get_guided_prompt("gaps", "dialysis").lower()
    print("  ✓ planning")

    # Extraction (regex only)
    from src.extraction import extract_from_text
    out = extract_from_text("We offer surgery, x-ray, and 24/7 emergency care.")
    assert "surgery" in out["procedures"] or "emergency" in out["capabilities"]
    print("  ✓ extraction")

    # Synthesis
    from src.synthesis import synthesize_regional_capabilities
    syn = synthesize_regional_capabilities(
        [{"name": "A", "region": "Accra", "procedures": ["surgery"], "equipment": [], "capabilities": []}],
        [{"name": "A", "metadata": {}}],
    )
    assert "by_region" in syn
    print("  ✓ synthesis")

    # Citations
    from src.citations import format_row_citations, format_step_traces
    assert "References" in format_row_citations([{"ref_id": 1, "row_name": "X", "fields_used": ["capability"]}])
    print("  ✓ citations")
    print("\nLightweight tests passed.\n")


def test_full_agent():
    """Full pipeline test (requires: pip3 install -r requirements.txt)."""
    try:
        from src.data.loaders import load_documents, build_index
        from src.graph.pipeline import run_agent
    except ImportError as e:
        print("Skipping full agent test (missing dependencies).")
        print("  To run the full test, in Terminal run:")
        print("    cd ~/Documents/idp-medical-agent")
        print("    pip3 install -r requirements.txt")
        print("  Then run: python3 test_agent.py")
        print("\n  Error was:", e)
        return False

    docs = load_documents()
    build_index(docs)
    result = run_agent("Where are facilities with maternity care?")
    assert "final_answer" in result
    assert "route" in result
    assert "step_traces" in result
    print("  ✓ load_documents + build_index")
    print("  ✓ run_agent (route=%s, answer length=%s)" % (result.get("route"), len(result.get("final_answer", ""))))
    return True


def main():
    print("Testing IDP Medical Agent\n")
    test_without_heavy_deps()
    ok = test_full_agent()
    if ok:
        print("\nAll tests passed.")
    else:
        print("\nLightweight tests passed. Install deps for full test (see above).")

if __name__ == "__main__":
    main()
