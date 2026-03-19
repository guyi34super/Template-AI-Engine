"""
Supermemory client — cross-session AI memory (Section 8.3).

Wraps the self-hosted Supermemory REST API for:
  - add_memory()      — store a context snippet
  - search_memory()   — semantic search across stored memories
  - delete_memory()   — remove by id

Includes a simple circuit-breaker: after N consecutive failures the client
stops making outbound calls for a cooldown period, avoiding cascading delays.
"""
from __future__ import annotations

import os
import time
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SUPERMEMORY_URL = os.getenv("SUPERMEMORY_URL", "http://localhost:3100")
SUPERMEMORY_API_KEY = os.getenv("SUPERMEMORY_API_KEY", "")
_TIMEOUT = float(os.getenv("SUPERMEMORY_TIMEOUT", "10"))

# Circuit-breaker settings
_CB_THRESHOLD = int(os.getenv("SUPERMEMORY_CB_THRESHOLD", "5"))
_CB_COOLDOWN = int(os.getenv("SUPERMEMORY_CB_COOLDOWN", "60"))  # seconds

_failures: int = 0
_circuit_open_until: float = 0.0

_client: Optional[httpx.AsyncClient] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if SUPERMEMORY_API_KEY:
        h["Authorization"] = f"Bearer {SUPERMEMORY_API_KEY}"
    return h


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=SUPERMEMORY_URL,
            timeout=_TIMEOUT,
            headers=_headers(),
        )
    return _client


async def close_supermemory() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


def _circuit_open() -> bool:
    return _failures >= _CB_THRESHOLD and time.time() < _circuit_open_until


def _record_success() -> None:
    global _failures, _circuit_open_until
    _failures = 0
    _circuit_open_until = 0.0


def _record_failure() -> None:
    global _failures, _circuit_open_until
    _failures += 1
    if _failures >= _CB_THRESHOLD:
        _circuit_open_until = time.time() + _CB_COOLDOWN
        logger.warning(
            "Supermemory circuit-breaker OPEN — cooling down %ss after %s failures",
            _CB_COOLDOWN, _failures,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def add_memory(content: str, *, user_id: str | None = None, metadata: dict | None = None) -> dict | None:
    """Store a memory snippet. Returns the created memory object or None."""
    if _circuit_open():
        logger.debug("Supermemory circuit open — skipping add_memory")
        return None
    try:
        client = await _get_client()
        payload: dict[str, Any] = {"content": content}
        if user_id:
            payload["userId"] = user_id
        if metadata:
            payload["metadata"] = metadata
        resp = await client.post("/api/memories", json=payload)
        resp.raise_for_status()
        _record_success()
        return resp.json()
    except Exception as exc:
        _record_failure()
        logger.warning("Supermemory add_memory failed: %s", exc)
        return None


async def search_memory(query: str, *, user_id: str | None = None, limit: int = 5) -> list[dict]:
    """Semantic search across stored memories."""
    if _circuit_open():
        return []
    try:
        client = await _get_client()
        params: dict[str, Any] = {"q": query, "limit": limit}
        if user_id:
            params["userId"] = user_id
        resp = await client.get("/api/memories/search", params=params)
        resp.raise_for_status()
        _record_success()
        data = resp.json()
        return data if isinstance(data, list) else data.get("results", [])
    except Exception as exc:
        _record_failure()
        logger.warning("Supermemory search failed: %s", exc)
        return []


async def delete_memory(memory_id: str) -> bool:
    """Delete a memory by ID."""
    if _circuit_open():
        return False
    try:
        client = await _get_client()
        resp = await client.delete(f"/api/memories/{memory_id}")
        resp.raise_for_status()
        _record_success()
        return True
    except Exception as exc:
        _record_failure()
        logger.warning("Supermemory delete failed: %s", exc)
        return False


async def health() -> dict:
    """Check Supermemory health endpoint."""
    try:
        client = await _get_client()
        resp = await client.get("/api/health")
        return {"status": "ok", "code": resp.status_code}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
