"""
Embedding Client — v2.1 spec Section 8.3.

Separate from llm_client.py; dedicated to embedding operations.

Features:
  - Dual model support (fast small model + high-quality large model)
  - SHA-256 Redis cache to avoid re-embedding identical texts
  - Batch embedding (up to 32 texts per request)
  - Async with retry logic
"""
from __future__ import annotations

import os
import json
import hashlib
import logging
import asyncio
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Config ──
HF_API_TOKEN: str | None = os.getenv("HUGGINGFACE_API_TOKEN")
HF_BASE_URL = os.getenv("HUGGINGFACE_API_URL", "https://api-inference.huggingface.co")

# Dual models
EMBED_MODEL_FAST = os.getenv("HF_EMBED_MODEL_FAST", "sentence-transformers/all-MiniLM-L6-v2")
EMBED_MODEL_QUALITY = os.getenv("HF_EMBED_MODEL_QUALITY", "sentence-transformers/all-mpnet-base-v2")

# Defaults
EMBED_TIMEOUT = float(os.getenv("EMBED_TIMEOUT_SEC", "60"))
EMBED_MAX_RETRIES = int(os.getenv("EMBED_MAX_RETRIES", "3"))
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "32"))
EMBED_CACHE_TTL = int(os.getenv("EMBED_CACHE_TTL_SEC", "86400"))  # 24h

# Model dimensions
MODEL_DIMS = {
    EMBED_MODEL_FAST: 384,
    EMBED_MODEL_QUALITY: 768,
}

_client: Optional[httpx.AsyncClient] = None


def _headers() -> dict:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if HF_API_TOKEN:
        h["Authorization"] = f"Bearer {HF_API_TOKEN}"
    return h


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=EMBED_TIMEOUT, headers=_headers())
    return _client


async def close_embedding_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


# ── Cache helpers ──
def _cache_key(text: str, model: str) -> str:
    """SHA-256 of text+model → Redis key."""
    h = hashlib.sha256(f"{model}:{text}".encode()).hexdigest()
    return f"embed_cache:{h}"


async def _cache_get(key: str) -> Optional[list[float]]:
    """Try Redis cache for cached embedding."""
    try:
        from core.redis_client import _pool
        if _pool is None:
            return None
        val = await _pool.get(key)
        if val:
            return json.loads(val)
    except Exception:
        pass
    return None


async def _cache_set(key: str, vector: list[float]) -> None:
    """Store embedding in Redis cache with TTL."""
    try:
        from core.redis_client import _pool
        if _pool is None:
            return
        await _pool.setex(key, EMBED_CACHE_TTL, json.dumps(vector))
    except Exception:
        pass


# ── Raw API call ──
async def _embed_raw(texts: list[str], model: str) -> list[list[float]]:
    """Call HuggingFace inference API for embeddings."""
    if not HF_API_TOKEN:
        dim = MODEL_DIMS.get(model, 384)
        logger.warning("HUGGINGFACE_API_TOKEN not set — returning zero vectors (dim=%d)", dim)
        return [[0.0] * dim for _ in texts]

    url = f"{HF_BASE_URL}/pipeline/feature-extraction/{model}"
    client = await _get_client()
    last_exc: Exception | None = None

    for attempt in range(1, EMBED_MAX_RETRIES + 1):
        try:
            resp = await client.post(url, json={
                "inputs": texts,
                "options": {"wait_for_model": True},
            })
            if resp.status_code == 503:
                wait = resp.json().get("estimated_time", 20)
                logger.info("Embedding model loading, retry in %ss (attempt %d)", wait, attempt)
                await asyncio.sleep(min(wait, 60))
                continue
            resp.raise_for_status()
            data = resp.json()

            # HF returns nested arrays — may need mean pooling
            vectors = []
            for item in data:
                if isinstance(item, list) and isinstance(item[0], list):
                    # Token-level embeddings — mean pool
                    import numpy as np
                    arr = np.array(item)
                    vectors.append(arr.mean(axis=0).tolist())
                elif isinstance(item, list):
                    vectors.append(item)
                else:
                    vectors.append([0.0] * MODEL_DIMS.get(model, 384))
            return vectors

        except httpx.HTTPStatusError as exc:
            last_exc = exc
            logger.warning("Embed HTTP %s on attempt %d", exc.response.status_code, attempt)
        except Exception as exc:
            last_exc = exc
            logger.warning("Embed error on attempt %d: %s", attempt, exc)
        await asyncio.sleep(2 ** attempt)

    logger.error("Embedding failed after %d attempts: %s", EMBED_MAX_RETRIES, last_exc)
    dim = MODEL_DIMS.get(model, 384)
    return [[0.0] * dim for _ in texts]


# ── Public API ──
async def embed_text(text: str, *, model: str | None = None, use_cache: bool = True) -> list[float]:
    """Embed a single text string (with Redis cache)."""
    model = model or EMBED_MODEL_FAST

    if use_cache:
        key = _cache_key(text, model)
        cached = await _cache_get(key)
        if cached:
            return cached

    vectors = await _embed_raw([text], model)
    result = vectors[0] if vectors else [0.0] * MODEL_DIMS.get(model, 384)

    if use_cache:
        await _cache_set(_cache_key(text, model), result)

    return result


async def embed_batch(
    texts: list[str],
    *,
    model: str | None = None,
    use_cache: bool = True,
) -> list[list[float]]:
    """Embed a batch of texts (up to 32 per API call), with per-text Redis cache."""
    model = model or EMBED_MODEL_FAST
    results: list[Optional[list[float]]] = [None] * len(texts)
    to_embed: list[tuple[int, str]] = []

    # Check cache first
    if use_cache:
        for i, text in enumerate(texts):
            key = _cache_key(text, model)
            cached = await _cache_get(key)
            if cached:
                results[i] = cached
            else:
                to_embed.append((i, text))
    else:
        to_embed = list(enumerate(texts))

    # Batch embed uncached texts
    if to_embed:
        for start in range(0, len(to_embed), EMBED_BATCH_SIZE):
            batch = to_embed[start:start + EMBED_BATCH_SIZE]
            batch_texts = [t for _, t in batch]
            vectors = await _embed_raw(batch_texts, model)
            for (idx, text), vec in zip(batch, vectors):
                results[idx] = vec
                if use_cache:
                    await _cache_set(_cache_key(text, model), vec)

    # Fill any remaining None with zero vectors
    dim = MODEL_DIMS.get(model, 384)
    return [v if v is not None else [0.0] * dim for v in results]


async def embed_text_quality(text: str, *, use_cache: bool = True) -> list[float]:
    """Embed using the high-quality (larger) model."""
    return await embed_text(text, model=EMBED_MODEL_QUALITY, use_cache=use_cache)


async def embed_batch_quality(texts: list[str], *, use_cache: bool = True) -> list[list[float]]:
    """Batch embed using the high-quality (larger) model."""
    return await embed_batch(texts, model=EMBED_MODEL_QUALITY, use_cache=use_cache)
