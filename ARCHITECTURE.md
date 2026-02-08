# IDP Medical Agent – Architecture (runs by default, no prompt)

The full architecture runs **without user prompt**: every query is routed by intent, and each component is used **when the question warrants it**.

## Default flow

1. **Supervisor Agent** – Always on for single-query and Genie Chat. Classifies intent and delegates to the appropriate sub-agent. No `--supervisor` flag needed.

2. **Sub-agents (used when the question warrants it)**

   - **Local CSV** – Counts, locations, services, gaps, risk categories, unrealistic procedures, claim-but-lack, regions lack, care near me, etc. Used when `can_handle_locally(query)` is true.

   - **Genie (text-to-SQL)** – Plaintext English → SQL (DuckDB or Databricks). Used when the question is analytical: "count by", "group by", "total number of", "by region", "by type", or explicit "as SQL" / "convert to sql".

   - **Geospatial** – Non-standard geospatial calculations (e.g. geodesic distance via Haversine). Used when the question is "within X km of Y".

   - **Medical Reasoning Agent** – Adds context, modifies queries, or reasons over results. Used when the question purpose is verification, risk, data quality, clinical care ("where should I go", "I'm pregnant", "recommend"), or claim/lack/regions lack.

   - **External Data** – Data outside the Foundational Data Refresh (FDR). Used when the question mentions "external data", "not in FDR", "real-time", "outside the data", etc.

   - **RAG (vector search + filtering)** – Semantic lookup on plaintext plus metadata-based filtering. Used when no other sub-agent matches. Infers filters from the query (e.g. "hospitals in Accra" → facilityTypeId, region).

## No prompt required

- Single query: `python main.py "your question"` → Supervisor routes and runs the right sub-agent; Medical Reasoning is turned on when the question purpose warrants it.
- Genie Chat: `python main.py --chat` → Same: each message goes through Supervisor + optional Medical Reasoning.
- Opt-out: `--no-supervisor` for direct (legacy) path; `--no-medical-reasoning` to disable auto Medical Reasoning; `--medical-reasoning` to force it on.

## Components

| Component | When used |
|-----------|-----------|
| Supervisor | Always (default) |
| Genie text-to-SQL | Analytical / "count by", "group by", "as sql" |
| Geospatial | "within X km of Y" |
| Medical Reasoning | Risk, verification, clinical care, data quality |
| External Data | "external data", "outside FDR", "real-time" |
| Vector search with filtering | Default RAG path; filters inferred from query |
