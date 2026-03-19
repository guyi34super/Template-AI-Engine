"""
Memory Store — PostgreSQL-backed CRUD for memory_entries and memory_keyword_index.

Uses async SQLAlchemy sessions; falls back to sync when needed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
import uuid

from core.db import get_sync_session, is_async_db

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryStore:
    """PostgreSQL-backed memory entry CRUD."""

    # ── Create ──
    @staticmethod
    def create(
        user_id: str,
        context_summary: str,
        memory_type: str = "general",
        memory_id: Optional[str] = None,
        embedding_id: Optional[str] = None,
        keywords: Optional[list[str]] = None,
        importance_score: float = 0.5,
        expires_at: Optional[datetime] = None,
    ) -> dict:
        """Create a new memory entry + keyword index rows."""
        from core.models import MemoryEntry, MemoryKeywordIndex

        entry_id = str(uuid.uuid4())

        if is_async_db():
            with get_sync_session() as session:
                entry = MemoryEntry(
                    id=entry_id,
                    user_id=user_id,
                    memory_id=memory_id,
                    memory_type=memory_type,
                    context_summary=context_summary,
                    embedding_id=embedding_id,
                    keywords=keywords,
                    importance_score=importance_score,
                    expires_at=expires_at,
                )
                session.add(entry)

                # Insert keyword index entries
                if keywords:
                    for kw in keywords:
                        session.add(MemoryKeywordIndex(
                            id=str(uuid.uuid4()),
                            memory_id=entry_id,
                            keyword=kw.lower(),
                            tf_score=1.0 / len(keywords),
                        ))

                session.commit()
                return {
                    "id": entry_id,
                    "user_id": user_id,
                    "memory_type": memory_type,
                    "context_summary": context_summary,
                    "keywords": keywords,
                    "importance_score": importance_score,
                }
        else:
            logger.warning("PostgreSQL not available — memory not persisted")
            return {"id": entry_id, "user_id": user_id, "context_summary": context_summary}

    # ── Read by ID ──
    @staticmethod
    def get(entry_id: str) -> Optional[dict]:
        if not is_async_db():
            return None
        from core.models import MemoryEntry
        with get_sync_session() as session:
            entry = session.query(MemoryEntry).filter(MemoryEntry.id == entry_id).first()
            if not entry:
                return None
            # Bump access count
            entry.access_count = (entry.access_count or 0) + 1
            entry.last_accessed = _now()
            session.commit()
            return _entry_to_dict(entry)

    # ── Search by keyword ──
    @staticmethod
    def search_by_keywords(user_id: str, keywords: list[str], limit: int = 20) -> list[dict]:
        """Pre-filter memories by keyword index (Stage 1 of two-stage retrieval)."""
        if not is_async_db():
            return []
        from core.models import MemoryEntry, MemoryKeywordIndex
        from sqlalchemy import func

        with get_sync_session() as session:
            # Find memory IDs matching any keyword, ranked by match count
            lower_kws = [k.lower() for k in keywords]
            subq = (
                session.query(
                    MemoryKeywordIndex.memory_id,
                    func.count(MemoryKeywordIndex.id).label("match_count"),
                    func.sum(MemoryKeywordIndex.tf_score).label("total_tf"),
                )
                .filter(MemoryKeywordIndex.keyword.in_(lower_kws))
                .group_by(MemoryKeywordIndex.memory_id)
                .order_by(func.count(MemoryKeywordIndex.id).desc())
                .limit(limit * 2)  # Over-fetch for re-ranking
                .subquery()
            )
            entries = (
                session.query(MemoryEntry)
                .join(subq, MemoryEntry.id == subq.c.memory_id)
                .filter(MemoryEntry.user_id == user_id)
                .filter(MemoryEntry.expires_at.is_(None) | (MemoryEntry.expires_at > _now()))
                .order_by(subq.c.match_count.desc())
                .limit(limit)
                .all()
            )
            return [_entry_to_dict(e) for e in entries]

    # ── List by user ──
    @staticmethod
    def list_by_user(user_id: str, memory_type: Optional[str] = None, limit: int = 50) -> list[dict]:
        if not is_async_db():
            return []
        from core.models import MemoryEntry
        with get_sync_session() as session:
            q = session.query(MemoryEntry).filter(MemoryEntry.user_id == user_id)
            if memory_type:
                q = q.filter(MemoryEntry.memory_type == memory_type)
            q = q.filter(MemoryEntry.expires_at.is_(None) | (MemoryEntry.expires_at > _now()))
            entries = q.order_by(MemoryEntry.created_at.desc()).limit(limit).all()
            return [_entry_to_dict(e) for e in entries]

    # ── Delete ──
    @staticmethod
    def delete(entry_id: str) -> bool:
        if not is_async_db():
            return False
        from core.models import MemoryEntry
        with get_sync_session() as session:
            entry = session.query(MemoryEntry).filter(MemoryEntry.id == entry_id).first()
            if not entry:
                return False
            session.delete(entry)  # Cascades to keyword_index
            session.commit()
            return True

    # ── Update importance ──
    @staticmethod
    def update_importance(entry_id: str, score: float) -> bool:
        if not is_async_db():
            return False
        from core.models import MemoryEntry
        with get_sync_session() as session:
            entry = session.query(MemoryEntry).filter(MemoryEntry.id == entry_id).first()
            if not entry:
                return False
            entry.importance_score = max(0.0, min(1.0, score))
            session.commit()
            return True


def _entry_to_dict(entry) -> dict:
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "memory_id": entry.memory_id,
        "memory_type": entry.memory_type,
        "context_summary": entry.context_summary,
        "embedding_id": entry.embedding_id,
        "keywords": entry.keywords,
        "importance_score": entry.importance_score,
        "access_count": entry.access_count,
        "last_accessed": str(entry.last_accessed) if entry.last_accessed else None,
        "expires_at": str(entry.expires_at) if entry.expires_at else None,
        "created_at": str(entry.created_at) if entry.created_at else None,
    }
