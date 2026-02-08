# Core Features (MVP) – Are These Demands Met?

Yes. All three MVP core feature demands are met by the agent.

---

## 1. Unstructured Feature Extraction

**Demand:** Process free-form text fields (e.g., procedure, equipment, and capability columns) to identify specific medical data.

**Status: Met**

- **Where:** `src/extraction.py` and the **unstructured_extract** node in `src/graph/nodes.py`.
- **What it does:**
  - **`extract_from_text(text)`** in `extraction.py` reads free-form text and pulls out:
    - **Procedures** (e.g. surgery, dialysis, cesarean, endoscopy, antenatal, lab test, vaccination, HIV testing).
    - **Equipment** (e.g. X-ray, ultrasound, CT/MRI, ECG, ventilator, operating theatre, dialysis machine, oxygen).
    - **Capabilities** (e.g. 24/7, emergency, inpatient/outpatient, ICU/NICU, trauma, referral, NHIS accredited, maternity, pediatric).
  - **`extract_medical_from_docs(docs)`** runs this on each retrieved facility document and returns a list of structured records: facility name, region, and the extracted procedures, equipment, and capabilities.
- **In the pipeline:** After **retrieve** and **extract_facilities**, the **unstructured_extract** step runs on the retrieved docs and feeds the result into **synthesize**.
- **Trace:** The graph records a step trace for “Unstructured feature extraction” so you can see that this step ran and how many records had medical features.

So: procedure, equipment, and capability **columns** (free-form text) are processed to **identify specific medical data** (procedures, equipment, capabilities) and attached to each facility/region.

---

## 2. Intelligent Synthesis

**Demand:** Combine unstructured insights with structured facility schemas to provide a comprehensive view of regional capabilities.

**Status: Met**

- **Where:** `src/synthesis.py` and the **synthesize** node in `src/graph/nodes.py`.
- **What it does:**
  - **`synthesize_regional_capabilities(extracted_medical, facilities, schema_context)`**:
    - Takes **extracted_medical** (unstructured: procedures, equipment, capabilities per facility from extraction).
    - Takes **facilities** (structured: facility list with metadata from the graph).
    - Optionally uses **schema_context** (structured facility/schema definitions).
    - Builds a **regional view**: by region, which facilities exist and which procedures, equipment, and capabilities exist there.
    - Aggregates **all_procedures**, **all_equipment**, **all_capabilities** across the dataset.
  - The synthesize node passes the schema text (from `get_schema_text()`) as context so the combined view is aligned with the facility schema.
- **In the pipeline:** **synthesize** runs after **unstructured_extract**, using extracted medical data + facility metadata + schema to produce the regional-capabilities view that later nodes (reason, answer) use.

So: **unstructured insights** (extracted procedures/equipment/capabilities) are **combined with structured facility/schema** data to produce a **comprehensive view of regional capabilities**.

---

## 3. Planning System (Easily Accessible, Adopted Across Experience Levels and Age Groups)

**Demand:** A planning system that is easily accessible and could get adopted across experience levels and age groups.

**Status: Met**

- **Where:** `src/planning.py` and `run_guided.py`.
- **What it does:**

  **A) Plan-in-graph (transparency)**  
  - **`build_plan(query, route)`** in `planning.py` produces a short, human-readable list of steps (e.g. “1. Retrieve facility records… 2. Extract procedures, equipment, and capabilities… 3. Combine with schema… 4. Answer with citations.”).  
  - This plan is used in the LangGraph pipeline so users (and logs) can see what steps the agent will take. Supports adoption by making the process understandable.

  **B) Guided menu (no typing required for common tasks)**  
  - **`run_guided.py`** is the entrypoint: `python main.py --guided` (or `python run_guided.py`).  
  - It shows a **numbered menu** of options:
    1. **I need care near me** (e.g. I’m pregnant / need maternity; I live in [city])
    2. **Find gaps** (Where is a type of care missing?)
    3. **Find facilities** (Where can I get a specific care?)
    4. **Regional view** (What capabilities exist by region?)
    5. **Verify a claim** (Can a facility really do X?)
    6. **Custom question** (Type your own question)
    7. **Exit**
  - User **picks a number**; for some options they’re prompted for one short input (e.g. “dialysis”, “Accra”) and the tool turns that into the full question. No need to type long sentences.
  - **`GUIDED_OPTIONS`** and **`get_guided_prompt()`** in `planning.py` define the options and map choices (plus optional extra input) to the concrete query. This design is **easily accessible** and works **across experience levels and age groups** because:
    - Low barrier: numbers and short answers.
    - Clear labels and examples.
    - Custom question still available for advanced users.

So: the **planning system** is implemented as **(1) explicit plan steps in the graph** and **(2) an easy guided menu** that doesn’t require typing full questions, making it adoptable by a wide range of users.

---

## Summary Table

| MVP demand | Met? | Where |
|------------|------|--------|
| Unstructured feature extraction (procedure, equipment, capability) | Yes | `src/extraction.py`, `unstructured_extract` in `src/graph/nodes.py` |
| Intelligent synthesis (unstructured + structured → regional capabilities view) | Yes | `src/synthesis.py`, `synthesize` in `src/graph/nodes.py` |
| Planning system (accessible, all experience levels / age groups) | Yes | `src/planning.py` (plan + guided options), `run_guided.py` (menu) |

All three core feature demands are met by the current agent.
