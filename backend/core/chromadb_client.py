"""
ChromaDB client — manages 4 vector collections per Section 8.4.

Collections:
  doc_chunks      — raw extracted text chunks for similarity search
  template_fields — template field descriptions for auto-mapping
  validation_ctx  — validation rule examples / corrections
  memory_ctx      — cross-session memory embeddings (Supermemory mirror)

Initialised once at app startup; idempotent.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:
    chromadb = None  # type: ignore

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8100"))
CHROMA_PERSIST = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
USE_REMOTE = os.getenv("CHROMA_REMOTE", "false").lower() == "true"

COLLECTION_NAMES = [
    "doc_chunks",
    "template_fields",
    "validation_ctx",
    "memory_ctx",
]

# Global handle
_client: Any = None
_collections: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def init_chromadb() -> None:
    """Create / connect ChromaDB client and ensure all collections exist."""
    global _client, _collections
    if chromadb is None:
        logger.warning("chromadb package not installed — vector features disabled")
        return

    try:
        if USE_REMOTE:
            _client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
            logger.info("ChromaDB remote client → %s:%s", CHROMA_HOST, CHROMA_PORT)
        else:
            _client = chromadb.PersistentClient(path=CHROMA_PERSIST)
            logger.info("ChromaDB persistent client → %s", CHROMA_PERSIST)

        for name in COLLECTION_NAMES:
            _collections[name] = _client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("  ✓ collection '%s' (%d docs)", name, _collections[name].count())
    except Exception as exc:
        logger.error("ChromaDB init failed: %s", exc)
        _client = None


def get_collection(name: str) -> Any | None:
    return _collections.get(name)


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------
async def add_documents(
    collection: str,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict] | None = None,
    embeddings: list[list[float]] | None = None,
) -> None:
    """Add documents (with optional pre-computed embeddings) to a collection."""
    col = _collections.get(collection)
    if col is None:
        logger.warning("Collection '%s' not initialised", collection)
        return
    kwargs: dict[str, Any] = {"ids": ids, "documents": documents}
    if metadatas:
        kwargs["metadatas"] = metadatas
    if embeddings:
        kwargs["embeddings"] = embeddings
    col.add(**kwargs)


async def query_documents(
    collection: str,
    query_texts: list[str] | None = None,
    query_embeddings: list[list[float]] | None = None,
    n_results: int = 5,
    where: dict | None = None,
) -> dict:
    """Query a collection by text or embedding vector."""
    col = _collections.get(collection)
    if col is None:
        return {"ids": [], "documents": [], "distances": []}
    kwargs: dict[str, Any] = {"n_results": n_results}
    if query_texts:
        kwargs["query_texts"] = query_texts
    if query_embeddings:
        kwargs["query_embeddings"] = query_embeddings
    if where:
        kwargs["where"] = where
    return col.query(**kwargs)


async def delete_documents(collection: str, ids: list[str]) -> None:
    col = _collections.get(collection)
    if col is None:
        return
    col.delete(ids=ids)


async def count_documents(collection: str) -> int:
    col = _collections.get(collection)
    return col.count() if col else 0
