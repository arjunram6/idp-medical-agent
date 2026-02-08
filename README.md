# IDP Medical Agent

## Project description
IDP Medical Agent is an intelligent document‑parsing system for Ghana healthcare facility data. It extracts capabilities from messy, unstructured text and answers questions about services, gaps, and access.

## Setup instructions
```bash
cd ~/Documents/idp-medical-agent-full
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Add your OPENAI_API_KEY to .env
```

Add data files:
- `data/Virtue Foundation Ghana v0.3 - Sheet1.csv`
- `data/Virtue Foundation Scheme Documentation.txt` (or `SCHEMA.md`)

## Dependencies and environment files
- `requirements.txt` (Python dependencies)
- `.env.example` (copy to `.env`)

Required environment variables:
- `OPENAI_API_KEY` (for RAG, Medical Reasoning, External Data, and Text‑to‑SQL)
- `GEOCODE_API_KEY` (optional, for geocode‑based distance queries)
