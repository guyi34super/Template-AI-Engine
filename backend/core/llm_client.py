"""
LLM client — wraps HuggingFace Inference API (Section 8.2).

Provides:
  - chat_completion()  — structured message-based completions
  - embed_text()       — text → vector (via sentence-transformers endpoint)
  - classify_intent()  — lightweight intent detection helper

Falls back to a local stub when HUGGINGFACE_API_TOKEN is not set.
"""
from __future__ import annotations

import os
import json
import logging
import asyncio
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

HF_API_TOKEN: str | None = os.getenv("HUGGINGFACE_API_TOKEN")
HF_BASE_URL = os.getenv("HUGGINGFACE_API_URL", "https://api-inference.huggingface.co")
HF_CHAT_MODEL = os.getenv("HF_CHAT_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
HF_EMBED_MODEL = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Retry / timeout config
_TIMEOUT = float(os.getenv("LLM_TIMEOUT_SEC", "120"))
_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))

# Shared async client (created lazily)
_client: Optional[httpx.AsyncClient] = None


def _headers() -> dict:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if HF_API_TOKEN:
        h["Authorization"] = f"Bearer {HF_API_TOKEN}"
    return h


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=_TIMEOUT, headers=_headers())
    return _client


async def close_llm_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


# ---------------------------------------------------------------------------
# Chat completion
# ---------------------------------------------------------------------------
async def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    stop: list[str] | None = None,
) -> str:
    """
    Send a chat-completion request to HuggingFace Inference API.

    messages example: [{"role": "user", "content": "Hello"}]
    Returns the assistant reply as plain text.
    """
    model = model or HF_CHAT_MODEL
    if not HF_API_TOKEN:
        logger.warning("HUGGINGFACE_API_TOKEN not set — returning stub response")
        return "[LLM stub] no API key configured"

    url = f"{HF_BASE_URL}/models/{model}"
    # HF Inference API expects "inputs" field for text-generation
    prompt = _messages_to_prompt(messages)
    payload: dict[str, Any] = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "return_full_text": False,
        },
    }
    if stop:
        payload["parameters"]["stop"] = stop

    client = await _get_client()
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = await client.post(url, json=payload)
            if resp.status_code == 503:
                # Model loading — retry after estimated time
                wait = resp.json().get("estimated_time", 20)
                logger.info("Model loading, retrying in %ss (attempt %s)", wait, attempt)
                await asyncio.sleep(min(wait, 60))
                continue
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0].get("generated_text", "")
            return str(data)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            logger.warning("LLM HTTP %s on attempt %s", exc.response.status_code, attempt)
        except Exception as exc:
            last_exc = exc
            logger.warning("LLM error on attempt %s: %s", attempt, exc)
        await asyncio.sleep(2 ** attempt)

    logger.error("LLM failed after %s attempts: %s", _MAX_RETRIES, last_exc)
    return "[LLM error] request failed"


def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
    """Convert chat-style messages to a single prompt string for HF text-gen."""
    parts: list[str] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            parts.append(f"[INST] <<SYS>>\n{content}\n<</SYS>>\n")
        elif role == "user":
            parts.append(f"[INST] {content} [/INST]")
        else:
            parts.append(content)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
async def embed_text(text: str, *, model: str | None = None) -> list[float]:
    """Return embedding vector for a single text string."""
    model = model or HF_EMBED_MODEL
    if not HF_API_TOKEN:
        logger.warning("HUGGINGFACE_API_TOKEN not set — returning zero vector")
        return [0.0] * 384

    url = f"{HF_BASE_URL}/pipeline/feature-extraction/{model}"
    client = await _get_client()
    resp = await client.post(url, json={"inputs": text, "options": {"wait_for_model": True}})
    resp.raise_for_status()
    data = resp.json()
    # HF returns nested list — flatten
    if isinstance(data, list) and isinstance(data[0], list):
        # Mean-pool token embeddings
        import numpy as np
        arr = __import__("numpy").array(data[0])
        return arr.mean(axis=0).tolist()
    return data


async def embed_batch(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    """Embed a batch of texts in parallel."""
    tasks = [embed_text(t, model=model) for t in texts]
    return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Intent classification (convenience)
# ---------------------------------------------------------------------------
async def classify_intent(text: str, intents: list[str]) -> str:
    """Ask the LLM to pick the best intent label for the given text."""
    prompt = (
        f"Classify the following text into one of these categories: {', '.join(intents)}.\n"
        f"Text: \"{text}\"\n"
        f"Category:"
    )
    result = await chat_completion(
        [{"role": "user", "content": prompt}],
        max_tokens=20,
        temperature=0.0,
    )
    # Simple extraction — first word that matches an intent
    result_lower = result.strip().lower()
    for intent in intents:
        if intent.lower() in result_lower:
            return intent
    return intents[0]  # default
