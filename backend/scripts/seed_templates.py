# ai-engine/scripts/seed_templates.py
import argparse, json, re
from pathlib import Path
from typing import Dict, List, Tuple

from core.db import init_db, SessionLocal
from core.models import Template
from core.templates import (
    create_or_update_template,
    index_template_text,
    index_template_fields,
    upsert_template_fields_json,
)
from extractors.pdf.adapter import extract_pdf
from extractors.docling import main as docling_main  # must expose extract_text_by_page()

# ---------- registry ----------
def _load_registry(p: str) -> Dict:
    path = Path(p)
    if not p or not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[warn] invalid registry at {path}: {e}; proceeding without it")
        return {}

# ---------- template row helpers ----------
def _get_or_create_template_id(name: str, header_json: Dict, notes: str = "") -> str:
    with SessionLocal() as s:
        existing = s.query(Template).filter(Template.name == name).first()
        if existing:
            return existing.id
    return create_or_update_template(name=name, header_json=header_json or {"columns": []}, notes=notes)

# ---------- anchor split ----------
def _find_anchor_starts(pages: List[str], anchors: List[str]) -> List[int]:
    anchors_lc = [a.lower() for a in anchors]
    starts = []
    for i, t in enumerate(pages):
        low = (t or "").lower()
        if any(a in low for a in anchors_lc):
            starts.append(i)
    return sorted(list(dict.fromkeys(starts)))

def _split_by_registry_anchors(pages: List[str], registry: Dict) -> List[Tuple[str, List[str]]]:
    """
    Returns [(template_name, [page_texts...]), ...] using registry anchors.
    """
    candidates: List[Tuple[int, str]] = []
    for tmpl_name, spec in registry.items():
        anchors = spec.get("anchors") or []
        if not anchors:
            continue
        for sp in _find_anchor_starts(pages, anchors):
            candidates.append((sp, tmpl_name))
    if not candidates:
        return []
    candidates.sort(key=lambda x: x[0])
    out: List[Tuple[str, List[str]]] = []
    for idx, (start, name) in enumerate(candidates):
        end = candidates[idx + 1][0] if idx + 1 < len(candidates) else len(pages)
        subset = pages[start:end]
        if subset:
            out.append((name, subset))
    return out

# ---------- field table parsing ----------
HEADER_PAT = re.compile(r"(field\s*name).*(data\s*type).*(length.*format|format|length).*(special|notes|instruction)", re.I)

def _normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def _split_cols(line: str) -> List[str]:
    # split on 2+ spaces or tabs
    parts = re.split(r"\t+| {2,}", line.strip())
    return [p.strip() for p in parts if p.strip()]

def _parse_field_rows(lines: List[str]) -> List[Dict]:
    """
    Parse rows after we detect a header line that looks like:
    Field Name | Data Type | Length / Format | Special ...
    We keep collecting until we hit a blank or another section header.
    """
    fields: List[Dict] = []
    current = None
    for raw in lines:
        line = raw.strip()
        if not line:
            # blank line ends current row continuation
            current = None
            continue
        cols = _split_cols(line)

        # Likely a new row if we have >=2 columns and first col isn't continuing punctuation
        if len(cols) >= 2 and (current is None or len(cols) >= 3):
            # new row
            name = cols[0]
            data_type = cols[1] if len(cols) > 1 else ""
            length_fmt = cols[2] if len(cols) > 2 else ""
            special = " ".join(cols[3:]) if len(cols) > 3 else ""
            current = {
                "name": name,
                "data_type": data_type,
                "length_format": length_fmt,
                "special": special,
                "required": None,
                "allowed_values": []
            }
            # detect obvious required flags
            if re.search(r"\brequired\b|\bmandatory\b", (special + " " + name + " " + data_type), re.I):
                current["required"] = True
            elif re.search(r"\boptional\b", (special + " " + name + " " + data_type), re.I):
                current["required"] = False
            # detect enum-ish lists
            m = re.search(r"(allowed|valid|values?)\s*:\s*(.+)", special, re.I)
            if m:
                vals = re.split(r",|;|\|", m.group(2))
                current["allowed_values"] = [v.strip() for v in vals if v.strip()]
            fields.append(current)
        else:
            # continuation line → append to special/notes of current row
            if current is not None:
                current["special"] = (current.get("special","") + " " + line).strip()
    return fields

def _extract_fields_from_pages(pages: List[str]) -> List[Dict]:
    """
    Looks for a header line that matches HEADER_PAT, then parses subsequent lines
    into field rows until a stopping condition (blank/anchor-like caps).
    """
    fields: List[Dict] = []
    for ptxt in pages:
        lines = [l for l in ptxt.splitlines()]
        i = 0
        while i < len(lines):
            if HEADER_PAT.search(lines[i]):
                # collect subsequent lines into a block
                block: List[str] = []
                i += 1
                while i < len(lines):
                    # stop when we hit another big header-ish line or an anchor-looking title
                    if re.match(r"^[A-Z][A-Za-z0-9\s/\-]{0,80}$", lines[i]) and lines[i].isupper():
                        break
                    block.append(lines[i])
                    i += 1
                fields.extend(_parse_field_rows(block))
            else:
                i += 1
    # de-dup by field name (keep the richest row)
    by_name: Dict[str, Dict] = {}
    for f in fields:
        k = f.get("name","").strip()
        if not k:
            continue
        if k not in by_name or len((f.get("special") or "")) > len((by_name[k].get("special") or "")):
            by_name[k] = f
    return list(by_name.values())

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-dir", required=True)
    ap.add_argument("--registry", default="")
    ap.add_argument("--tenant-id", default="__system__")
    args = ap.parse_args()

    init_db()
    registry = _load_registry(args.registry)
    seed_dir = Path(args.seed_dir)
    pdfs = list(seed_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"[info] no PDFs under {seed_dir}")
        return

    for pdf in pdfs:
        # per-page text
        if hasattr(docling_main, "extract_text_by_page"):
            pages = docling_main.extract_text_by_page(str(pdf))
        else:
            inter = extract_pdf(str(pdf))
            pages = [tb["text"] for tb in inter.get("text_blocks", [])]

        sections = _split_by_registry_anchors(pages, registry)
        if not sections:
            # single-template fallback
            name = pdf.stem
            header_json = registry.get(name, {})
            tpl_id = _get_or_create_template_id(name, header_json, notes=f"seeded from {pdf.name}")
            index_template_text(template_id=tpl_id, tenant_id=args.tenant_id, text_chunks=pages)
            # field parsing on entire doc (best-effort)
            fields = _extract_fields_from_pages(pages)
            if fields:
                index_template_fields(tpl_id, args.tenant_id, fields)
                upsert_template_fields_json(tpl_id, fields)
            print(f"[seed:single] template={name} id={tpl_id} sections=1 fields={len(fields)} chunks={len(pages)}")
            continue

        # per-section (per-template) seeding
        for tmpl_name, subset in sections:
            header_json = registry.get(tmpl_name, {})
            tpl_id = _get_or_create_template_id(tmpl_name, header_json, notes=f"seeded from {pdf.name} (anchors)")
            index_template_text(template_id=tpl_id, tenant_id=args.tenant_id, text_chunks=subset)
            fields = _extract_fields_from_pages(subset)
            if fields:
                index_template_fields(tpl_id, args.tenant_id, fields)
                upsert_template_fields_json(tpl_id, fields)
            print(f"[seed] template={tmpl_name} id={tpl_id} sections=1 fields={len(fields)} chunks={len(subset)} from={pdf.name}")

if __name__ == "__main__":
    main()
