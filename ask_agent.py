#!/usr/bin/env python3
"""Ask the IDP Medical Agent a question via the running API. Usage: python ask_agent.py 'Your question here'"""

import sys
import urllib.request
import json

BASE = "http://localhost:8000"


def ask(query: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}/api/query",
        data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ask_agent.py 'Your question here'")
        sys.exit(1)
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print("Usage: python ask_agent.py 'Your question here'")
        sys.exit(1)
    try:
        out = ask(question)
        print(out.get("answer", out))
        if out.get("sub_agent"):
            print("\n[Agent:", out["sub_agent"], "| Medical reasoning:", out.get("used_medical_reasoning", False), "]")
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        sys.exit(1)
