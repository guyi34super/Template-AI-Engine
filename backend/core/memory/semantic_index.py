"""
Semantic Index — ChromaDB vector storage for memory entries.

Stores memory embeddings in the 'memory_ctx' collection and supports
similarity-based retrieval for the second stage of two-stage retrieval.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SemanticIndex:
    """ChromaDB-backed semantic memory index."""

    def __init__(self):
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            try:
                from core.chromadb_client import get_collection
                self._collection = get_collection("memory_ctx")
            except Exception as e:
                logger.warning("ChromaDB memory collection unavailable: %s", e)
        return self._collection

    async def add(self, memory_id: str, text: str, metadata: Optional[dict] = None) -> Optional[str]:
        """Embed text and store in ChromaDB. Returns embedding_id."""
        collection = self._get_collection()
        if collection is None:
            return None

        try:
            from core.embedding_client import embed_text
            vector = await embed_text(text)

            meta = metadata or {}
            meta["memory_id"] = memory_id

            collection.upsert(
                ids=[memory_id],
                embeddings=[vector],
                documents=[text],
                metadatas=[meta],
            )
            return memory_id
        except Exception as e:
            logger.error("Failed to add memory to semantic index: %s", e)
            return None

    async def search(self, query: str, n_results: int = 10, where: Optional[dict] = None) -> list[dict]:
        """Semantic search — embed query, find similar memories."""
        collection = self._get_collection()
        if collection is None:
            return []

        try:
            from core.embedding_client import embed_text
            query_vec = await embed_text(query)

            params = {
                "query_embeddings": [query_vec],
                "n_results": n_results,
            }
            if where:
                params["where"] = where

            results = collection.query(**params)

            items = []
            for i, doc_id in enumerate(results.get("ids", [[]])[0]):
                items.append({
                    "memory_id": doc_id,
                    "text": results.get("documents", [[]])[0][i] if results.get("documents") else "",
                    "distance": results.get("distances", [[]])[0][i] if results.get("distances") else 0.0,
                    "metadata": results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {},
                })
            return items
        except Exception as e:
            logger.error("Semantic search failed: %s", e)
            return []

    def delete(self, memory_id: str) -> bool:
        """Remove memory from semantic index."""
        collection = self._get_collection()
        if collection is None:
            return False
        try:
            collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False
