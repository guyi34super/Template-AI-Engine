"""
Configuration management for AI-RAG Engine
Loads environment variables from .env file
"""

import os
from pathlib import Path
from typing import Optional


def load_env_file(env_path: Optional[str] = None):
    """Load environment variables from .env file"""
    if env_path is None:
        env_path = Path(__file__).parent.parent / ".env"
    else:
        env_path = Path(env_path)
    
    if not env_path.exists():
        print(f"⚠️ No .env file found at {env_path}. Using system environment variables.")
        return
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value


# Load .env on module import
load_env_file()


# Configuration class
class Config:
    """Application configuration"""
    
    # Databricks
    DATABRICKS_TOKEN: str = os.getenv("DATABRICKS_TOKEN", "")
    DATABRICKS_LLM_ENDPOINT: str = os.getenv(
        "DATABRICKS_LLM_ENDPOINT",
        "https://adb-2013026601306673.13.azuredatabricks.net/serving-endpoints/databricks-meta-llama-3-3-70b-instruct/invocations"
    )
    DATABRICKS_SMALL_LLM_ENDPOINT: str = os.getenv("DATABRICKS_SMALL_LLM_ENDPOINT", "databricks-meta-llama-3-1-8b-instruct")
    DATABRICKS_EMBEDDING_ENDPOINT: str = os.getenv("DATABRICKS_EMBEDDING_ENDPOINT", "databricks-gte-large-en")
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    RELOAD: bool = os.getenv("RELOAD", "false").lower() == "true"
    
    # Paths
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", "output/uploads"))
    EXTRACT_DIR: Path = Path(os.getenv("EXTRACT_DIR", "output/extract"))
    MAPPING_DIR: Path = Path(os.getenv("MAPPING_DIR", "output/mapping"))
    CHAT_DIR: Path = Path(os.getenv("CHAT_DIR", "output/chat"))
    CHROMA_DIR: Path = Path(os.getenv("CHROMA_DIR", "data/chroma"))
    MEMORY_DB: Path = Path(os.getenv("MEMORY_DB", "power_memory/data/memory_graph.db"))
    SESSION_DB: Path = Path(os.getenv("SESSION_DB", "power_memory/data/sessions.db"))
    
    # LLM
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "8000"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
    TOP_P: float = float(os.getenv("TOP_P", "0.9"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories"""
        for path in [cls.UPLOAD_DIR, cls.EXTRACT_DIR, cls.MAPPING_DIR, cls.CHAT_DIR]:
            path.mkdir(parents=True, exist_ok=True)
        
        # Create data directory
        cls.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        cls.MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
        cls.SESSION_DB.parent.mkdir(parents=True, exist_ok=True)


# Initialize config
config = Config()
