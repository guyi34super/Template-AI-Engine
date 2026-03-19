# aqee/core/embeddings.py
from typing import List
import os

# If you’re using OpenAI, uncomment and set key in .env
# from openai import OpenAI
# from .config import OPENAI_API_KEY, EMBED_MODEL
# client = OpenAI(api_key=OPENAI_API_KEY)

def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Replace with your preferred provider. This is a stub returning
    unit vectors for wiring tests. Integrate OpenAI or a local model here.
    """
    # Example (OpenAI):
    # resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    # return [d.embedding for d in resp.data]
    import math
    out = []
    for t in texts:
        # super simple hash-based pseudo-embedding for now (dev wiring)
        h = abs(hash(t)) % 1000
        vec = [math.sin(h), math.cos(h), (h % 7) / 7.0]
        out.append(vec)
    return out
