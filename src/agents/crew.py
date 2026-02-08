"""CrewAI agents for extraction and verification (used by LangGraph nodes)."""

import os
from typing import Any

# CrewAI optional: only run if crewai is installed and API key set
def create_extraction_crew():
    """Create a CrewAI crew with an extraction agent for facility capabilities."""
    try:
        from crewai import Agent, Task, Crew
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None
    if not os.getenv("OPENAI_API_KEY"):
        return None
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    extractor = Agent(
        role="Medical Facility Data Extractor",
        goal="Extract structured facility names, capabilities, procedures, and locations from unstructured text.",
        backstory="You work with messy healthcare facility data and produce clean, structured extractions.",
        llm=llm,
        allow_delegation=False,
    )
    return {"agent": extractor, "llm": llm}


def run_extraction(text: str, query: str = "") -> str | None:
    """Run CrewAI extraction on a chunk of text. Returns structured summary or None."""
    try:
        from crewai import Agent, Task, Crew
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None
    if not os.getenv("OPENAI_API_KEY"):
        return None
    crew_config = create_extraction_crew()
    if not crew_config:
        return None
    agent = crew_config["agent"]
    task = Task(
        description=f"From this text, extract: facility name(s), medical capabilities, procedures, equipment, and location/region. "
        f"User question for context: {query or 'General extraction'}. Text:\n\n{text[:3000]}",
        expected_output="Bullet list: facility name, then capabilities/procedures/equipment, then location.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task])
    result = crew.kickoff()
    return str(result) if result else None
