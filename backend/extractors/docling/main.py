# ai-engine/extractors/docling/main.py
from __future__ import annotations
from typing import List

def extract_text_by_page(path: str) -> List[str]:
    """
    Returns a list[str] where each item is the text of one PDF page.
    Uses PyPDF2 by default so it works immediately. You can later
    swap this to your Docling pipeline and keep the same signature.
    """
    # 1) Try PyPDF2 (ships in your requirements)
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        pages: List[str] = []
        for i, p in enumerate(reader.pages):
            try:
                txt = p.extract_text() or ""
            except Exception:
                txt = ""
            pages.append(txt)
        # Ensure we return at least one item to avoid downstream crashes
        return pages if pages else [""]
    except Exception:
        pass

    # 2) Optional fallback: pdfminer.six (if you have it installed)
    try:
        from pdfminer.high_level import extract_text
        whole = extract_text(path) or ""
        # pdfminer separates pages with form feeds; split if present
        parts = [s for s in whole.split("\x0c") if s is not None]
        return parts if parts else [whole]
    except Exception:
        # Last resort: return a single empty page
        return [""]
