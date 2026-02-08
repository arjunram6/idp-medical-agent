"""Configuration and environment for the IDP medical agent."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
STORAGE_DIR = PROJECT_ROOT / "storage"
DATA_DIR.mkdir(exist_ok=True)

# Ghana data: prefer data/, fallback to Desktop
GHANA_CSV_NAMES = ["Virtue Foundation Ghana v0.3 - Sheet1.csv", "Virtue_Foundation_Ghana_Sheet1.csv"]
SCHEMA_TXT_NAMES = ["Virtue Foundation Scheme Documentation.txt", "SCHEMA.md"]


def _find_ghana_csv() -> Path | None:
    for name in GHANA_CSV_NAMES:
        p = DATA_DIR / name
        if p.exists():
            return p
    desktop = Path.home() / "Desktop"
    for name in GHANA_CSV_NAMES:
        p = desktop / name
        if p.exists():
            return p
    return None


def _find_geocoded_csv() -> Path | None:
    """Prefer CSV that has latitude/longitude (e.g. *_geocoded.csv)."""
    base = _find_ghana_csv()
    if not base:
        return None
    geocoded = base.parent / (base.stem + "_geocoded" + base.suffix)
    if geocoded.exists():
        return geocoded
    return base


def _find_schema_txt() -> Path | None:
    for name in SCHEMA_TXT_NAMES:
        p = DATA_DIR / name
        if p.exists():
            return p
    desktop = Path.home() / "Desktop"
    for name in SCHEMA_TXT_NAMES:
        p = desktop / name
        if p.exists():
            return p
    return None

# LLM
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# RAG (LlamaIndex)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "4"))  # fewer chunks = faster retrieve + answer (target 3–5s)

# Graph
MAX_STEPS = int(os.getenv("MAX_STEPS", "15"))

# Geocoding (geocode.maps.co) for facility lat/lon (env overrides default)
GEOCODE_API_KEY = os.getenv("GEOCODE_API_KEY", "6987cd64e1b91785873438yeb0bcc63")
GEOCODE_BASE_URL = "https://geocode.maps.co/search"
