"""
Medical Reasoning Agent: Adds medical context, modifies user queries, or reasons over results
returned by other agents. Uses an LLM with a medical-focused system prompt.
"""


def _medical_system_prompt() -> str:
    return """You are a medical reasoning assistant for healthcare facility data in Ghana.
Your role is to:
- Add relevant medical or public health context when appropriate.
- Clarify or rephrase user questions only if needed for accuracy (e.g. map lay terms to clinical terms).
- Reason over answers from other agents: summarize, highlight caveats, or suggest follow-ups (e.g. "Consider contacting the facility to confirm hours").
Keep responses concise and actionable. Do not replace factual answers with generic advice."""


def enhance_query(query: str) -> str | None:
    """
    Optionally refine the user query with medical context or rephrasing.
    Returns the modified query, or None to keep the original.
    """
    try:
        from openai import OpenAI
        from src.config import OPENAI_API_KEY, LLM_MODEL
        if not OPENAI_API_KEY or not (query or "").strip():
            return None
        client = OpenAI(api_key=OPENAI_API_KEY)
        r = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _medical_system_prompt()},
                {"role": "user", "content": f"Rephrase or clarify this question for a facility database search, if needed. If the question is already clear, respond with exactly: {query!r}\n\nUser question: {query}"},
            ],
            max_tokens=200,
        )
        out = (r.choices[0].message.content or "").strip().strip('"')
        return out if out and out != query else None
    except Exception:
        return None


def reason_over_results(question: str, raw_answer: str) -> str | None:
    """
    Reason over the raw answer: add context, caveats, or follow-up suggestions.
    Returns the refined answer, or None to keep the raw answer.
    """
    try:
        from openai import OpenAI
        from src.config import OPENAI_API_KEY, LLM_MODEL
        if not OPENAI_API_KEY or not raw_answer:
            return None
        client = OpenAI(api_key=OPENAI_API_KEY)
        r = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _medical_system_prompt()},
                {"role": "user", "content": f"User asked: {question}\n\nAnswer from the system:\n{raw_answer}\n\nBriefly add any medical context, caveats, or follow-up suggestions. If nothing to add, respond with exactly the same answer as above."},
            ],
            max_tokens=500,
        )
        out = (r.choices[0].message.content or "").strip()
        return out if out and out != raw_answer else None
    except Exception:
        return None
