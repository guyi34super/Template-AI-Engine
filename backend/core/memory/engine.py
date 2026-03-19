"""
Memory Engine — top-level orchestrator that ties together all memory modules.

Provides high-level operations:
  - add_memory: extract facts + store + index
  - recall: two-stage retrieval
  - forget: delete memory
  - summarise: compact old memories
  - build_index: delegate keyword index building to Rust
"""
from __future__ import annotations

import logging
from typing import Optional, Any
from datetime import datetime

from .fact_extractor import extract_facts, extract_keywords_simple
from .store import MemoryStore
from .semantic_index import SemanticIndex
from .retriever import MemoryRetriever
from . import summariser

logger = logging.getLogger(__name__)


class MemoryEngine:
    """Single entry point for all memory operations."""

    def __init__(self):
        self.store = MemoryStore()
        self.semantic = SemanticIndex()
        self.retriever = MemoryRetriever(self.semantic)

    async def add_memory(
        self,
        user_id: str,
        text: str,
        *,
        memory_type: str = "general",
        importance_score: float = 0.5,
        expires_at: Optional[datetime] = None,
        extract_from_llm: bool = True,
    ) -> list[dict]:
        """
        Add one or more memory entries from text.

        If extract_from_llm=True, uses the LLM to extract structured facts.
        Otherwise, stores the text as a single memory entry.
        """
        results = []

        if extract_from_llm:
            facts = await extract_facts(text)
            if not facts:
                # Fallback: store as single entry
                facts = [{"text": text, "type": memory_type, "importance": importance_score, "keywords": []}]
        else:
            facts = [{"text": text, "type": memory_type, "importance": importance_score, "keywords": []}]

        for fact in facts:
            fact_text = fact.get("text", text)
            fact_type = fact.get("type", memory_type)
            fact_importance = fact.get("importance", importance_score)
            keywords = fact.get("keywords") or extract_keywords_simple(fact_text)

            # Store in PostgreSQL
            entry = self.store.create(
                user_id=user_id,
                context_summary=fact_text,
                memory_type=fact_type,
                keywords=keywords,
                importance_score=fact_importance,
                expires_at=expires_at,
            )

            # Index in ChromaDB
            embedding_id = await self.semantic.add(
                entry["id"],
                fact_text,
                metadata={"user_id": user_id, "memory_type": fact_type},
            )
            if embedding_id:
                entry["embedding_id"] = embedding_id

            results.append(entry)

        # Optionally delegate keyword indexing to Rust for batch efficiency
        if len(results) > 3:
            await self._rust_keyword_index(results)

        return results

    async def recall(
        self,
        user_id: str,
        query: str,
        *,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Two-stage retrieval: keyword pre-filter → semantic re-rank."""
        return await self.retriever.retrieve(
            user_id, query, memory_type=memory_type, limit=limit
        )

    async def forget(self, entry_id: str) -> bool:
        """Delete a memory entry from all stores."""
        self.semantic.delete(entry_id)
        return self.store.delete(entry_id)

    async def summarise(self, user_id: str, **kwargs) -> dict:
        """Compact old memories into summaries."""
        return await summariser.summarise_memories(user_id, **kwargs)

    async def expire(self) -> dict:
        """Remove all expired entries."""
        return await summariser.expire_memories()

    async def get(self, entry_id: str) -> Optional[dict]:
        """Retrieve a single memory entry."""
        return self.store.get(entry_id)

    async def list_memories(
        self, user_id: str, memory_type: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """List all memories for a user."""
        return self.store.list_by_user(user_id, memory_type=memory_type, limit=limit)

    async def _rust_keyword_index(self, entries: list[dict]) -> None:
        """Delegate keyword indexing to Rust service for batch efficiency."""
        try:
            from core.rust_bridge import build_keyword_index
            rust_entries = [
                {
                    "id": e["id"],
                    "text": e.get("context_summary", ""),
                    "metadata": {"user_id": e.get("user_id"), "type": e.get("memory_type")},
                }
                for e in entries
            ]
            result = await build_keyword_index(rust_entries)
            logger.debug("Rust keyword index built: %d keywords in %dms",
                         result.get("total_keywords", 0),
                         result.get("processing_time_ms", 0))
        except Exception as e:
            logger.debug("Rust keyword indexing unavailable: %s", e)
