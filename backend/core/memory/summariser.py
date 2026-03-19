"""
Memory Summariser — periodic memory compaction and summarisation.

Condenses old, low-importance or frequently-accessed memories into
compact summaries to prevent memory bloat.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from .store import MemoryStore

logger = logging.getLogger(__name__)


async def summarise_memories(
    user_id: str,
    *,
    older_than_days: int = 30,
    min_access_count: int = 0,
    max_importance: float = 0.3,
) -> dict:
    """
    Summarise old, low-importance memories into a single compacted entry.

    Returns summary stats.
    """
    from core.db import is_async_db, get_sync_session
    if not is_async_db():
        return {"summarised": 0, "message": "PostgreSQL not available"}

    from core.models import MemoryEntry

    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    with get_sync_session() as session:
        candidates = (
            session.query(MemoryEntry)
            .filter(
                MemoryEntry.user_id == user_id,
                MemoryEntry.created_at < cutoff,
                MemoryEntry.importance_score <= max_importance,
            )
            .order_by(MemoryEntry.created_at.asc())
            .limit(50)
            .all()
        )

        if not candidates:
            return {"summarised": 0, "message": "No candidates for summarisation"}

        # Collect summaries
        texts = [e.context_summary or "" for e in candidates if e.context_summary]
        if not texts:
            return {"summarised": 0, "message": "No text to summarise"}

        combined = "\n---\n".join(texts)

        # Use LLM to produce compacted summary
        try:
            from core.llm_client import chat_completion
            prompt = (
                f"Summarise the following {len(texts)} memory entries into a single, "
                "concise paragraph preserving all key facts:\n\n"
                f"{combined[:4000]}"
            )
            summary = await chat_completion(
                [{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=0.2,
            )
        except Exception as e:
            logger.error("LLM summarisation failed: %s", e)
            summary = f"[Auto-summary of {len(texts)} entries] " + combined[:500]

        # Create new compacted entry
        from .fact_extractor import extract_keywords_simple
        keywords = extract_keywords_simple(summary)

        MemoryStore.create(
            user_id=user_id,
            context_summary=summary,
            memory_type="general",
            keywords=keywords,
            importance_score=0.6,  # Summaries get moderate importance
        )

        # Delete old entries
        ids_to_delete = [e.id for e in candidates]
        for eid in ids_to_delete:
            MemoryStore.delete(eid)

        return {
            "summarised": len(ids_to_delete),
            "new_summary_length": len(summary),
            "message": f"Compacted {len(ids_to_delete)} memories into 1 summary",
        }


async def expire_memories() -> dict:
    """Remove all expired memory entries."""
    from core.db import is_async_db, get_sync_session
    if not is_async_db():
        return {"expired": 0}

    from core.models import MemoryEntry
    now = datetime.now(timezone.utc)

    with get_sync_session() as session:
        expired = (
            session.query(MemoryEntry)
            .filter(
                MemoryEntry.expires_at.isnot(None),
                MemoryEntry.expires_at < now,
            )
            .all()
        )
        count = len(expired)
        for e in expired:
            session.delete(e)
        session.commit()

    return {"expired": count}
