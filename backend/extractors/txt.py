# ai-engine/extractors/txt.py
from typing import Dict, Any
from pathlib import Path

def extract_txt(path: str) -> Dict[str, Any]:
    """Extract text from plain text files."""
    try:
        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()
    except UnicodeDecodeError:
        # Try different encodings
        for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
            try:
                with open(path, 'r', encoding=encoding) as file:
                    content = file.read()
                break
            except UnicodeDecodeError:
                continue
        else:
            # If all encodings fail, read as binary and decode with errors
            with open(path, 'rb') as file:
                content = file.read().decode('utf-8', errors='replace')
    
    # Split content into lines for processing
    lines = content.splitlines()
    
    # Create text blocks (treat as single page)
    text_blocks = [{"page": 1, "text": content}] if content.strip() else []
    
    # Try to identify potential headers/fields
    header_candidates = []
    for line in lines[:50]:  # Check first 50 lines
        line = line.strip()
        if line and len(line) < 100:
            # Look for lines that might be headers or field names
            lower_line = line.lower()
            if any(keyword in lower_line for keyword in [
                "name", "date", "total", "amount", "number", "id", "title", 
                "address", "phone", "email", "invoice", "receipt", "order"
            ]):
                header_candidates.append(line)
            # Also look for lines with colons (key-value pairs)
            elif ":" in line and len(line.split(":")) == 2:
                key = line.split(":")[0].strip()
                if key and len(key) < 50:
                    header_candidates.append(key)
    
    # Remove duplicates and limit
    header_candidates = list(dict.fromkeys(header_candidates))[:64]
    
    return {
        "text_blocks": text_blocks,
        "table_blocks": [],  # Plain text doesn't have structured tables
        "header_candidates": header_candidates
    }