# ai-engine/pipelines/extract_flow.py
from typing import Dict, Any, List
from pathlib import Path
import json
import re
from ..extractors.csv import extract_csv
from ..extractors.xlsx import extract_xlsx
from ..extractors.docx import extract_docx
from ..extractors.txt import extract_txt
from ..extractors.easyocr.easyocr_extractor import EasyOCRExtractor
from ..core.templates import classify_template
from ..pipelines.ingest import ingest_intermediate
from ..core.databricks_llm import DatabricksLLM

def _route_extract(file_type: str, path: str) -> Dict[str, Any]:
    """Route file extraction based on file type."""
    ft = (file_type or Path(path).suffix.lower().lstrip(".")).lower()
    
    # Structured documents - use specific extractors
    if ft in ("csv",):
        return extract_csv(path)
    if ft in ("xlsx", "xls"):
        return extract_xlsx(path)
    if ft in ("docx", "doc"):
        return extract_docx(path)
    if ft in ("txt",):
        return extract_txt(path)
    
    # PDFs and images - use EasyOCR
    if ft in ("pdf",):
        return _extract_pdf_with_easyocr(path)
    if ft in ("png", "jpg", "jpeg", "tiff", "tif", "bmp", "gif"):
        return _extract_image_with_easyocr(path)
    
    raise ValueError(f"Unsupported file type: {ft}")

def _extract_image_with_easyocr(path: str) -> Dict[str, Any]:
    """Extract text from images using EasyOCR."""
    try:
        extractor = EasyOCRExtractor()
        from PIL import Image
        image = Image.open(path)
        text = extractor.extract_text_from_image(image)
        
        # Create text blocks (treat as single page)
        text_blocks = [{"page": 1, "text": text}] if text and text.strip() else []
        
        # Extract potential header candidates from the text
        header_candidates = []
        if text:
            lines = text.splitlines()
            for line in lines[:20]:  # Check first 20 lines
                line = line.strip()
                if line and len(line) < 100:
                    lower_line = line.lower()
                    if any(keyword in lower_line for keyword in [
                        "invoice", "receipt", "date", "total", "amount", "vendor", 
                        "po", "number", "id", "name", "address", "phone"
                    ]):
                        header_candidates.append(line)
        
        header_candidates = list(dict.fromkeys(header_candidates))[:64]
        
        return {
            "text_blocks": text_blocks,
            "table_blocks": [],  # Images don't have structured table data
            "header_candidates": header_candidates,
            "metadata": {
                "processor": "PaddleOCR-VL",
                "file_type": "image",
                "extraction_method": "vision-language-model"
            }
        }
        
    except Exception as e:
        print(f"[warn] EasyOCR image extraction failed: {e}")
        # Fallback to basic file info
        return {
            "text_blocks": [{"page": 1, "text": f"Error processing image {Path(path).name}: {str(e)}"}],
            "table_blocks": [],
            "header_candidates": [],
            "metadata": {
                "processor": "EasyOCR",
                "file_type": "image",
                "extraction_method": "error-fallback"
            }
        }

def _extract_pdf_with_easyocr(path: str) -> Dict[str, Any]:
    """Extract text from PDF using EasyOCR for fast, accurate OCR."""
    try:
        extractor = EasyOCRExtractor()
        result = extractor.extract_text_from_pdf(path)
        
        # Extract header candidates from all pages
        header_candidates = []
        for tb in result.get("text_blocks", []):
            for line in (tb.get("text", "") or "").splitlines():
                line = line.strip()
                if line and len(line) < 100:
                    lower_line = line.lower()
                    if any(keyword in lower_line for keyword in [
                        "invoice", "receipt", "date", "total", "amount", "vendor",
                        "po", "number", "id", "name", "address", "phone", "tax"
                    ]):
                        header_candidates.append(line)
        
        header_candidates = list(dict.fromkeys(header_candidates))[:64]
        
        # Ensure we have the expected structure
        result.setdefault("header_candidates", header_candidates)
        result.setdefault("metadata", {}).update({
            "processor": "EasyOCR",
            "file_type": "pdf",
            "extraction_method": "ocr-cpu-optimized"
        })
        
        return result
        
    except Exception as e:
        print(f"[warn] EasyOCR PDF extraction failed: {e}, falling back to docling")
        # Fallback to docling if EasyOCR fails
        from ..extractors.pdf.adapter import extract_pdf
        return extract_pdf(path)

def _chunk_tabular_data(headers: List[str], rows: List[List[str]], chunk_size: int = 50) -> List[tuple]:
    """Split tabular data into chunks with dynamic sizing based on dataset"""
    num_rows = len(rows)
    
    # Dynamic chunk size based on dataset size (optimized for parallel processing)
    if num_rows <= 30:
        optimal_size = 1  # Maximum parallelism for small datasets
    elif num_rows <= 60:
        optimal_size = 2
    elif num_rows <= 120:
        optimal_size = 3
    elif num_rows <= 240:
        optimal_size = 5
    elif num_rows <= 500:
        optimal_size = 8
    else:
        optimal_size = 10
    
    chunk_size = min(chunk_size, optimal_size) if chunk_size else optimal_size
    
    chunks = []
    for i in range(0, len(rows), chunk_size):
        chunk_rows = rows[i:i+chunk_size]
        chunks.append((headers, chunk_rows))
    
    return chunks

