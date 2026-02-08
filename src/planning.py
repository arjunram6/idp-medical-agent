"""
Planning system: easy to use across experience levels and age groups.
- Plan-in-graph: produce a short list of steps before executing (transparency).
- Guided flow: simple menu so users can choose "Find gaps", "Regional view", etc. without typing.
"""

from typing import Any

# Human-friendly options for guided planning (accessible to all experience levels)
GUIDED_OPTIONS = [
    {"id": "care_near_me", "label": "I need care near me", "short": "e.g. I'm pregnant / need maternity; I live in [city]", "example": "I'm pregnant, where should I go? I live in Accra"},
    {"id": "gaps", "label": "Find gaps", "short": "Where is a type of care missing?", "example": "Which regions lack dialysis?"},
    {"id": "find", "label": "Find facilities", "short": "Where can I get a specific care?", "example": "Facilities with maternity care"},
    {"id": "regional", "label": "Regional view", "short": "What capabilities exist by region?", "example": "What does Accra have?"},
    {"id": "verify", "label": "Verify a claim", "short": "Can a facility really do X?", "example": "Can Korle Bu do dialysis?"},
    {"id": "custom", "label": "Custom question", "short": "Type your own question", "example": ""},
]


def build_plan(query: str, route: str) -> list[str]:
    """Build a short human-readable plan (steps we will take) for transparency."""
    plans = {
        "rag": [
            "1. Retrieve facility records matching your question.",
            "2. Extract procedures, equipment, and capabilities from the text.",
            "3. Combine with schema for a clear view.",
            "4. Answer with citations to the source data.",
        ],
        "gaps": [
            "1. Retrieve facilities and their capabilities.",
            "2. Identify which regions have or lack the capability you asked about.",
            "3. Synthesize a regional view and list gaps.",
            "4. Answer with citations.",
        ],
        "verify": [
            "1. Find the facility you named.",
            "2. Check its procedures, equipment, and capabilities.",
            "3. Compare with what it claims and give a verdict.",
            "4. Cite the source rows.",
        ],
        "deserts": [
            "1. Retrieve facilities and locations.",
            "2. Identify areas with little or no coverage.",
            "3. Synthesize and answer with citations.",
        ],
    }
    return plans.get(route, plans["rag"])


def get_guided_prompt(choice_id: str, extra: str = "") -> str:
    """Turn a guided menu choice into a concrete query (so all ages/levels get a good result)."""
    for opt in GUIDED_OPTIONS:
        if opt["id"] == choice_id:
            if choice_id == "custom":
                return extra.strip() or "What facilities and capabilities are in the data?"
            if extra.strip() and choice_id in ("gaps", "find", "regional", "care_near_me"):
                return extra.strip()
            return opt.get("example", opt["short"])
    return extra or "What facilities and capabilities are in the data?"
