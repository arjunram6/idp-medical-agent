IDP Medical Agent – Share package
==================================

This zip contains the codebase. It EXCLUDES:
  - .env (API keys – recipient must add their own)
  - .venv / venv
  - data/*.csv (Ghana facility data – add your own CSV to data/ or Desktop)
  - storage/ (vector index cache – rebuilt on first run)
  - .git

Recipient setup:
  1. Unzip into a folder (e.g. idp-medical-agent).
  2. cd into that folder.
  3. python3 -m venv .venv && source .venv/bin/activate  (or Windows: .venv\Scripts\activate)
  4. pip install -r requirements.txt
  5. Copy .env.example to .env and set OPENAI_API_KEY (and GEOCODE_API_KEY if using geocoding).
  6. Place Ghana CSV + scheme doc in data/ or Desktop (see README.md for names).
  7. Run: python main.py "your question"  or  python main.py --chat

Architecture: See ARCHITECTURE.md. Supervisor routes by intent; Medical Reasoning, Genie text-to-SQL, geospatial, external data, and vector search are used when the question warrants it.
