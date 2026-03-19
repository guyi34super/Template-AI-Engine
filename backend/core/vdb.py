# aqee/core/vdb.py
from typing import Dict, List, Optional, Tuple
from chromadb import PersistentClient
from chromadb.utils import embedding_functions
from .config import CHROMA_DIR
from .embeddings import embed_texts

# We’ll call embed_texts ourselves so we can swap providers easily.
# Chroma will receive vectors directly.

class VDB:
    def __init__(self, collection_name: str):
        self.client = PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def upsert(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict],
        documents: Optional[List[str]] = None,
    ):
        self.collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    def query(
        self,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 5,
        where: Optional[Dict] = None,
    ):
        if query_embeddings is None and query_texts is not None:
            query_embeddings = embed_texts(query_texts)
        return self.collection.query(query_embeddings=query_embeddings, n_results=n_results, where=where)

def tenant_collection(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"

def template_collection() -> str:
    return "templates"
