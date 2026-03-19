# aqee/core/templates.py
import json
import uuid
from typing import Dict, List, Optional
from sqlalchemy import select
from .config import SIMILARITY_GATE
from .vdb import VDB, template_collection
from .embeddings import embed_texts
import json, re
from .db import SessionLocal
from .models import Template

def create_or_update_template(name: str, header_json: Dict, notes: str = "", source_doc_id: str | None = None) -> str:
    tid = str(uuid.uuid4())
    with SessionLocal() as s:
        t = Template(id=tid, name=name, header_json=json.dumps(header_json), notes=notes, source_doc_id=source_doc_id)
        s.add(t); s.commit()
    return tid

def classify_template(header_candidates: List[str]) -> Dict:
    """Return best template match or {} if none pass the gate."""
    vdb = VDB(template_collection())
    query_text = " | ".join(header_candidates[:64]) or "document"
    result = vdb.query(query_texts=[query_text], n_results=5)
    if not result or not result.get("metadatas"):
        return {}

    # Chroma returns lists
    metadatas = result["metadatas"][0]
    distances = result["distances"][0] if "distances" in result else None
    ids = result["ids"][0]

    # Convert distances to similarity if distances present (cosine)
    scored = []
    for i, md in enumerate(metadatas):
        sim = 1.0 - distances[i] if distances else 0.0
        scored.append((sim, md.get("template_id"), ids[i]))

    scored.sort(reverse=True, key=lambda x: x[0])
    top_sim, top_tid, _ = scored[0]
    if top_sim >= SIMILARITY_GATE:
        with SessionLocal() as s:
            t: Template | None = s.get(Template, top_tid)
            if not t: return {}
            return {"id": t.id, "name": t.name, "similarity": round(top_sim, 4), "header_json": json.loads(t.header_json)}
    return {}

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")

def index_template_text(template_id: str, tenant_id: str, text_chunks: List[str]):
    """Index non-empty text chunks as template vectors; safe against empties."""
    from .vdb import VDB, template_collection
    from .embeddings import embed_texts
    docs = [ (t or "").strip() for t in (text_chunks or []) if (t or "").strip() ]
    if not docs:
        print(f"[seed:skip] template={template_id} (no non-empty text)")
        return
    ids = [f"{template_id}:tpl:{i}" for i in range(len(docs))]
    metas = [{"tenant_id": tenant_id, "template_id": template_id, "page": None, "kind": "template"} for _ in docs]
    vecs = embed_texts(docs)
    if not vecs:
        print(f"[seed:skip] template={template_id} (no embeddings produced)")
        return
    VDB(template_collection()).upsert(ids=ids, embeddings=vecs, metadatas=metas, documents=docs)

def index_template_fields(template_id: str, tenant_id: str, fields: List[Dict]):
    """One embedding per field with rich metadata for precise retrieval."""
    from .vdb import VDB, template_collection
    from .embeddings import embed_texts
    docs, ids, metas = [], [], []
    for f in fields or []:
        name = (f.get("name") or "").strip()
        if not name: 
            continue
        card = (
            f"Template:{template_id} | Field:{name} | "
            f"Type:{f.get('data_type','')} | "
            f"LengthFormat:{f.get('length_format','')} | "
            f"Required:{f.get('required','')} | "
            f"Allowed:{', '.join(f.get('allowed_values',[]) or [])} | "
            f"Notes:{f.get('special','')}"
        )
        docs.append(card)
        ids.append(f"{template_id}:field:{_slug(name)}")
        metas.append({
            "tenant_id": tenant_id,
            "template_id": template_id,
            "kind": "field",
            "field_name": name,
            "data_type": f.get("data_type"),
            "length_format": f.get("length_format"),
            "required": f.get("required"),
            "allowed_values": f.get("allowed_values"),
        })
    if not docs:
        print(f"[seed:skip] template={template_id} (no fields)")
        return
    vecs = embed_texts(docs)
    if not vecs:
        print(f"[seed:skip] template={template_id} (no embeddings for fields)")
        return
    VDB(template_collection()).upsert(ids=ids, embeddings=vecs, metadatas=metas, documents=docs)

def upsert_template_fields_json(template_id: str, fields: List[Dict]):
    """Merge parsed fields into Template.header_json under 'fields'; keep existing 'columns'."""
    with SessionLocal() as s:
        t = s.get(Template, template_id)
        if not t:
            return
        cur = json.loads(t.header_json) if t.header_json else {}
        existing = { (f.get("name") or f"f{i}"): f for i, f in enumerate(cur.get("fields", [])) }
        for f in (fields or []):
            name = f.get("name") or f"f{len(existing)}"
            existing[name] = f
        cur["fields"] = list(existing.values())
        t.header_json = json.dumps(cur)
        s.add(t); s.commit()