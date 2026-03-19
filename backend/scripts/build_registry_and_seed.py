# ai-engine/scripts/build_registry_and_seed.py
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Dict, List, Tuple

from core.db import init_db, SessionLocal
from core.models import Template
from core.templates import (
    index_template_text,
    index_template_fields,
    upsert_template_fields_json,
)
from core.templates import create_or_update_template

# ---------- utils ----------
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def _load_json(path: str) -> Dict:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        raise SystemExit(f"[error] JSON not found or empty: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"[error] invalid JSON at {p}: {e}")

# ---------- text extraction for anchors ----------
def extract_pages_text(pdf_path: str) -> List[str]:
    """Robust per-page text: docling helper -> PyPDF2 -> pdfplumber. Skips empties."""
    try:
        from extractors.docling import main as docling_main
        if hasattr(docling_main, "extract_text_by_page"):
            pages = docling_main.extract_text_by_page(pdf_path) or []
            if any(_norm(p) for p in pages): return pages
    except Exception: pass
    try:
        from PyPDF2 import PdfReader
        pages = []
        r = PdfReader(pdf_path)
        for p in r.pages:
            try: pages.append(p.extract_text() or "")
            except Exception: pages.append("")
        if any(_norm(p) for p in pages): return pages
    except Exception: pass
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for pg in pdf.pages:
                try: pages.append(pg.extract_text() or "")
                except Exception: pages.append("")
        if any(_norm(p) for p in pages): return pages
    except Exception: pass
    return []

def find_anchors(pages: List[str], anchors: List[str]) -> List[int]:
    al = [a.lower() for a in anchors]
    out = []
    for i, t in enumerate(pages):
        low = (t or "").lower()
        if any(a in low for a in al):
            out.append(i)
    return sorted(list(dict.fromkeys(out)))

# ---------- table extraction with pdfplumber ----------
def extract_fields_pdfplumber(pdf_path: str, start: int, end: int) -> List[Dict]:
    """
    Extract 'Field Name / Data Type / Length/Format / Special|Notes' table rows
    from page range [start, end).
    """
    import pdfplumber
    def norm(s: str) -> str: return re.sub(r"\s+", " ", (s or "")).strip().lower()
    header_syn = [
        ("field name", "data type", "length", "special"),
        ("field name", "data type", "format", "special"),
        ("field name", "data type", "length / format", "special"),
        ("field name", "data type", "length/format", "notes"),
        ("field", "type", "length", "notes")
    ]
    def looks_header(cells: List[str]) -> bool:
        cols = tuple(norm(c) for c in cells[:4])
        joined = " ".join(cols)
        if "field" in joined and "data type" in joined: return True
        return any(all(h[i] in cols[i] for i in range(min(4,len(cols)))) for h in header_syn)

    fields: List[Dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for pi in range(start, min(end, len(pdf.pages))):
            page = pdf.pages[pi]
            for ts in (
                {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
                {"vertical_strategy": "text",  "horizontal_strategy": "text"},
                {"vertical_strategy": "lines", "horizontal_strategy": "text"},
            ):
                try:
                    tables = page.extract_tables(table_settings=ts) or []
                except Exception:
                    continue
                for tbl in tables:
                    if not tbl or len(tbl) < 2: continue
                    # find header row
                    header_idx = -1
                    for r, row in enumerate(tbl[:6]):
                        if looks_header([c or "" for c in row]): header_idx = r; break
                    if header_idx < 0: continue
                    hdr = [norm(c or "") for c in tbl[header_idx]]
                    def pos(key: str, default=None):
                        for i,h in enumerate(hdr):
                            if key in h: return i
                        return default
                    i_name  = pos("field", 0)
                    i_dtype = pos("data type", 1)
                    i_len   = pos("length", 2) if pos("length", None) is not None else pos("format", 2)
                    i_notes = pos("special", 3) if pos("special", None) is not None else pos("notes", 3)

                    for row in tbl[header_idx+1:]:
                        if not row: continue
                        name  = _norm(row[i_name]  if i_name  is not None and i_name  < len(row) else "")
                        if not name: continue
                        dtype = _norm(row[i_dtype] if i_dtype is not None and i_dtype < len(row) else "")
                        leng  = _norm(row[i_len]   if i_len   is not None and i_len   < len(row) else "")
                        note  = _norm(row[i_notes] if i_notes is not None and i_notes < len(row) else "")
                        f = {
                            "name": name,
                            "data_type": dtype,
                            "length_format": leng,
                            "required": True if re.search(r"\brequired|mandatory\b", f"{name} {dtype} {note}") else None,
                            "allowed_values": [],
                            "special": note
                        }
                        m = re.search(r"(allowed|valid|values?)\s*:\s*(.+)", note)
                        if m:
                            vals = re.split(r",|;|\|", m.group(2))
                            f["allowed_values"] = [v.strip() for v in vals if v.strip()]
                        # heuristic: if dtype contains enumerations like "enum (A, B)"
                        m2 = re.search(r"\(([^)]+)\)", dtype)
                        if m2 and not f["allowed_values"]:
                            vals = re.split(r",|;", m2.group(1))
                            f["allowed_values"] = [v.strip() for v in vals if v.strip()]
                        fields.append(f)
    # de-dup by field name; keep the richest notes
    by_name: Dict[str, Dict] = {}
    for f in fields:
        k = f["name"]
        if k not in by_name or len(f.get("special","")) > len(by_name[k].get("special","")):
            by_name[k] = f
    return list(by_name.values())

# ---------- build registry from PDFs (anchors) and seed ----------
def build_registry_from_pdfs(seed_dir: str, anchors_json: str) -> Dict:
    anchors = _load_json(anchors_json)  # expected: {"Template Name": {"anchors":[...], "description": "..."}}
    seed = {}
    seed_path = Path(seed_dir)
    pdfs = list(seed_path.rglob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"[info] no PDFs under {seed_dir}")

    for pdf in pdfs:
        pages = extract_pages_text(str(pdf))
        if not any(_norm(p) for p in pages):
            print(f"[skip] {pdf.name} has no extractable text")
            continue

        # collect (page_start, template_name) from anchors
        marks: List[Tuple[int,str]] = []
        for tmpl, spec in anchors.items():
            starts = find_anchors(pages, spec.get("anchors", []))
            for s in starts: marks.append((s, tmpl))
        if not marks:
            print(f"[warn] no anchors matched in {pdf.name}")
            continue
        marks.sort(key=lambda x: x[0])

        for i,(start, name) in enumerate(marks):
            end = marks[i+1][0] if i+1 < len(marks) else len(pages)
            fields = extract_fields_pdfplumber(str(pdf), start, end)
            entry = {
                "anchors": anchors[name].get("anchors", []),
                "description": anchors[name].get("description", ""),
                "fields": fields
            }
            seed[name] = entry
            print(f"[build] {name}: pages={end-start} fields={len(fields)} from={pdf.name}")
    return seed

def seed_from_registry(registry: Dict, tenant_id: str):
    for name, entry in registry.items():
        header_json = {
            "columns": entry.get("columns") or [f["name"] for f in entry.get("fields", [])],
            "fields": entry.get("fields", []),
            "source": "pdf"
        }
        tpl_id = create_or_update_template(name=name, header_json=header_json, notes="seeded from PDF")
        # template card
        card = "Template: " + name + (" | Fields: " + ", ".join([f["name"] for f in header_json["fields"]]) if header_json["fields"] else "")
        index_template_text(template_id=tpl_id, tenant_id=tenant_id, text_chunks=[card])
        # field vectors
        if header_json["fields"]:
            index_template_fields(template_id=tpl_id, tenant_id=tenant_id, fields=header_json["fields"])
            upsert_template_fields_json(template_id=tpl_id, fields=header_json["fields"])
        print(f"[seed] template={name} id={tpl_id} fields={len(header_json['fields'])}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-dir", required=True, help="Folder with PDFs (e.g. .\\templates\\seed)")
    ap.add_argument("--anchors", required=True, help="JSON with template anchors and optional descriptions")
    ap.add_argument("--out", default=".\\templates\\registry_built.json")
    ap.add_argument("--tenant-id", default="__system__")
    args = ap.parse_args()

    init_db()
    built = build_registry_from_pdfs(args.seed_dir, args.anchors)
    # write the built registry
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(built, indent=2), encoding="utf-8")
    print(f"[write] {outp}  (templates={len(built)})")

    # seed from the built registry
    seed_from_registry(built, args.tenant_id)

if __name__ == "__main__":
    main()
