# aqee/core/chunking.py
from typing import List, Dict
import re

def split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

def to_fixed_token_chunks(paragraphs: List[str], target_tokens=512, overlap_tokens=50) -> List[str]:
    # lightweight token approximation by words; swap for tiktoken if desired
    chunks, buf = [], []
    count = 0
    for p in paragraphs:
        words = p.split()
        if count + len(words) > target_tokens and buf:
            chunks.append(" ".join(buf))
            # overlap
            buf = " ".join(buf).split()[-overlap_tokens:]
            buf = buf if isinstance(buf, list) else buf.split()
            count = len(buf)
        buf += words
        count += len(words)
    if buf:
        chunks.append(" ".join(buf))
    return chunks

def quality_score(text: str) -> float:
    # simple heuristic: penalize very short/very long text and noise
    l = len(text)
    if l < 50: return 0.2
    if l > 5000: return 0.5
    return 0.9
