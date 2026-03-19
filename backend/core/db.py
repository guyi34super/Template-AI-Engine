"""
Database layer for AI-RAG Engine.
Supports async PostgreSQL (production) and sync SQLite (development fallback).
"""

import os
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

Base = declarative_base()

# ---------------------------------------------------------------------------
# Detect database URL – prefer async PostgreSQL, fall back to sync SQLite
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")
_USE_ASYNC = DATABASE_URL.startswith("postgresql")

if _USE_ASYNC:
    # ---- Async PostgreSQL (production) ----
    async_engine = create_async_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=15,
        pool_pre_ping=True,
        echo=False,
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    # Sync engine / session set to None when running async
    engine = None
    SessionLocal = None
else:
    # ---- Sync SQLite (development) ----
    from .config import SQLITE_PATH

    engine = create_engine(
        f"sqlite:///{SQLITE_PATH}",
        future=True,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False, future=True
    )
    async_engine = None
    AsyncSessionLocal = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@asynccontextmanager
async def get_async_session():
    """Yield an async PostgreSQL session (production)."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Async DB not configured – set DATABASE_URL")
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_sync_session() -> Session:
    """Return a sync SQLite session (development)."""
    if SessionLocal is None:
        raise RuntimeError("Sync DB not configured")
    return SessionLocal()


def is_async_db() -> bool:
    """True when running against PostgreSQL."""
    return _USE_ASYNC


async def init_async_db():
    """Create all tables (async PostgreSQL)."""
    from . import models  # noqa: F401 – ensure models are imported
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_db():
    """Create all tables (sync SQLite)."""
    from . import models  # noqa: F401
    if engine is not None:
        Base.metadata.create_all(bind=engine)
