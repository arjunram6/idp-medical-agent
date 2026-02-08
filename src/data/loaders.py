"""Document loading and RAG index using LlamaIndex. Ghana CSV + Scheme TXT."""

from pathlib import Path
from typing import Any

from src.config import (
    DATA_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    OPENAI_API_KEY,
    _find_ghana_csv,
    _find_schema_txt,
)

# Lazy imports so the project can be imported without all deps installed
_index = None

# Columns that form the main searchable text for Ghana facility rows
GHANA_TEXT_COLS = [
    "name", "description", "capability", "procedure", "equipment", "specialties",
    "address_line1", "address_city", "address_stateOrRegion", "address_country",
    "organization_type", "facilityTypeId", "capacity",
]


def load_documents(path: str | Path | None = None) -> list[Any]:
    """Load documents: Ghana CSV + Scheme TXT when path is data dir or None."""
    try:
        from llama_index.core import SimpleDirectoryReader
        from llama_index.core.schema import Document
    except ImportError:
        return []

    # Default: load Ghana CSV and Scheme TXT
    if path is None or Path(path) == DATA_DIR:
        docs = []
        csv_path = _find_ghana_csv()
        if csv_path:
            docs.extend(_load_ghana_csv(csv_path))
        schema_path = _find_schema_txt()
        if schema_path:
            docs.append(_load_schema_doc(schema_path))
        if docs:
            return docs
        # Fallback: any files in data/
        path = DATA_DIR

    path = Path(path)
    if not path.exists():
        return []

    if path.is_file():
        if path.suffix.lower() == ".csv":
            return _load_ghana_csv(path) if _looks_like_ghana_csv(path) else _load_csv(path)
        return SimpleDirectoryReader(input_files=[str(path)]).load_data()

    return SimpleDirectoryReader(input_dir=str(path)).load_data()


def _looks_like_ghana_csv(path: Path) -> bool:
    with open(path, encoding="utf-8", errors="replace") as f:
        first = f.readline().lower()
    return "capability" in first and ("name" in first or "pk_unique_id" in first)


def _load_ghana_csv(path: Path) -> list[Any]:
    """Load Virtue Foundation Ghana CSV: one doc per facility with rich text and metadata."""
    import csv
    from llama_index.core.schema import Document

    docs = []
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            text_parts = []
            for col in GHANA_TEXT_COLS:
                val = row.get(col)
                if val and str(val).strip() and str(val).strip().lower() not in ("null", "[]", ""):
                    text_parts.append(f"{col}: {val}")
            text = "\n".join(text_parts) if text_parts else str(row)[:2000]
            meta = {
                "row_id": i,
                "source": str(path.name),
                "name": (row.get("name") or "").strip() or "Unknown",
                "address_city": (row.get("address_city") or "").strip(),
                "address_stateOrRegion": (row.get("address_stateOrRegion") or "").strip(),
                "region": (row.get("address_stateOrRegion") or row.get("address_city") or "").strip(),
                "facilityTypeId": (row.get("facilityTypeId") or "").strip(),
                "pk_unique_id": (row.get("pk_unique_id") or "").strip(),
            }
            docs.append(Document(text=text, metadata=meta))
    return docs


def _load_schema_doc(path: Path) -> Any:
    """Load Scheme Documentation as one doc for context."""
    from llama_index.core.schema import Document
    text = path.read_text(encoding="utf-8", errors="replace")
    return Document(
        text=text,
        metadata={"source": path.name, "type": "schema", "name": "Virtue Foundation Scheme"},
    )


def get_schema_text() -> str:
    """Return raw schema document text for synthesis (combine with structured view)."""
    path = _find_schema_txt()
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _load_csv(path: Path) -> list[Any]:
    """Generic CSV: one row per doc with metadata."""
    import csv
    from llama_index.core.schema import Document

    docs = []
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            parts = [f"{k}: {v}" for k, v in row.items() if v and str(v).strip()]
            text = "\n".join(parts)
            docs.append(Document(text=text, metadata={"row_id": i, "source": str(path), **row}))
    return docs


