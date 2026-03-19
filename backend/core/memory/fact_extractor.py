"""
Fact Extractor — extract structured facts from text using the LLM.

Takes chat messages or document text and identifies:
  - Factual statements
  - User preferences
  - Corrections to previous facts
  - General context
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """You are a fact extraction engine. Given the following text, extract structured facts.

Return a JSON array where each item has:
- "text": the fact or statement (string)
- "type": one of "fact", "preference", "correction", "general"
- "importance": float 0.0 to 1.0 (how important/permanent this fact is)
- "keywords": array of 2-5 keywords

Text:
\"\"\"
{text}
\"\"\"

Return ONLY valid JSON array, no other text."""


async def extract_facts(text: str) -> list[dict[str, Any]]:
    """Use LLM to extract structured facts from text."""
    try:
        from core.llm_client import chat_completion
        prompt = EXTRACT_PROMPT.format(text=text[:4000])  # Limit input size
        response = await chat_completion(
            [{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.1,
        )
        # Parse JSON from response
        cleaned = response.strip()
        # Handle potential markdown code blocks
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        facts = json.loads(cleaned)
        if isinstance(facts, list):
            return facts
        return []
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM fact extraction response")
        return []
    except Exception as e:
        logger.error("Fact extraction failed: %s", e)
        return []


def extract_keywords_simple(text: str) -> list[str]:
    """Simple keyword extraction without LLM (fallback)."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through",
        "and", "or", "but", "not", "if", "that", "this", "it", "its",
    }
    words = text.lower().split()
    keywords = []
    seen = set()
    for w in words:
        cleaned = "".join(c for c in w if c.isalnum() or c in "-_")
        if len(cleaned) > 2 and cleaned not in stop_words and cleaned not in seen:
            seen.add(cleaned)
            keywords.append(cleaned)
    return keywords[:20]
