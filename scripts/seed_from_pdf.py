# ai-engine/scripts/seed_from_pdf.py
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from core.db import init_db, SessionLocal
from core.models import Template
from core.templates import (
    create_or_update_template,
    index_template_text,
    index_template_fields,
    upsert_template_fields_json,
)
from extractors.docling import main as docling_main  

def _extract_pages_robust(pdf_path: str) -> List[str]:
    """Try multiple ways to get page text."""
    # 1) docling helper if present
    try:
        if hasattr(docling_main, "extract_text_by_page"):
            pages = docling_main.extract_text_by_page(pdf_path) or []
            if any((p or "").strip() for p in pages):
                return pages
    except Exception as e:
        print(f"[warn] docling extract failed: {e}")

    # 2) PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        pages = []
        for p in reader.pages:
            try:
                txt = p.extract_text() or ""
            except Exception:
                txt = ""
            pages.append(txt)
        if any((p or "").strip() for p in pages):
            return pages
    except Exception as e:
        print(f"[warn] PyPDF2 extract failed: {e}")

    # 3) pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages = []
            for pg in pdf.pages:
                try:
                    txt = pg.extract_text() or ""
                except Exception:
                    txt = ""
                pages.append(txt)
        if any((p or "").strip() for p in pages):
            return pages
    except Exception as e:
        print(f"[warn] pdfplumber extract failed: {e}")

    # 4) give up
    return []

# ---------------- registry ----------------
def _load_registry(p: Optional[str]) -> Dict:
    if not p:
        return {}
    path = Path(p)
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[warn] invalid registry {path}: {e}")
        return {}

def _get_or_create_template_id(name: str, header_json: Dict, notes: str = "") -> str:
    with SessionLocal() as s:
        ex = s.query(Template).filter(Template.name == name).first()
        if ex:
            return ex.id
    return create_or_update_template(name=name, header_json=header_json or {"columns": []}, notes=notes)

# ---------------- anchor split ----------------
def _find_anchor_starts(pages: List[str], anchors: List[str]) -> List[int]:
    anchors_lc = [a.lower() for a in anchors]
    out = []
    for i, t in enumerate(pages):
        low = (t or "").lower()
        if any(a in low for a in anchors_lc):
            out.append(i)
    return sorted(list(dict.fromkeys(out)))

def _sections_by_anchors(pages: List[str], registry: Dict) -> List[Tuple[str, int, int, List[str]]]:
    """
    Return list of (template_name, start_idx, end_idx, page_texts[start:end])
    """
    marks: List[Tuple[int, str]] = []
    for name, spec in registry.items():
        anchors = spec.get("anchors") or []
        if not anchors:
            continue
        for s in _find_anchor_starts(pages, anchors):
            marks.append((s, name))
    if not marks:
        return []
    marks.sort(key=lambda x: x[0])
    out: List[Tuple[str, int, int, List[str]]] = []
    for i, (start, name) in enumerate(marks):
        end = marks[i+1][0] if i + 1 < len(marks) else len(pages)
        out.append((name, start, end, pages[start:end]))
    return out

