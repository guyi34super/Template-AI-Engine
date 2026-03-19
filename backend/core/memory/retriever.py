"""
Two-Stage Memory Retriever — v2.1 spec Section 9.3.

Stage 1: Keyword pre-filter via PostgreSQL memory_keyword_index (fast, narrow)
Stage 2: Semantic re-rank via ChromaDB cosine similarity (precise)

Falls back to semantic-only when keyword index is empty.
"""
from __future__ import annotations

import logging
from typing import Optional

from .store import MemoryStore
from .semantic_index import SemanticIndex
from .fact_extractor import extract_keywords_simple

logger = logging.getLogger(__name__)


class MemoryRetriever:
    """Two-stage memory retrieval engine."""

    def __init__(self, semantic_index: Optional[SemanticIndex] = None):
        self.store = MemoryStore()
        self.semantic = semantic_index or SemanticIndex()

    async def retrieve(
        self,
        user_id: str,
        query: str,
        *,
        memory_type: Optional[str] = None,
        limit: int = 10,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7,
    ) -> list[dict]:
        """
        Two-stage retrieval:
        1. Extract keywords from query → search keyword index → get candidate IDs
        2. Semantic search with query → re-rank candidates + semantic results

        Returns merged, deduplicated, scored results.
        """
        # Stage 1: Keyword pre-filter
        keywords = extract_keywords_simple(query)
        keyword_results = []
        if keywords:
            try:
                keyword_results = self.store.search_by_keywords(
                    user_id, keywords, limit=limit * 3
                )
                logger.debug("Keyword stage returned %d candidates", len(keyword_results))
            except Exception as e:
                logger.warning("Keyword search failed: %s", e)

        # Stage 2: Semantic search
        semantic_results = []
        try:
            where_filter = {"user_id": user_id} if user_id else None
            semantic_results = await self.semantic.search(
                query, n_results=limit * 2, where=where_filter
            )
            logger.debug("Semantic stage returned %d candidates", len(semantic_results))
        except Exception as e:
            logger.warning("Semantic search failed: %s", e)

        # Merge and score
        scored: dict[str, float] = {}
        memory_map: dict[str, dict] = {}

        # Score keyword results (rank-based)
        for rank, mem in enumerate(keyword_results):
            mid = mem["id"]
            # Inverse rank score (first = highest)
            rank_score = 1.0 / (rank + 1)
            scored[mid] = scored.get(mid, 0) + keyword_weight * rank_score
            memory_map[mid] = mem

        # Score semantic results (distance-based)
        for rank, sem in enumerate(semantic_results):
            mid = sem.get("memory_id", "")
            # Convert distance to similarity (lower distance = higher similarity)
            distance = sem.get("distance", 1.0)
            similarity = max(0, 1.0 - distance)
            scored[mid] = scored.get(mid, 0) + semantic_weight * similarity
            if mid not in memory_map:
                memory_map[mid] = {
                    "id": mid,
                    "context_summary": sem.get("text", ""),
                    "metadata": sem.get("metadata", {}),
                }

        # Sort by combined score, apply type filter, limit
        ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)

        results = []
        for mid, score in ranked:
            mem = memory_map.get(mid, {})
            if memory_type and mem.get("memory_type") and mem["memory_type"] != memory_type:
                continue
            mem["retrieval_score"] = round(score, 4)
            results.append(mem)
            if len(results) >= limit:
                break

        return results

    async def retrieve_keyword_only(
        self, user_id: str, keywords: list[str], limit: int = 20
    ) -> list[dict]:
        """Stage 1 only — keyword pre-filter."""
        return self.store.search_by_keywords(user_id, keywords, limit)

    async def retrieve_semantic_only(
        self, query: str, limit: int = 10, user_id: Optional[str] = None
    ) -> list[dict]:
        """Stage 2 only — semantic search."""
        where = {"user_id": user_id} if user_id else None
        return await self.semantic.search(query, n_results=limit, where=where)