def _to_snake_case(name: str) -> str:
    """Convert field name to snake_case"""
    name = re.sub(r'[\s/\-]+', '_', name)
    name = re.sub(r'[^\w_]', '', name)
    return name.lower()

def _clean_llm_json(response: str) -> str:
    """Extract JSON array from LLM response"""
    cleaned = response.strip()
    cleaned = cleaned.replace('```json', '').replace('```', '').strip()
    
    start_idx = cleaned.find('[')
    end_idx = cleaned.rfind(']')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx:end_idx+1]
    
    return cleaned

def _extract_chunk_with_llm(llm: DatabricksLLM, headers: List[str], chunk_rows: List[List[str]], 
                            chunk_idx: int, total_chunks: int, template_fields: List[str]) -> List[Dict]:
    """Process a single chunk with LLM"""
    # Convert to pipe-delimited text
    header_line = ' | '.join(headers)
    data_lines = [' | '.join(str(cell) for cell in row) for row in chunk_rows]
    chunk_text = header_line + '\n' + '\n'.join(data_lines)
    
    # Snake case template fields
    snake_fields = [_to_snake_case(field) for field in template_fields] if template_fields else []
    if not snake_fields:
        snake_fields = [_to_snake_case(h) for h in headers]
    
    num_fields = len(snake_fields)
    num_lines = len(chunk_rows)
    
    # Calculate dynamic tokens
    estimated_tokens = num_lines * num_fields * 15 + 300
    max_tokens = min(8192, max(3000, int(estimated_tokens * 1.3)))
    
    system_prompt = f"""Extract data to JSON array. Fields: {', '.join(snake_fields)}
Rules: Return ONLY JSON array starting with [. Map columns to snake_case field names. Empty cells = "". No markdown."""
    
    user_message = f"""Data ({num_lines} rows):
{chunk_text}

JSON array with {num_fields} fields:"""
    
    try:
        response = llm.chat(
            user_message=user_message,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=0.0
        )
        
        cleaned = _clean_llm_json(response)
        data = json.loads(cleaned)
        chunk_rows_data = data if isinstance(data, list) else data.get("rows", [data] if isinstance(data, dict) else [])
        
        # Ensure all fields present
        complete_rows = []
        for row in chunk_rows_data[:num_lines]:  # Take only expected rows
            complete_row = {field: row.get(field, "") for field in snake_fields}
            complete_rows.append(complete_row)
        
        print(f"   📦 Chunk {chunk_idx}/{total_chunks}... ✅ {len(complete_rows)} records")
        return complete_rows
        
    except Exception as e:
        print(f"   📦 Chunk {chunk_idx}/{total_chunks}... ⚠️ Parse error: {str(e)[:50]}")
        return []

def extract_and_shape(tenant_id: str, path: str, file_type: str | None = None, use_chunking: bool = True) -> Dict[str, Any]:
    """Extract and structure data with intelligent chunking for large datasets"""
    inter = _route_extract(file_type, path)

    # Ingest to DB + VDB
    doc_id = ingest_intermediate(
        tenant_id=tenant_id,
        name=Path(path).name,
        mime=file_type or "",
        path=str(Path(path).resolve()),
        intermediate=inter
    )

    # Template classification (≥ 0.40)
    tpl = classify_template(inter.get("header_candidates", []))

    # Build final JSON
    if tpl:
        columns = tpl["header_json"].get("columns", [])
        template_name = tpl.get("name", "Unknown")
    else:
        # Fallback: use seen headers or simple best-guess
        if inter.get("table_blocks"):
            columns = inter["table_blocks"][0]["headers"]
        else:
            columns = ["column_1", "column_2", "column_3"]
        template_name = "Unknown"

    # Extract rows with chunking for large datasets
    rows = []
    
    if inter.get("table_blocks"):
        headers = inter["table_blocks"][0]["headers"]
        rows_list = inter["table_blocks"][0]["rows"]
        num_rows = len(rows_list)
        
        # Use chunking for datasets > 30 rows
        if use_chunking and num_rows > 30:
            print(f"\n🔄 Processing {num_rows} rows with intelligent chunking...")
            print(f"   Template: {template_name}, Fields: {len(columns)}")
            
            # Initialize LLM
            llm = DatabricksLLM()
            
            # Split into chunks
            chunks = _chunk_tabular_data(headers, rows_list, chunk_size=50)
            total_chunks = len(chunks)
            
            print(f"   Split into {total_chunks} chunks for parallel processing")
            
            # Process chunks
            all_rows = []
            for idx, (chunk_headers, chunk_rows) in enumerate(chunks, 1):
                chunk_result = _extract_chunk_with_llm(
                    llm, chunk_headers, chunk_rows,
                    idx, total_chunks, columns
                )
                all_rows.extend(chunk_result)
            
            rows = all_rows
            print(f"✅ Chunked extraction complete: {len(rows)} total records")
        else:
            # Direct conversion for small datasets
            rows = [dict(zip(columns, r[:len(columns)])) for r in rows_list]
            if num_rows > 0:
                print(f"✅ Direct conversion: {len(rows)} records (no chunking needed)")
    else:
        rows = []

    result = {
        "template": {k: v for k, v in tpl.items() if k in ("id", "name", "similarity")},
        "columns": columns,
        "rows": rows,
        "provenance": []  # fill later if you want column→chunk mapping
    }
    return result