# ---------------- tables via pdfplumber (optional) ----------------
def _extract_fields_pdfplumber(pdf_path: str, start: int, end: int) -> List[Dict]:
    """
    Extract 'Field Name / Data Type / Length/Format / Special' rows from page range [start, end)
    using pdfplumber tables. Returns list of {"name","data_type","length_format","special","required","allowed_values"}.
    """
    try:
        import pdfplumber
    except Exception:
        print("[warn] pdfplumber not installed; skipping table extraction")
        return []

    headers_syn = [
        ("field name", "data type", "length", "special"),
        ("field name", "data type", "format", "special"),
        ("field name", "data type", "length / format", "special"),
        ("field name", "data type", "length/format", "notes"),
    ]

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip().lower())

    def _looks_like_header(cells: List[str]) -> bool:
        cols = tuple(_norm(c) for c in cells[:4])
        cols3 = (cols[0], cols[1], cols[2] if len(cols) > 2 else "", cols[3] if len(cols) > 3 else "")
        for h in headers_syn:
            if all(h[i] in cols3[i] for i in range(min(4, len(cols3)))):
                return True
        # loose match
        joined = " ".join(cols3)
        return "field name" in joined and "data type" in joined

    fields: List[Dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        for pi in range(start, min(end, len(pdf.pages))):
            page = pdf.pages[pi]
            # try multiple table settings to be robust
            for ts in (
                {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
                {"vertical_strategy": "text", "horizontal_strategy": "text"},
                {"vertical_strategy": "lines", "horizontal_strategy": "text"},
            ):
                try:
                    tables = page.extract_tables(table_settings=ts) or []
                except Exception:
                    continue

                for tbl in tables:
                    if not tbl or len(tbl) < 2:
                        continue
                    # find header row
                    header_idx = -1
                    for r, row in enumerate(tbl[:5]):  # search top few rows
                        if _looks_like_header([c or "" for c in row]):
                            header_idx = r
                            break
                    if header_idx < 0:
                        continue

                    # normalize headers to positions
                    hdr = [(_norm(c or "")) for c in tbl[header_idx]]
                    def pos(needle: str, default: Optional[int]) -> Optional[int]:
                        for i, h in enumerate(hdr):
                            if needle in h:
                                return i
                        return default

                    i_name   = pos("field", 0)
                    i_dtype  = pos("data type", 1)
                    i_len    = pos("length", 2)
                    if i_len is None:
                        i_len = pos("format", 2)
                    i_notes  = pos("special", 3)
                    if i_notes is None:
                        i_notes = pos("notes", 3)

                    # iterate data rows
                    for row in tbl[header_idx+1:]:
                        if not row or all((c is None or str(c).strip()=="") for c in row):
                            continue
                        def cell(i): 
                            return (row[i] if i is not None and i < len(row) else "") or ""
                        name  = str(cell(i_name)).strip()
                        if not name:
                            continue
                        dtype = str(cell(i_dtype)).strip()
                        leng  = str(cell(i_len)).strip()
                        note  = str(cell(i_notes)).strip()

                        f = {
                            "name": name,
                            "data_type": dtype,
                            "length_format": leng,
                            "special": note,
                            "required": True if re.search(r"\brequired|mandatory\b", f"{name} {dtype} {note}", re.I) else None,
                            "allowed_values": []
                        }
                        m = re.search(r"(allowed|valid|values?)\s*:\s*(.+)", note, re.I)
                        if m:
                            vals = re.split(r",|;|\|", m.group(2))
                            f["allowed_values"] = [v.strip() for v in vals if v.strip()]
                        fields.append(f)
    # de-dup by field name; keep the richest note
    store: Dict[str, Dict] = {}
    for f in fields:
        k = f["name"].strip()
        if k not in store or len((f.get("special") or "")) > len((store[k].get("special") or "")):
            store[k] = f
    return list(store.values())

# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-dir", required=True)
    ap.add_argument("--registry", default="")
    ap.add_argument("--tenant-id", default="__system__")
    ap.add_argument("--mode", choices=["raw", "tables"], default="raw",
                    help="raw = chunk+embed section text only; tables = also parse field tables with pdfplumber")
    args = ap.parse_args()

    init_db()
    registry = _load_registry(args.registry)
    seed_dir = Path(args.seed_dir)
    pdfs = list(seed_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"[info] no PDFs under {seed_dir}")
        return

    for pdf in pdfs:
        pages = _extract_pages_robust(str(pdf))
        if not pages:
            print(f"[seed:skip] {pdf.name} -> no extractable text on any page")
            continue

        sections = _sections_by_anchors(pages, registry)
        if not sections:
            name = pdf.stem
            header_json = registry.get(name, {})
            tpl_id = _get_or_create_template_id(name, header_json, notes=f"seeded from {pdf.name}")
            whole = [ (t or "").strip() for t in pages if (t or "").strip() ]
            if not whole:
                print(f"[seed:skip] template={name} from={pdf.name} (whole doc had no text)")
                continue
            index_template_text(template_id=tpl_id, tenant_id=args.tenant_id, text_chunks=whole)

        for name, start, end, subset in sections:
            header_json = registry.get(name, {})
            tpl_id = _get_or_create_template_id(name, header_json, notes=f"seeded from {pdf.name}")
            subset = [ (t or "").strip() for t in subset if (t or "").strip() ]
            if not subset:
                print(f"[seed:skip] template={name} from={pdf.name} (section had no text)")
                continue

            index_template_text(template_id=tpl_id, tenant_id=args.tenant_id, text_chunks=subset)

            # 2) optionally parse & index fields from the physical PDF pages
            if args.mode == "tables":
                from core.templates import index_template_fields, upsert_template_fields_json
                fields = _extract_fields_pdfplumber(str(pdf), start, end)
                if fields:
                    index_template_fields(tpl_id, args.tenant_id, fields)
                    upsert_template_fields_json(tpl_id, fields)
                print(f"[seed:{args.mode}] template={name} id={tpl_id} pages={end-start} fields={len(fields)} chunks={len(subset)} from={pdf.name}")
            else:
                print(f"[seed:{args.mode}] template={name} id={tpl_id} pages={end-start} fields=0 chunks={len(subset)} from={pdf.name}")

if __name__ == "__main__":
    main()
