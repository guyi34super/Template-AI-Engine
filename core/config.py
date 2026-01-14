# aqee/core/config.py
from pathlib import Path
import os

# Import centralized configuration
from .env_config import config

# Paths
ROOT = Path(__file__).resolve().parents[1]
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", ROOT / "data" / "app.db"))
CHROMA_DIR = config.CHROMA_DIR
DOC_LING_MODEL_DIR = Path(os.getenv("DOC_LING_MODEL_DIR", ROOT / "extractors" / "docling" / "models"))

# LLM Configuration
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-large")
MAX_CONTEXT_TOKENS = config.MAX_TOKENS
ADAPTIVE_TOPK_MIN = int(os.getenv("ADAPTIVE_TOPK_MIN", 2))
ADAPTIVE_TOPK_MAX = int(os.getenv("ADAPTIVE_TOPK_MAX", 12))
SIMILARITY_GATE = float(os.getenv("SIMILARITY_GATE", 0.40))

# Databricks Configuration (from env_config)
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
DATABRICKS_LLM_ENDPOINT = os.getenv("DATABRICKS_LLM_ENDPOINT", "")
DATABRICKS_EMBEDDING_ENDPOINT = os.getenv("DATABRICKS_EMBEDDING_ENDPOINT", "")

# Small 7B model for fast validation/cleanup
DATABRICKS_SMALL_LLM_ENDPOINT = os.getenv("DATABRICKS_SMALL_LLM_ENDPOINT", "")

CHROMA_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
