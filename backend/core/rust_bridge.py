"""
Python → Rust bridge client (Section 3.2 of v2.1 spec).

All communication with the Rust data-tier micro-service goes through this module.
Requests are signed with HMAC-SHA256 using a shared secret.

Provides async helpers for:
  - Parsing: parse_xlsx, parse_csv, parse_docx, parse_pdf_meta
  - Validation: validate_batch, test_pattern
  - Hashing: hash_data, hash_fields, hash_file, verify_diff
  - Coercion: coerce_batch
  - Chunking: chunk_text
  - Auth: verify_jwt
  - Memory: build_keyword_index
  - Rate limit: check_rate_limit
"""
from __future__ import annotations

import os
import json
import hmac
import hashlib
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RUST_BASE_URL = os.getenv("RUST_SERVICE_URL", "http://localhost:8001")
RUST_HMAC_SECRET = os.getenv("RUST_HMAC_SECRET", "dev-hmac-secret")
RUST_TIMEOUT = float(os.getenv("RUST_TIMEOUT_SEC", "30"))

# Shared async client (created lazily)
_client: Optional[httpx.AsyncClient] = None


def _hmac_sign(body: bytes) -> str:
    """Compute HMAC-SHA256 of the request body."""
    return hmac.new(
        RUST_HMAC_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=RUST_BASE_URL,
            timeout=RUST_TIMEOUT,
        )
    return _client


async def close_rust_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def _post_json(path: str, payload: Any) -> dict:
    """POST JSON to Rust service with HMAC signature."""
    client = await _get_client()
    body = json.dumps(payload, default=str).encode()
    sig = _hmac_sign(body)
    resp = await client.post(
        path,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hmac-Signature": sig,
        },
    )
    resp.raise_for_status()
    return resp.json()


async def _post_bytes(path: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    """POST raw bytes to Rust service with HMAC signature."""
    client = await _get_client()
    sig = _hmac_sign(data)
    resp = await client.post(
        path,
        content=data,
        headers={
            "Content-Type": content_type,
            "X-Hmac-Signature": sig,
        },
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
async def rust_health() -> dict:
    """Check Rust service health."""
    client = await _get_client()
    resp = await client.get("/health")
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
async def parse_xlsx(file_bytes: bytes) -> dict:
    """Send XLSX bytes to Rust for parsing → structured sheets/rows."""
    return await _post_bytes("/parse/xlsx", file_bytes)


async def parse_csv(file_bytes: bytes) -> dict:
    """Send CSV bytes to Rust for parsing → headers + rows."""
    return await _post_bytes("/parse/csv", file_bytes, "text/csv")


async def parse_docx(file_bytes: bytes) -> dict:
    """Send DOCX bytes to Rust for parsing → paragraphs + text."""
    return await _post_bytes("/parse/docx", file_bytes)


async def parse_pdf_meta(file_bytes: bytes) -> dict:
    """Send PDF bytes to Rust for metadata extraction."""
    return await _post_bytes("/parse/pdf-meta", file_bytes, "application/pdf")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
async def validate_batch(items: list[dict]) -> list[dict]:
    """
    Batch validate fields via Rust Rayon parallel engine.
    
    items: [{"field": "email", "value": "x@y.com", "pattern": "^[\\w.]+@..."}]
    Returns: [{"field": "email", "valid": true, "error": null}]
    """
    return await _post_json("/validate/batch", items)


async def test_pattern(pattern: str, sample_values: list[str]) -> dict:
    """Test a regex pattern against sample values."""
    return await _post_json("/validate/test-pattern", {
        "pattern": pattern,
        "sample_values": sample_values,
    })


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------
async def hash_data(data: str) -> str:
    """SHA-256 hash of a string → returns hex digest."""
    result = await _post_json("/hash", {"data": data})
    return result.get("sha256", "")


async def hash_fields(fields: dict) -> dict:
    """Hash every field value → {field: sha256}."""
    return await _post_json("/hash/fields", fields)


async def hash_file(file_bytes: bytes) -> dict:
    """Stream file bytes to Rust → {sha256, size_bytes}."""
    return await _post_bytes("/hash/file", file_bytes)


async def verify_diff(original: dict, current: dict) -> dict:
    """Compare two versions of a document → changed/added/removed fields."""
    return await _post_json("/hash/verify-diff", {
        "original": original,
        "current": current,
    })


# ---------------------------------------------------------------------------
# Coercion
# ---------------------------------------------------------------------------
async def coerce_batch(items: list[dict]) -> list[dict]:
    """
    Batch type-coerce extracted values.
    
    items: [{"field": "age", "value": "25", "target_type": "integer"}]
    """
    return await _post_json("/coerce/batch", items)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
async def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> dict:
    """Split text into overlapping chunks via Rust."""
    return await _post_json("/chunk/text", {
        "text": text,
        "chunk_size": chunk_size,
        "overlap": overlap,
    })


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def verify_jwt(token: str, algorithm: str = "HS256") -> dict:
    """Delegate JWT verification to Rust → {valid, claims, error}."""
    return await _post_json("/auth/verify-jwt", {
        "token": token,
        "algorithm": algorithm,
    })


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------
async def build_keyword_index(entries: list[dict]) -> dict:
    """
    Build keyword index for memory entries via Rust Rayon.
    
    entries: [{"id": "...", "text": "...", "metadata": {...}}]
    """
    return await _post_json("/memory/index", {"entries": entries})


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
async def check_rate_limit(key: str, limit: int, window_secs: int) -> dict:
    """Check rate limit via Rust in-memory sliding window."""
    return await _post_json("/ratelimit/check", {
        "key": key,
        "limit": limit,
        "window_secs": window_secs,
    })
