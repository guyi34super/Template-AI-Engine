"""
Async Redis client — session cache, rate-limit counters, idempotency store, job status.

Key patterns (Section 7.2 of architecture spec):
  session:{jti}          → user_id + role   (TTL = access-token lifetime)
  ratelimit:ip:{ip}      → counter          (TTL = 60 s window)
  ratelimit:user:{uid}   → counter          (TTL = 60 s window)
  idempotency:{key}      → response JSON    (TTL = 86 400 s)
  job:{job_id}           → status JSON      (TTL = 3 600 s)
  file_cache:{sha256}    → extraction JSON   (TTL = 86 400 s)
"""
from __future__ import annotations

import json
import os
import logging
from typing import Any, Optional

try:
    import redis.asyncio as aioredis  # redis-py ≥ 4.2
except ImportError:
    aioredis = None  # graceful fallback when redis pkg missing

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global connection pool (overwritten on startup)
# ---------------------------------------------------------------------------
_pool: Optional[Any] = None


def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def init_redis() -> None:
    """Create the shared connection pool.  Call once at app startup."""
    global _pool
    if aioredis is None:
        logger.warning("redis package not installed — Redis features disabled")
        return
    _pool = aioredis.from_url(
        _redis_url(),
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    try:
        await _pool.ping()
        logger.info("Redis connected  (%s)", _redis_url())
    except Exception as exc:
        logger.warning("Redis ping failed (%s) — running without cache", exc)
        _pool = None


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Redis connection closed")


def get_redis() -> Optional[Any]:
    """Return the pool (or None when unavailable)."""
    return _pool


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

async def redis_get(key: str) -> Optional[str]:
    if _pool is None:
        return None
    return await _pool.get(key)


async def redis_set(key: str, value: str, ttl: int | None = None) -> None:
    if _pool is None:
        return
    if ttl:
        await _pool.setex(key, ttl, value)
    else:
        await _pool.set(key, value)


async def redis_delete(key: str) -> None:
    if _pool is None:
        return
    await _pool.delete(key)


async def redis_incr(key: str, ttl: int | None = None) -> int:
    """Increment a counter and optionally set TTL on first creation."""
    if _pool is None:
        return 0
    val = await _pool.incr(key)
    if val == 1 and ttl:
        await _pool.expire(key, ttl)
    return val


# ---------------------------------------------------------------------------
# Domain-specific helpers
# ---------------------------------------------------------------------------

# -- Sessions
async def cache_session(jti: str, user_id: str, role: str, ttl: int = 900) -> None:
    """Cache a JWT session for fast lookup (default 15 min)."""
    await redis_set(f"session:{jti}", json.dumps({"user_id": user_id, "role": role}), ttl)


async def get_session(jti: str) -> Optional[dict]:
    raw = await redis_get(f"session:{jti}")
    return json.loads(raw) if raw else None


async def revoke_session(jti: str) -> None:
    await redis_delete(f"session:{jti}")


# -- Rate-limiting
async def check_rate_limit_ip(ip: str, limit: int = 60, window: int = 60) -> bool:
    """Return True if request is within limit."""
    count = await redis_incr(f"ratelimit:ip:{ip}", ttl=window)
    return count <= limit


async def check_rate_limit_user(user_id: str, limit: int = 120, window: int = 60) -> bool:
    count = await redis_incr(f"ratelimit:user:{user_id}", ttl=window)
    return count <= limit


# -- Idempotency
async def get_idempotency(key: str) -> Optional[dict]:
    raw = await redis_get(f"idempotency:{key}")
    return json.loads(raw) if raw else None


async def set_idempotency(key: str, response: dict, ttl: int = 86_400) -> None:
    await redis_set(f"idempotency:{key}", json.dumps(response), ttl)


# -- Job status
async def set_job_status(job_id: str, status: dict, ttl: int = 3_600) -> None:
    await redis_set(f"job:{job_id}", json.dumps(status), ttl)


async def get_job_status(job_id: str) -> Optional[dict]:
    raw = await redis_get(f"job:{job_id}")
    return json.loads(raw) if raw else None


# -- File cache
async def cache_extraction(sha256: str, data: dict, ttl: int = 86_400) -> None:
    await redis_set(f"file_cache:{sha256}", json.dumps(data), ttl)


async def get_cached_extraction(sha256: str) -> Optional[dict]:
    raw = await redis_get(f"file_cache:{sha256}")
    return json.loads(raw) if raw else None
