# IDP Medical Agent

An **Intelligent Document Parsing (IDP) agent** that goes beyond simple search: it extracts and verifies medical facility capabilities from messy, unstructured data and **reasons over it** to understand where care truly exists and where it is missing.

## Stack

- **LangGraph** – orchestration (state machine: route → retrieve → extract → reason → answer)
- **LlamaIndex** – document loading, chunking, and vector RAG
- **CrewAI** – optional extraction/verification agents (structured extraction from text)
- **LangChain / OpenAI** – LLM calls for routing and answer generation

## Setup

```bash
cd ~/Documents/idp-medical-agent-full
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Add your OPENAI_API_KEY to .env
```

## Data (Ghana CSV + Scheme TXT)

The agent looks for:

1. **Virtue Foundation Ghana CSV** – `Virtue Foundation Ghana v0.3 - Sheet1.csv`  
   In `data/` or on your **Desktop**. One document per facility; columns `name`, `capability`, `description`, `procedure`, `equipment`, `specialties`, address, etc. are used for search and metadata.

2. **Virtue Foundation Scheme Documentation** – `Virtue Foundation Scheme Documentation.txt` (or `SCHEMA.md`)  
   In `data/` or **Desktop**. Loaded as one context doc for schema (field definitions, specialty hierarchy).

You can copy the CSV and TXT into `data/` for a self-contained project, or leave them on Desktop; the loader checks both.

If neither is found, the agent runs with a placeholder index (retrieval returns little).

## Run

```bash
# Direct query
python main.py "Which regions lack dialysis?"
python main.py "Find facilities with maternity care"

# Guided planning (menu-driven, all experience levels / age groups)
python main.py --guided

# Export step trace for experiment tracking
python main.py --trace "Which regions lack dialysis?"
# Writes trace.json with step-level inputs/outputs and citation refs
```

## API (Lovable / frontend)

Run the API:

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Base URL: `http://localhost:8000`

### Health
- `GET /api/health`
- `GET /health` (legacy alias)

### Query (single-turn)
- `POST /api/query`
- `POST /query` (legacy alias)

Body:
```json
{ "query": "Which regions lack dialysis?" }
```

Response:
```json
{
  "answer": "...",
  "intent": "local_facility_query",
  "sub_agent": "local_csv",
  "used_medical_reasoning": false
}
```

### Chat (single-turn, UI-friendly)
- `POST /api/chat`

Body:
```json
{ "message": "How many hospitals in Accra have emergency care?" }
```

Response:
```json
{
  "reply": "...",
  "intent": "local_facility_query",
  "sub_agent": "local_csv"
}
```

### Guided options
- `GET /api/guided-options`

Response:
```json
{ "options": [ { "id": "gaps", "label": "...", "short": "..." } ] }
```

### Guided query
- `POST /api/guided-query`

Body:
```json
{ "query": "Which regions lack dialysis?" }
```

### Regional capabilities summary
- `GET /api/regions/summary`

Response:
```json
{
  "summary": { "by_region": { "Accra": { "facilities": [], "procedures": [] } } },
  "regions_count": 16,
  "total_procedures": 42,
  "total_equipment": 28,
  "total_capabilities": 31
}
```

### Notes
- Local CSV queries run without OpenAI.
- RAG / Text-to-SQL / External Data / Medical Reasoning require `OPENAI_API_KEY`.
- Geospatial queries use geocode API when available; run `python geocode_facilities.py` for full lat/lon coverage.

## Core features (MVP)

1. **Unstructured feature extraction** – Processes free-form `procedure`, `equipment`, and `capability` columns (and description/specialties) to identify specific medical data. Each retrieved doc is parsed for procedures (e.g. surgery, dialysis, cesarean), equipment (e.g. x-ray, ultrasound, operating theatre), and capabilities (e.g. 24/7, emergency, ICU). Stored in state as `extracted_medical` and used in synthesis.

2. **Intelligent synthesis** – Combines unstructured extracted insights with the structured facility schema (Virtue Foundation Scheme) into a **regional capabilities view**: by region, which facilities exist and which procedures/equipment/capabilities are present. Stored in state as `synthesis` and used for gap analysis and the final answer.

3. **Planning system** – Two parts:
   - **Plan-in-graph**: After routing, the agent produces a short human-readable plan (e.g. “1. Retrieve facility records … 2. Extract procedures/equipment … 3. Synthesize regional view … 4. Answer with citations”) and attaches it to the answer for transparency.
   - **Guided flow**: Run `python main.py --guided` for a simple menu: “Find gaps”, “Find facilities”, “Regional view”, “Verify a claim”, or “Custom question”. Designed to be easily accessible and adoptable across experience levels and age groups.

## Citations and tracing (stretch)

- **Row-level citations**: Every retrieved doc gets a ref ID. The final answer includes a **References** section: `[ref_id] row_name — fields_used`. The LLM is prompted to cite refs in the answer (e.g. “Facility X [1] offers …”).
- **Step-level citations**: Each graph step records which ref IDs it used. The answer appends **Step-level citations**: “Step 1 (route): used —. Step 2 (retrieve): used [1,2,3]. …” so you can see which data supported each reasoning step.
- **Experiment tracking**: Use `python main.py --trace "query"` to write `trace.json` with `trace_export` (steps, citation_refs, inputs/outputs summaries). You can log this to MLflow, LangSmith, or any tracker by reading `trace.json` after each run.

## Project layout

```
idp-medical-agent/
├── main.py              # Entrypoint (query, --guided, --trace)
├── run_guided.py        # Guided planning menu
├── requirements.txt
├── .env.example
├── data/                # Ghana CSV + Scheme TXT (or Desktop)
└── src/
    ├── config.py
    ├── models.py        # AgentState, RowCitation, StepTrace
    ├── citations.py     # Row + step citations, trace export
    ├── extraction.py   # Unstructured procedure/equipment/capability extraction
    ├── synthesis.py    # Regional capabilities synthesis
    ├── planning.py    # build_plan(), GUIDED_OPTIONS, get_guided_prompt
    ├── data/loaders.py
    ├── graph/
    │   ├── nodes.py    # route, plan, retrieve, extract, unstructured_extract, synthesize, reason, answer
    │   └── pipeline.py
    └── agents/crew.py
```

## Routes

The agent classifies each query into:

- **rag** – semantic search over facilities (LlamaIndex), then answer from context.
- **gaps** – which regions lack a capability (simple heuristic over retrieved docs).
- **verify** – verify a claim about a facility (e.g. “Can X really do Y?”).
- **deserts** – medical deserts / access risk (placeholder for your logic).

You can extend `graph/nodes.py` and add tools or CrewAI tasks for verification and desert analysis.

## License

Use as you like.
