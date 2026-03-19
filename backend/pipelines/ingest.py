# aqee/pipelines/ingest.py
from typing import Dict, Any, List, Tuple
from uuid import uuid4
from sqlalchemy import select, delete
from ..core.db import SessionLocal
from ..core.models import Document, Chunk
from ..core.hashing import sha256_text
from ..core.chunking import split_paragraphs, to_fixed_token_chunks, quality_score
from ..core.embeddings import embed_texts
from ..core.vdb import VDB, tenant_collection
from ..core.config import ADAPTIVE_TOPK_MIN
from ..core import config

def _store_document_row(tenant_id: str, path: str, name: str, mime: str, sha256: str) -> str:
    doc_id = str(uuid4())
    with SessionLocal() as s:
        d = Document(id=doc_id, tenant_id=tenant_id, name=name, mime=mime, path=path, size_bytes=None, sha256=sha256, status="ready")
        s.add(d); s.commit()
    return doc_id

def _to_chunks(doc_id: str, tenant_id: str, text_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chunks = []
    for tb in text_blocks:
        paras = split_paragraphs(tb["text"])
        fixed = to_fixed_token_chunks(paras, target_tokens=512, overlap_tokens=50)
        start = 0
        for c in fixed:
            chash = sha256_text(c)
            chunks.append({
                "id": str(uuid4()),
                "doc_id": doc_id,
                "tenant_id": tenant_id,
                "page": tb.get("page", 1),
                "start": start,
                "end": start + len(c),
                "chunk_id": str(uuid4()),
                "chunk_hash": chash,
                "text": c,
                "quality_score": quality_score(c)
            })
            start += len(c)
    return chunks

def _persist_chunks(chunks: List[Dict[str, Any]]):
    with SessionLocal() as s:
        for c in chunks:
            s.add(Chunk(**c))
        s.commit()

def _upsert_vectors(tenant_id: str, chunks: List[Dict[str, Any]]):
    vdb = VDB(tenant_collection(tenant_id))
    texts = [c["text"] for c in chunks]
    vecs = embed_texts(texts)
    ids = [c["chunk_id"] for c in chunks]
    metas = [{
        "tenant_id": tenant_id,
        "doc_id": c["doc_id"],
        "page": c["page"],
        "start": c["start"],
        "end": c["end"],
        "chunk_id": c["chunk_id"],
        "chunk_hash": c["chunk_hash"]
    } for c in chunks]
    vdb.upsert(ids=ids, embeddings=vecs, metadatas=metas, documents=texts)

def ingest_intermediate(tenant_id: str, name: str, mime: str, path: str, intermediate: Dict[str, Any]) -> str:
    sha = sha256_text((intermediate.get("text_blocks") or [name, path]).__repr__())
    doc_id = _store_document_row(tenant_id=tenant_id, path=path, name=name, mime=mime, sha256=sha)

    text_blocks = intermediate.get("text_blocks", [])
    chunks = _to_chunks(doc_id, tenant_id, text_blocks)
    if chunks:
        _persist_chunks(chunks)
        _upsert_vectors(tenant_id, chunks)
    return doc_id
