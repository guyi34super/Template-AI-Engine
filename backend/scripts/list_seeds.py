# ai-engine/scripts/list_seeds.py
from __future__ import annotations
from sqlalchemy import select
from core.db import init_db, SessionLocal
from core.models import Template
from core.vdb import VDB, template_collection
import textwrap

def _count_vectors_for_template(tpl_id: str) -> int:
    v = VDB(template_collection())
    res = v.collection.get(where={"template_id": tpl_id})  # simple list result
    return len(res.get("ids", [])) if res else 0

def _sample_text_for_template(tpl_id: str, k: int = 1) -> str:
    v = VDB(template_collection())
    res = v.collection.get(where={"template_id": tpl_id}, include=["documents"], limit=k)
    docs = res.get("documents", [])
    if docs and len(docs) > 0:
        # 'documents' is a list[str]
        sample = (docs[0] or "").replace("\n", " ")
        return textwrap.shorten(sample, width=120)
    return ""

def main():
    init_db()
    with SessionLocal() as s:
        rows = s.scalars(select(Template)).all()
        if not rows:
            print("No templates found. Did you run seed_templates?")
            return
        print(f"Found {len(rows)} templates:\n")
        for t in rows:
            nvec = _count_vectors_for_template(t.id)
            sample = _sample_text_for_template(t.id)
            print(f"- {t.name}  [{t.id}]  vectors={nvec}")
            if sample:
                print(f"  sample: {sample}")
            print()

if __name__ == "__main__":
    main()
