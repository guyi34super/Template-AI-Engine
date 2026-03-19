"""
Memory Engine package — v2.1 spec Section 9.

Modules:
  - fact_extractor: Extract structured facts from LLM conversations
  - store: PostgreSQL-backed memory CRUD
  - semantic_index: ChromaDB vector storage for memory entries
  - retriever: Two-stage retrieval (keyword pre-filter → semantic re-rank)
  - summariser: Periodic memory compaction and summarisation
  - engine: Top-level orchestrator with background tasks
"""

from .engine import MemoryEngine
from .store import MemoryStore
from .retriever import MemoryRetriever

__all__ = ["MemoryEngine", "MemoryStore", "MemoryRetriever"]