def build_index(documents: list[Any] | None = None, persist_dir: str | Path | None = None) -> Any:
    """Build a vector index from documents. Uses OpenAI embeddings if OPENAI_API_KEY set."""
    global _index
    try:
        from llama_index.core import VectorStoreIndex, Settings, StorageContext, load_index_from_storage
        from llama_index.core.node_parser import SentenceSplitter
        from llama_index.embeddings.openai import OpenAIEmbedding
        from llama_index.llms.openai import OpenAI
    except ImportError as e:
        raise ImportError("Install llama-index and llama-index-embeddings-openai") from e

    if persist_dir and Path(persist_dir).exists():
        try:
            storage_context = StorageContext.from_defaults(persist_dir=str(persist_dir))
            _index = load_index_from_storage(storage_context)
            return _index
        except Exception:
            pass

    docs = documents or load_documents()
    if not docs:
        # Empty index: use a placeholder doc so the index is buildable
        from llama_index.core.schema import Document
        Settings.chunk_size = CHUNK_SIZE
        Settings.chunk_overlap = CHUNK_OVERLAP
        if OPENAI_API_KEY:
            Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
        placeholder = Document(text="No facility data loaded. Add CSV or TXT files to the data directory.", metadata={"source": "placeholder"})
        _index = VectorStoreIndex.from_documents([placeholder], embed_model=Settings.embed_model)
        return _index

    Settings.chunk_size = CHUNK_SIZE
    Settings.chunk_overlap = CHUNK_OVERLAP
    if OPENAI_API_KEY:
        Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(docs)
    _index = VectorStoreIndex(nodes, embed_model=Settings.embed_model)

    if persist_dir:
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        _index.storage_context.persist(persist_dir=str(persist_dir))

    return _index


def infer_metadata_filters_from_query(query: str) -> dict[str, Any]:
    """
    Infer metadata filters from natural-language query for vector search with filtering.
    E.g. "hospitals in Accra" -> facilityTypeId=hospital, region/address_stateOrRegion=Accra.
    """
    q = (query or "").strip().lower()
    filters: dict[str, Any] = {}
    import re
    # Facility type
    for ft, label in [("hospital", "hospital"), ("clinic", "clinic"), ("pharmacy", "pharmacy"), ("dentist", "dentist"), ("doctor", "doctor")]:
        if re.search(rf"\b{ft}s?\b", q):
            filters["facilityTypeId"] = ft
            break
    # Place: "in Accra", "in Kumasi", "Accra hospitals"
    places = ["accra", "kumasi", "tamale", "takoradi", "cape coast", "greater accra", "ashanti", "eastern", "western"]
    for place in places:
        if place in q:
            filters["region"] = place.title()
            break
    return filters


def get_retriever(top_k: int = 10, metadata_filters: dict[str, Any] | None = None):
    """Return a retriever over the built index. Optionally apply metadata-based filtering."""
    global _index
    if _index is None:
        build_index()
    try:
        from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
        if metadata_filters and isinstance(metadata_filters, dict):
            filters = [
                MetadataFilter(key=k, value=str(v).strip(), operator=FilterOperator.EQ)
                for k, v in metadata_filters.items()
                if v is not None and str(v).strip()
            ]
            if filters:
                return _index.as_retriever(
                    similarity_top_k=min(top_k * 2, 50),
                    filters=MetadataFilters(filters=filters, condition="and"),
                )
    except Exception:
        pass
    return _index.as_retriever(similarity_top_k=top_k)


def query_index(
    query: str,
    top_k: int = 10,
    metadata_filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Vector search: semantic lookup on plaintext plus optional metadata-based filtering.
    Returns list of doc dicts (text, metadata, score).
    """
    retriever = get_retriever(top_k=top_k, metadata_filters=metadata_filters)
    nodes = retriever.retrieve(query)
    out = [
        {"text": n.get_content(), "metadata": n.metadata, "score": n.score}
        for n in nodes
    ]
    if metadata_filters:
        # Post-filter if retriever did not apply filters (e.g. in-memory store)
        for key, val in metadata_filters.items():
            if val is None or not str(val).strip():
                continue
            v_lower = str(val).strip().lower()
            def _matches(md_val: Any) -> bool:
                s = str(md_val or "").strip().lower()
                return s == v_lower or v_lower in s
            out = [d for d in out if _matches((d.get("metadata") or {}).get(key))]
    return out[:top_k]
