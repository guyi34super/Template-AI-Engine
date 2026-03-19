# aqee/core/retrieval.py
from typing import Dict, List
from .vdb import VDB, tenant_collection
from .embeddings import embed_texts

def retrieve_doc_context(tenant_id: str, query_text: str, top_k: int = 5):
    vdb = VDB(tenant_collection(tenant_id))
    return vdb.query(query_texts=[query_text], n_results=top_k, where={"tenant_id": tenant_id})
