# ai-engine/extractors/pdf/adapter.py
from pathlib import Path
from typing import Dict, Any, List
from ..docling import main as docling_main

def _fallback_pages_with_pypdf2(path: str) -> List[str]:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        return [(p.extract_text() or "") for p in reader.pages]
    except Exception:
        return [""]

def extract_pdf(path: str) -> Dict[str, Any]:
    path = str(Path(path).resolve())
    # Use docling_main.extract_text_by_page if present, else fallback
    if hasattr(docling_main, "extract_text_by_page"):
        pages = docling_main.extract_text_by_page(path)
    else:
        pages = _fallback_pages_with_pypdf2(path)

    text_blocks = [{"page": i + 1, "text": t or ""} for i, t in enumerate(pages)]

    # naive header candidates from lines that look like fields
    header_candidates: List[str] = []
    for tb in text_blocks:
        for line in (tb["text"] or "").splitlines():
            low = line.lower()
            if any(k in low for k in ["invoice", "date", "total", "tax", "vendor", "amount", "po", "number"]):
                header_candidates.append(line.strip())
    header_candidates = list(dict.fromkeys(header_candidates))[:64]

    return {
        "text_blocks": text_blocks,
        "table_blocks": [],
        "header_candidates": header_candidates
    }
