#!/usr/bin/env python3
"""
FastAPI application for document extraction with Swagger UI

Endpoints:
- POST /extract/upload - Upload file and get extracted JSON
- GET /extract/jobs/{job_id} - Get extraction result by job ID
- GET /extract/list - List all extraction jobs
- POST /mapping/* - Intelligent field mapping endpoints (6 routes)
- POST /memory/* - PowerMemory engine endpoints (15+ routes)
- POST /chat/* - Chat-based file manipulation
- GET /health - Health check

Swagger UI: http://localhost:8000/docs
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import json
import uuid
import sys
import shutil
import asyncio
import time
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from sklearn.metrics.pairwise import cosine_similarity

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.databricks_llm import DatabricksLLM
from core.databricks_embeddings import DatabricksEmbeddings
from extractors.csv import extract_csv
from extractors.xlsx import extract_xlsx
from extractors.docx import extract_docx
from extractors.txt import extract_txt

try:
    from extractors.easyocr.easyocr_extractor import EasyOCRExtractor
except ImportError:
    EasyOCRExtractor = None

# Initialize FastAPI app
app = FastAPI(
    title="AI-RAG Document Extraction API",
    description="Extract and structure data from documents using EasyOCR/Docling and Databricks LLM",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Document Extraction"},
        {"name": "Mapping Engine"},
        {"name": "PowerMemory"},
        {"name": "Chat Engine"}
    ]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include chat engine routes
from chat_engine.api_routes import router as chat_router
app.include_router(chat_router)

# Include PowerMemory routes
from power_memory.api_routes import router as memory_router
app.include_router(memory_router)

# Include Mapping Engine routes
from mapping_engine.api_routes import router as mapping_router
app.include_router(mapping_router)

# In-memory storage for job results
extraction_jobs: Dict[str, Dict[str, Any]] = {}

# Cached LLM instance (reuse across requests)
_llm_instance = None

# PowerMemory instance (initialized on first use)
power_memory = None

# Thread pool for parallel processing (16 workers for maximum parallelism)
_executor = ThreadPoolExecutor(max_workers=16)

def get_llm_instance():
    """Get or create cached LLM instance"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = DatabricksLLM()
        print("✅ Databricks LLM client initialized (cached)")
    return _llm_instance

def get_power_memory():
    """Get or create PowerMemory instance"""
    global power_memory
    if power_memory is None:
        from power_memory import PowerMemoryEngine
        llm = get_llm_instance()
        power_memory = PowerMemoryEngine(llm=llm)
        print("✅ PowerMemory Engine initialized")
    return power_memory

def clean_llm_json(response: str) -> str:
    """Aggressively extract JSON array from LLM response"""
    cleaned = response.strip()
    
    # Remove markdown code blocks
    cleaned = cleaned.replace('```json', '').replace('```', '').strip()
    
    # Find first [ and last ]
    start_idx = cleaned.find('[')
    end_idx = cleaned.rfind(']')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx:end_idx+1]
    
    return cleaned

# Models
class ExtractionJob(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    filename: str
    uploaded_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None

class ExtractionResult(BaseModel):
    job_id: str
    status: str
    filename: str
    uploaded_at: str
    completed_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# Utility functions
def extract_file_content(file_path: Path) -> str:
    """Extract text from file using appropriate extractor"""
    ext = file_path.suffix.lower()
    print(f"\n🔍 File type detected: {ext}")
    
    if ext == '.csv':
        print(f"📊 Using CSV parser for extraction...")
        result = extract_csv(str(file_path))
        if result.get('table_blocks'):
            table = result['table_blocks'][0]
            headers = table['headers']
            rows = table['rows']
            lines = [' | '.join(headers)]
            for row in rows:
                lines.append(' | '.join(str(cell) for cell in row))
            extracted = '\n'.join(lines)
            print(f"✅ CSV extracted: {len(rows)} rows, {len(headers)} columns")
            return extracted
        return ''
    
    elif ext in ['.xlsx', '.xls']:
        print(f"📊 Using Excel parser for extraction...")
        result = extract_xlsx(str(file_path))
        if result.get('table_blocks'):
            table = result['table_blocks'][0]
            headers = table['headers']
            rows = table['rows']
            lines = [' | '.join(headers)]
            for row in rows:
                lines.append(' | '.join(str(cell) for cell in row))
            extracted = '\n'.join(lines)
            print(f"✅ Excel extracted: {len(rows)} rows, {len(headers)} columns")
            return extracted
        return ''
    
    elif ext == '.txt':
        print(f"📝 Using text parser for extraction...")
        result = extract_txt(str(file_path))
        text_blocks = result.get('text_blocks', [])
        extracted = '\n'.join(block.get('text', '') for block in text_blocks)
        print(f"✅ Text extracted: {len(extracted)} characters")
        return extracted
    
    elif ext == '.docx':
        print(f"📄 Using DOCX parser for extraction...")
        result = extract_docx(str(file_path))
        text_blocks = result.get('text_blocks', [])
        extracted = '\n'.join(block.get('text', '') for block in text_blocks)
        print(f"✅ DOCX extracted: {len(extracted)} characters")
        return extracted
    
    elif ext == '.pdf':
        if EasyOCRExtractor:
            try:
                print(f"📄 PDF detected: Using EasyOCR for extraction...")
                ocr = EasyOCRExtractor(languages=['en'], gpu=False)
                result = ocr.extract_text_from_pdf(str(file_path))
                extracted_text = result.get('full_text', '')
                print(f"✅ EasyOCR extracted {len(extracted_text)} characters from PDF")
                return extracted_text
            except Exception as e:
                print(f"❌ EasyOCR failed: {e}")
                print(f"⚠️  Cannot extract PDF without EasyOCR")
                raise ValueError(f"PDF extraction failed: {e}")
        else:
            raise ValueError("EasyOCR not available for PDF extraction")
    
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def identify_template(text_content: str) -> str:
    """Use Databricks LLM to identify which template matches the data - OPTIMIZED"""
    print(f"\n🔍 IDENTIFYING TEMPLATE...", end=" ", flush=True)
    
    # Load all templates from registry
    registry_path = Path(__file__).parent / "templates" / "registry.json"
    
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry = json.load(f)
    except Exception as e:
        print(f"⚠️ Error")
        return "Employee Profile"
    
    # Build compact template descriptions
    template_info = []
    for name, info in registry.items():
        fields = info.get("columns", [])[:5]  # Only first 5 fields
        anchors = info.get("anchors", [])
        template_info.append(f"{name}: {', '.join(anchors)} | {len(info.get('columns', []))} fields")
    
    llm = get_llm_instance()
    
    # Compact prompts for speed
    system_prompt = "Identify template from data. Return ONLY template name."
    
    user_message = f"""Templates:
{chr(10).join(template_info)}

Data sample:
{text_content[:1000]}

Template name:"""
    
    try:
        response = llm.chat(
            user_message=user_message,
            system_prompt=system_prompt,
            max_tokens=15,  # Further reduced for speed
            temperature=0.0
        )
        
        identified = response.strip().strip('"').strip("'")
        
        # Quick match
        if identified in registry:
            print(f"✅ {identified}")
            return identified
        
        # Fuzzy match
        for template_name in registry.keys():
            if template_name.lower() in identified.lower():
                print(f"✅ {template_name}")
                return template_name
        
        print(f"⚠️ Default")
        return "Employee Profile"
            
    except Exception as e:
        print(f"⚠️ Error")
        return "Employee Profile"


def structure_with_llm_chunked(text_content: str, template_name: str, template_fields: list) -> Dict:
    """Process large datasets in chunks to avoid token limits - DYNAMIC CHUNKING"""
    import time
    start_time = time.time()
    
    lines = text_content.strip().split('\n')
    header = lines[0] if lines else ""
    data_lines = lines[1:] if len(lines) > 1 else []
    
    # Convert template field names to snake_case
    def to_snake_case(name: str) -> str:
        import re
        name = re.sub(r'[\s/\-]+', '_', name)
        name = re.sub(r'[^\w_]', '', name)
        return name.lower()
    
    snake_case_fields = [to_snake_case(field) for field in template_fields] if template_fields else []
    
    # Dynamic chunk size based on field count AND dataset size
    num_fields = len(snake_case_fields)
    num_rows = len(data_lines)
    
    # Calculate optimal chunk size to balance parallelism and API rate limits
    # Target: ~1-2 rows per chunk for small datasets, scaling up for larger ones
    # This creates more chunks as dataset grows while avoiding excessive parallelism
    
    if num_rows <= 30:
        # Small dataset: 1 row per chunk for maximum parallelism
        optimal_chunk_size = 1
    elif num_rows <= 60:
        # Medium dataset: 2 rows per chunk (~30 chunks for 60 rows)
        optimal_chunk_size = 2
    elif num_rows <= 120:
        # Large dataset: 3 rows per chunk (~40 chunks for 120 rows)
        optimal_chunk_size = 3
    elif num_rows <= 240:
        # Very large dataset: 5 rows per chunk (~48 chunks for 240 rows)
        optimal_chunk_size = 5
    elif num_rows <= 500:
        # Extra large dataset: 8 rows per chunk (~62 chunks for 500 rows)
        optimal_chunk_size = 8
    else:
        # Massive dataset: 10 rows per chunk (scales linearly)
        optimal_chunk_size = 10
    
    chunk_size = optimal_chunk_size
    total_chunks = (num_rows + chunk_size - 1) // chunk_size
    
    print(f"   Chunk size: {chunk_size} rows for {num_fields} fields ({num_rows} rows → {total_chunks} chunks)")
    
    all_rows = []
    
    llm = get_llm_instance()
    
    # Minimal optimized system prompt
    system_prompt = f"""Extract data to JSON array. Fields: {', '.join(snake_case_fields)}
Rules: Return ONLY JSON array starting with [. Map columns to snake_case field names. Empty cells = "". No markdown."""
    
    print(f"   Processing {num_rows} rows × {num_fields} fields in {total_chunks} chunks...")
    print(f"   ⚡ Using parallel processing for faster extraction...")
    
    # Prepare all chunks
    chunks_to_process = []
    for i in range(0, len(data_lines), chunk_size):
        chunk_lines = data_lines[i:i+chunk_size]
        chunk_text = header + '\n' + '\n'.join(chunk_lines)
        chunk_num = (i // chunk_size) + 1
        chunks_to_process.append((chunk_num, chunk_text, len(chunk_lines)))
    
    # Try batch processing first
    print(f"   🚀 Attempting batch API request...")
    parallel_start = time.time()
    
    # Prepare batch requests
    batch_requests = [
        {
            "user_message": f"""Data ({num_lines} rows):
{chunk_text}

JSON array with {num_fields} fields:""",
            "system_prompt": system_prompt
        }
        for chunk_num, chunk_text, num_lines in chunks_to_process
    ]
    
    # Calculate dynamic max_tokens based on chunk size (OPTIMIZED FOR 70B)
    # Larger chunks need more tokens for complete JSON output
    estimated_tokens_needed = chunk_size * num_fields * 15 + 300  # +300 for JSON structure (70B needs more)
    dynamic_max_tokens = min(8192, max(3000, int(estimated_tokens_needed * 1.3)))  # Cap at model's max_output_tokens limit
    
    print(f"   Using max_tokens: {dynamic_max_tokens} (estimated: {estimated_tokens_needed})")
    
    # Try batch processing
    batch_responses = llm.chat_batch(batch_requests, max_tokens=dynamic_max_tokens, temperature=0.0)
    
    if batch_responses is not None:
        # Batch API worked!
        batch_elapsed = time.time() - parallel_start
        print(f"   ✅ Batch API completed in {batch_elapsed:.1f}s")
        
        # Process batch responses
        for idx, (chunk_info, response) in enumerate(zip(chunks_to_process, batch_responses)):
            chunk_num, chunk_text, num_lines = chunk_info
            
            try:
                cleaned = clean_llm_json(response)
                data = json.loads(cleaned)
                chunk_rows = data if isinstance(data, list) else data.get("rows", [data] if isinstance(data, dict) else [])
                
                # Validate: only take expected number of rows for this chunk
                expected_rows = num_lines
                if len(chunk_rows) > expected_rows:
                    print(f"   ⚠️ Chunk {chunk_num}: LLM returned {len(chunk_rows)} rows, expected {expected_rows}. Taking first {expected_rows}.")
                    chunk_rows = chunk_rows[:expected_rows]
                
                complete_rows = []
                for row in chunk_rows:
                    complete_row = {field: row.get(field, "") for field in snake_case_fields}
                    complete_rows.append(complete_row)
                
                all_rows.extend(complete_rows)
                print(f"   📦 Chunk {chunk_num}/{total_chunks}... ✅ {len(chunk_rows)} records")
                
            except Exception as e:
                print(f"   📦 Chunk {chunk_num}/{total_chunks}... ⚠️ Parse error: {str(e)[:50]}")
    else:
        # Batch not supported - use parallel processing with ThreadPoolExecutor
        print(f"   ⚠️ Batch API not supported, using parallel processing...")
        
        def process_chunk(chunk_info):
            chunk_num, chunk_text, num_lines = chunk_info
            chunk_start = time.time()
            
            user_message = f"""Data ({num_lines} rows):
{chunk_text}

JSON array with {num_fields} fields:"""
            
            try:
                response = llm.chat(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    max_tokens=dynamic_max_tokens,
                    temperature=0.0
                )
                
                chunk_elapsed = time.time() - chunk_start
                cleaned = clean_llm_json(response)
                data = json.loads(cleaned)
                chunk_rows = data if isinstance(data, list) else data.get("rows", [data] if isinstance(data, dict) else [])
                
                # Validate: only take expected number of rows for this chunk
                if len(chunk_rows) > num_lines:
                    print(f"   ⚠️ Chunk {chunk_num}: LLM returned {len(chunk_rows)} rows, expected {num_lines}. Taking first {num_lines}.")
                    chunk_rows = chunk_rows[:num_lines]
                
                complete_rows = []
                for row in chunk_rows:
                    complete_row = {field: row.get(field, "") for field in snake_case_fields}
                    complete_rows.append(complete_row)
                
                return (chunk_num, complete_rows, chunk_elapsed, None)
                
            except json.JSONDecodeError as e:
                chunk_elapsed = time.time() - chunk_start
                return (chunk_num, [], chunk_elapsed, f"Parse error: {str(e)[:100]}")
            except Exception as e:
                chunk_elapsed = time.time() - chunk_start
                return (chunk_num, [], chunk_elapsed, f"Error: {str(e)[:100]}")
        
        # Execute all chunks in parallel with ThreadPoolExecutor
        # Don't use 'with' statement - keep executor alive for multiple requests
        results = list(_executor.map(process_chunk, chunks_to_process))
        
        # Sort results by chunk number and collect rows
        results.sort(key=lambda x: x[0])
        for chunk_num, chunk_rows, chunk_elapsed, error in results:
            if error:
                print(f"   📦 Chunk {chunk_num}/{total_chunks}... ⚠️ {error} ({chunk_elapsed:.1f}s)")
            else:
                print(f"   📦 Chunk {chunk_num}/{total_chunks}... ✅ {len(chunk_rows)} records ({chunk_elapsed:.1f}s)")
                all_rows.extend(chunk_rows)
            all_rows.extend(chunk_rows)
    
    elapsed = time.time() - start_time
    print(f"✅ Total: {len(all_rows)} records with {num_fields} fields in {elapsed:.1f}s")
    return {"rows": all_rows}


def structure_pdf_with_llm(text_content: str, template_name: str, output_file: str = None) -> Dict:
    """
    PDF-specific structuring: Extract raw data from unstructured text.
    For large PDFs, chunk the text to avoid token limits and JSON errors.
    Supports streaming output to JSON file.
    """
    import time
    start_time = time.time()
    
    # Load template to get fields
    template_path = Path("templates/registry.json")
    with open(template_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    
    template_info = registry.get(template_name, {})
    template_fields = template_info.get("columns", [])
    
    if not template_fields:
        return {"rows": [], "metadata": {"template": template_name, "error": "Template not found"}}
    
    # Convert template field names to snake_case
    def to_snake_case(name: str) -> str:
        import re
        name = re.sub(r'[\s/\-]+', '_', name)
        name = re.sub(r'[^\w_]', '', name)
        return name.lower()
    
    snake_case_fields = [to_snake_case(field) for field in template_fields]
    
    print(f"🤖 Sending to Databricks LLM for structuring...")
    print(f"   Text length: {len(text_content)} characters")
    print(f"   Template: {template_name}")
    print(f"   Template has {len(template_fields)} fields")
    
    # Check if we need atomic extraction (large PDFs > 10,000 chars)
    if len(text_content) > 10000:
        print(f"   📊 Large PDF detected, using ATOMIC extraction with DUAL-LLM load balancing...")
        
        # Use atomic extraction with dual-LLM load balancer
        import os
        from core.atomic_extractor import extract_atomic
        
        main_llm = os.getenv("DATABRICKS_LLM_ENDPOINT")
        small_llm_model = os.getenv("DATABRICKS_SMALL_LLM_ENDPOINT")
        token = os.getenv("DATABRICKS_TOKEN")
        
        # Build full URL for small model
        small_llm = None
        if small_llm_model:
            if not small_llm_model.startswith("http"):
                base_url = main_llm.rsplit("/", 2)[0]
                small_llm = f"{base_url}/{small_llm_model}/invocations"
            else:
                small_llm = small_llm_model
            
            print(f"   🔧 70B: {main_llm.split('/')[-2]}")
            print(f"   🔧 7B: {small_llm.split('/')[-2]}")
            print(f"   🔧 Mode: Parallel processing")
        else:
            print(f"   🔧 LLM: {main_llm.split('/')[-2]}")
            print(f"   🔧 Mode: Single LLM")
        
        return extract_atomic(
            text=text_content,
            template_name=template_name,
            template_fields=template_fields,
            llm_endpoint=main_llm,
            small_llm_endpoint=small_llm,
            token=token,
            output_file=output_file
        )
    else:
        print(f"   📄 Small PDF, using direct extraction...")
        return structure_pdf_chunked(text_content, template_name, template_fields, snake_case_fields)
    
    # For small PDFs: Send all text directly to LLM
    llm = get_llm_instance()
    
    system_prompt = f"""You are a data extraction expert. Extract ALL employee/form data from the document text into a structured JSON array.

REQUIRED TEMPLATE FIELDS (snake_case):
{', '.join(snake_case_fields)}

EXTRACTION RULES:
1. CAREFULLY read the entire document text
2. Extract EVERY piece of data, even if partially visible or OCR-garbled
3. Map each data field to its corresponding snake_case template field name
4. For missing/empty fields: use "" (empty string)
5. Look for field labels, headers, and contextual clues to identify data
6. Return ONLY a JSON array starting with [ and ending with ]
7. NO markdown, NO explanations, NO intro text

IMPORTANT:
- Include ALL {len(snake_case_fields)} fields in each record
- Even if a field appears empty, include it with ""
- Preserve exact values as they appear (numbers, dates, codes, etc.)"""

    user_message = f"""DOCUMENT TEXT:
{text_content}

Extract all data as a JSON array with {len(snake_case_fields)} fields per record.
Template fields: {', '.join(snake_case_fields)}

JSON array:"""
    
    try:
        print(f"   ⏳ Calling LLM API...")
        api_start = time.time()
        
        response = llm.chat(
            user_message=user_message,
            system_prompt=system_prompt,
            max_tokens=8000,
            temperature=0.0
        )
        
        api_elapsed = time.time() - api_start
        print(f"   ⏱️  LLM API responded in {api_elapsed:.1f}s")
        print(f"   Response length: {len(response)} characters")
        
        # Parse response
        cleaned = clean_llm_json(response)
        data = json.loads(cleaned)
        rows = data if isinstance(data, list) else data.get("rows", [data] if isinstance(data, dict) else [])
        
        print(f"✅ Parsed JSON: {len(rows)} records extracted")
        
        # Ensure all template fields are present
        complete_rows = []
        for row in rows:
            complete_row = {field: row.get(field, "") for field in snake_case_fields}
            complete_rows.append(complete_row)
        
        print(f"📝 Filling missing fields from template...")
        print(f"✅ All {len(snake_case_fields)} template fields included")
        
        elapsed = time.time() - start_time
        print(f"   ⏱️  Structuring completed in {elapsed:.1f}s")
        
        return {
            "rows": complete_rows,
            "metadata": {
                "template": template_name,
                "fields": snake_case_fields,
                "record_count": len(complete_rows)
            }
        }
        
    except Exception as e:
        print(f"❌ Error structuring PDF: {str(e)[:200]}")
        return {
            "rows": [],
            "metadata": {
                "template": template_name,
                "error": str(e)
            }
        }


def structure_pdf_rag(text_content: str, template_name: str, template_fields: list, snake_case_fields: list) -> Dict:
    """
    RAG-based extraction with smart fallback:
    1. Try embeddings (if token valid)
    2. Fall back to keyword scoring (if embeddings fail)
    3. Last resort: process all chunks
    """
    import time
    
    print("   📊 Using RAG-based extraction (smart chunk selection)...")
    
    # Step 1: Chunk the document
    chunk_size = 3500
    chunks = []
    text_lines = text_content.split('\n')
    
    current_chunk = []
    current_size = 0
    
    for line in text_lines:
        line_len = len(line) + 1
        
        if current_size + line_len > chunk_size and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = current_chunk[-2:] if len(current_chunk) > 2 else []
            current_size = sum(len(l) + 1 for l in current_chunk)
        
        current_chunk.append(line)
        current_size += line_len
    
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    total_chunks = len(chunks)
    print(f"   Split into {total_chunks} chunks (~{chunk_size} chars each)")
    
    # Step 2: Try embeddings first (with 10s timeout)
    embed_start = time.time()
    selected_chunks = None
    
    try:
        print(f"   📝 Trying Databricks embeddings (10s timeout)...")
        embedder = DatabricksEmbeddings()
        
        # Create query
        query = f"Extract {template_name} data with fields: {', '.join(template_fields[:10])}"
        
        # Embed with timeout
        query_embedding = embedder.embed_texts([query])[0]
        chunk_embeddings = embedder.embed_texts(chunks)
        
        # Cosine similarity
        query_vec = np.array(query_embedding).reshape(1, -1)
        chunk_vecs = np.array(chunk_embeddings)
        similarities = cosine_similarity(query_vec, chunk_vecs)[0]
        
        # Select top 50%
        top_k = max(3, total_chunks // 2)
        top_indices = np.argsort(similarities)[::-1][:top_k]
        top_indices = sorted(top_indices)
        
        selected_chunks = [(i+1, chunks[i]) for i in top_indices]
        
        embed_time = time.time() - embed_start
        print(f"   ✅ Embeddings succeeded ({embed_time:.1f}s) - selected {len(selected_chunks)}/{total_chunks} chunks")
        
    except Exception as e:
        embed_time = time.time() - embed_start
        print(f"   ⚠️ Embeddings failed ({embed_time:.1f}s): {str(e)[:80]}...")
        print(f"   🔄 Using keyword-based scoring instead...")
        
        # Fallback: Keyword scoring (fast, no API calls)
        keywords = set()
        for field in template_fields[:15]:
            keywords.update(field.lower().split())
        
        scores = []
        for i, chunk in enumerate(chunks):
            chunk_lower = chunk.lower()
            score = sum(1 for kw in keywords if kw in chunk_lower)
            scores.append((score, i))
        
        # Select top 50% by keyword score
        scores.sort(reverse=True)
        top_k = max(3, total_chunks // 2)
        top_indices = sorted([idx for _, idx in scores[:top_k]])
        
        selected_chunks = [(i+1, chunks[i]) for i in top_indices]
        print(f"   ✅ Keyword scoring selected {len(selected_chunks)}/{total_chunks} chunks (saved {total_chunks - len(selected_chunks)} API calls)")
    
    # Step 3: Process selected chunks
    return _process_chunks_parallel(selected_chunks, template_name, template_fields, snake_case_fields, total_chunks)


def _process_chunks_parallel(chunk_infos, template_name, template_fields, snake_case_fields, total_chunks):
    """
    Shared function to process chunks in parallel with LLM
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    llm = get_llm_instance()
    all_rows = []
    
    system_prompt = f"""Extract employee timesheet data as pure JSON array. Group consecutive records for the same employee together.

FIELDS: {', '.join(snake_case_fields)}

RULES:
1. Return ONLY valid JSON array: [{{}}, {{}}]
2. NO markdown, NO ```json, NO text
3. Group data by employee - if same employee appears multiple times, extract all their records together
4. Include all {len(snake_case_fields)} fields per record (use "" for empty)
5. Preserve exact values (dates, numbers, codes)
6. Extract EVERY data point visible

Output pure JSON starting with [ and ending with ] - nothing else."""
    
    def process_chunk(chunk_info):
        chunk_num, chunk_text = chunk_info
        max_retries = 8
        retry_delay = 3
        
        for attempt in range(max_retries):
            try:
                chunk_start = time.time()
                
                user_message = f"""Chunk {chunk_num}/{total_chunks}:

{chunk_text}

JSON array:"""
                
                response = llm.chat(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    max_tokens=8000,
                    temperature=0.0
                )
                
                chunk_elapsed = time.time() - chunk_start
                cleaned = clean_llm_json(response)
                data = json.loads(cleaned)
                chunk_rows = data if isinstance(data, list) else data.get("rows", [data] if isinstance(data, dict) else [])
                
                complete_rows = []
                for row in chunk_rows:
                    complete_row = {field: row.get(field, "") for field in snake_case_fields}
                    complete_rows.append(complete_row)
                
                return (chunk_num, complete_rows, chunk_elapsed, None)
                
            except Exception as e:
                error_str = str(e)
                chunk_elapsed = time.time() - chunk_start
                
                if "429" in error_str or "RATE_LIMIT" in error_str or "Too Many Requests" in error_str:
                    if attempt < max_retries - 1:
                        print(f"      ⏳ Chunk {chunk_num}: Rate limited (attempt {attempt+1}/{max_retries}), waiting {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 60)
                        continue
                    else:
                        return (chunk_num, [], chunk_elapsed, f"Rate limit exceeded after {max_retries} retries")
                
                if attempt < max_retries - 1:
                    print(f"      ⚠️ Chunk {chunk_num}: Error (attempt {attempt+1}/{max_retries}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return (chunk_num, [], chunk_elapsed, f"Error: {error_str[:100]}")
        
        return (chunk_num, [], 0, "Max retries exceeded")
    
    print(f"   ⚡ Processing {len(chunk_infos)} chunks with 4 workers (max speed)...")
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_chunk, info): info for info in chunk_infos}
        
        completed = 0
        for future in as_completed(futures):
            chunk_num, chunk_rows, chunk_elapsed, error = future.result()
            completed += 1
            
            if error:
                print(f"   📦 Chunk {chunk_num}/{total_chunks}... ⚠️ {error}")
            else:
                all_rows.extend(chunk_rows)
                print(f"   📦 Chunk {chunk_num}/{total_chunks}... ✅ {len(chunk_rows)} records ({chunk_elapsed:.1f}s) [{completed}/{len(chunk_infos)}]")
    
    # Deduplicate
    seen = set()
    unique_rows = []
    for row in all_rows:
        row_key = json.dumps(row, sort_keys=True)
        if row_key not in seen:
            seen.add(row_key)
            unique_rows.append(row)
    
    duplicates = len(all_rows) - len(unique_rows)
    if duplicates > 0:
        print(f"   🔄 Removed {duplicates} duplicate records")
    
    print(f"   ✅ Total: {len(unique_rows)} unique records extracted")
    
    return {
        "rows": unique_rows,
        "metadata": {
            "template": template_name,
            "method": "RAG-based extraction",
            "chunks_processed": len(chunk_infos),
            "chunks_total": total_chunks,
            "record_count": len(unique_rows)
        }
    }


def structure_pdf_chunked(text_content: str, template_name: str, template_fields: list, snake_case_fields: list) -> Dict:
    """
    Chunk large PDF text into smaller pieces for processing.
    Split by pages or paragraphs to avoid overwhelming the LLM.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Split text into smaller chunks for faster LLM processing (~2500 chars each)
    # Smaller chunks = faster per-chunk completion, more parallelism
    chunk_size = 2500
    chunks = []
    text_lines = text_content.split('\n')
    
    current_chunk = []
    current_size = 0
    
    for line in text_lines:
        line_len = len(line) + 1  # +1 for newline
        if current_size + line_len > chunk_size and current_chunk:
            chunks.append('\n'.join(current_chunk))
            # Keep last 2 lines for context overlap
            current_chunk = current_chunk[-2:] if len(current_chunk) > 2 else []
            current_size = sum(len(l) + 1 for l in current_chunk)
        
        current_chunk.append(line)
        current_size += line_len
    
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    total_chunks = len(chunks)
    print(f"   Split into {total_chunks} chunks (~{chunk_size} chars each)")
    
    llm = get_llm_instance()
    all_rows = []
    
    system_prompt = f"""Extract employee timesheet data as pure JSON array. Group consecutive records for the same employee together.

FIELDS: {', '.join(snake_case_fields)}

RULES:
1. Return ONLY valid JSON array: [{{}}, {{}}]
2. NO markdown, NO ```json, NO text
3. Group data by employee - if same employee appears multiple times, extract all their records together
4. Include all {len(snake_case_fields)} fields per record (use "" for empty)
5. Preserve exact values (dates, numbers, codes)
6. Extract EVERY data point visible

Output pure JSON starting with [ and ending with ] - nothing else."""
    
    def process_chunk(chunk_info):
        chunk_num, chunk_text = chunk_info
        max_retries = 6  # Faster retry cycles
        retry_delay = 1.5  # Ultra-fast 1.5 second initial delay
        
        for attempt in range(max_retries):
            try:
                chunk_start = time.time()
                
                user_message = f"""Chunk {chunk_num}/{total_chunks}:

{chunk_text}

JSON array:"""
                
                response = llm.chat(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    max_tokens=8000,
                    temperature=0.0
                )
                
                chunk_elapsed = time.time() - chunk_start
                cleaned = clean_llm_json(response)
                data = json.loads(cleaned)
                chunk_rows = data if isinstance(data, list) else data.get("rows", [data] if isinstance(data, dict) else [])
                
                complete_rows = []
                for row in chunk_rows:
                    complete_row = {field: row.get(field, "") for field in snake_case_fields}
                    complete_rows.append(complete_row)
                
                return (chunk_num, complete_rows, chunk_elapsed, None)
                
            except Exception as e:
                error_str = str(e)
                chunk_elapsed = time.time() - chunk_start
                
                # Check if it's a rate limit error
                if "429" in error_str or "RATE_LIMIT" in error_str or "Too Many Requests" in error_str:
                    if attempt < max_retries - 1:
                        print(f"      ⏳ Chunk {chunk_num}: Rate limited (attempt {attempt+1}/{max_retries}), waiting {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 60)  # Exponential backoff: 8s, 16s, 32s, max 60s
                        continue
                    else:
                        return (chunk_num, [], chunk_elapsed, f"Rate limit exceeded after {max_retries} retries")
                
                # Other errors (like JSON parse errors)
                if attempt < max_retries - 1:
                    print(f"      ⚠️ Chunk {chunk_num}: Error (attempt {attempt+1}/{max_retries}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return (chunk_num, [], chunk_elapsed, f"Error: {error_str[:100]}")
        
        return (chunk_num, [], 0, "Max retries exceeded")
    
    # Process with 6 workers for maximum speed (smaller chunks handle rate limits better)
    print(f"   ⚡ Processing {total_chunks} chunks with 6 workers (maximum speed)...")
    chunk_infos = [(i+1, chunk) for i, chunk in enumerate(chunks)]
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        # Submit all chunks for parallel processing
        futures = []
        for info in chunk_infos:
            future = executor.submit(process_chunk, info)
            futures.append((future, info))
        
        completed = 0
        for future, info in futures:
            chunk_num, chunk_rows, chunk_elapsed, error = future.result()
            completed += 1
            
            if error:
                print(f"   📦 Chunk {chunk_num}/{total_chunks}... ⚠️ {error}")
            else:
                all_rows.extend(chunk_rows)
                print(f"   📦 Chunk {chunk_num}/{total_chunks}... ✅ {len(chunk_rows)} records ({chunk_elapsed:.1f}s) [{completed}/{total_chunks}]")
    
    # Remove duplicates (chunks may overlap)
    # Simple deduplication: convert to dict using first unique field as key
    seen = set()
    unique_rows = []
    for row in all_rows:
        # Create a signature from non-empty values
        sig = tuple(v for v in row.values() if v)
        if sig and sig not in seen:
            seen.add(sig)
            unique_rows.append(row)
    
    if len(unique_rows) < len(all_rows):
        print(f"   🔄 Removed {len(all_rows) - len(unique_rows)} duplicate records")
    
    print(f"   ✅ Total: {len(unique_rows)} unique records extracted")
    
    return {
        "rows": unique_rows,
        "metadata": {
            "template": template_name,
            "fields": snake_case_fields,
            "record_count": len(unique_rows),
            "processing_mode": "pdf_chunked"
        }
    }


def structure_with_llm(text_content: str, template_name: str = "Employee_Profile") -> Dict:
    """Use Databricks LLM to structure extracted text"""
    import time
    start_time = time.time()
    
    print(f"\n🤖 Sending to Databricks LLM for structuring...")
    print(f"   Text length: {len(text_content)} characters")
    print(f"   Template: {template_name}")
    
    # Load template fields from registry
    registry_path = Path(__file__).parent / "templates" / "registry.json"
    template_fields = []
    
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry = json.load(f)
            if template_name in registry:
                template_fields = registry[template_name].get("columns", [])
                print(f"   Template has {len(template_fields)} fields")
            else:
                print(f"⚠️  Template '{template_name}' not found in registry")
    except Exception as e:
        print(f"⚠️  Could not load template: {e}")
    
    # Convert template field names to snake_case
    def to_snake_case(name: str) -> str:
        import re
        name = re.sub(r'[\s/\-]+', '_', name)
        name = re.sub(r'[^\w_]', '', name)
        return name.lower()
    
    snake_case_fields = [to_snake_case(field) for field in template_fields] if template_fields else []
    
    # Dynamic chunking based on estimated output size
    lines = text_content.strip().split('\n')
    num_rows = len(lines) - 1  # Subtract header
    num_fields = len(snake_case_fields)
    
    # Estimate output tokens: ~100 chars per field * num_fields * num_rows / 4 chars per token
    estimated_output_tokens = (num_fields * 100 * num_rows) / 4
    
    print(f"   Estimated output: {int(estimated_output_tokens)} tokens for {num_rows} rows × {num_fields} fields")
    
    # If estimated output > 7000 tokens, use chunking
    if estimated_output_tokens > 7000 or num_rows > 20:
        print(f"   ⚡ Chunking enabled (output would exceed limits)")
        result = structure_with_llm_chunked(text_content, template_name, template_fields)
        elapsed = time.time() - start_time
        print(f"   ⏱️  Structuring completed in {elapsed:.1f}s")
        return result
    
    llm = get_llm_instance()
    
    # Convert template field names to snake_case for JSON output
    def to_snake_case(name: str) -> str:
        """Convert field name to snake_case"""
        import re
        # Replace spaces, slashes, and other separators with underscore
        name = re.sub(r'[\s/\-]+', '_', name)
        # Remove special characters
        name = re.sub(r'[^\w_]', '', name)
        return name.lower()
    
    snake_case_fields = [to_snake_case(field) for field in template_fields] if template_fields else []
    snake_case_fields = [to_snake_case(field) for field in template_fields] if template_fields else []
    
    # Ultra-compact system prompt
    system_prompt = """Extract to JSON array. Rules:
1. EXACT column-to-field mapping  
2. ALL rows
3. Dates: YYYY-MM-DD
4. Empty cells: ""
5. snake_case field names
6. NO intro text - return ONLY JSON array starting with [

Return JSON array ONLY."""
    
    user_message = f"Data:\n{text_content}\n\nExtract to JSON array with {len(snake_case_fields)} fields. Return ONLY JSON array."
    
    print(f"   ⏳ Calling LLM API...")
    api_start = time.time()
    
    response = llm.chat(
        user_message=user_message,
        system_prompt=system_prompt,
        max_tokens=4096,  # Reduced from 8192 for faster response
        temperature=0.0
    )
    
    api_elapsed = time.time() - api_start
    print(f"   ⏱️  LLM API responded in {api_elapsed:.1f}s")
    print(f"   Response length: {len(response)} characters")
    
    # Parse JSON response
    try:
        cleaned = response.strip()
        
        # Remove intro text and markdown
        if cleaned.startswith("Here is") or cleaned.startswith("Here's"):
            lines = cleaned.split('\n')
            for i, line in enumerate(lines):
                if line.strip().startswith('```'):
                    cleaned = '\n'.join(lines[i:])
                    break
        
        if cleaned.startswith("```"):
            lines = cleaned.split('\n')
            start_idx = 0
            end_idx = len(lines)
            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    if start_idx == 0:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break
            cleaned = '\n'.join(lines[start_idx:end_idx])
        
        cleaned = cleaned.strip()
        data = json.loads(cleaned)
        
        # Extract rows from various response formats
        rows = []
        if isinstance(data, list):
            rows = data
            print(f"✅ Parsed JSON: {len(rows)} records extracted")
        elif isinstance(data, dict) and "detectedTemplates" in data:
            first_template = list(data["detectedTemplates"].values())[0]
            rows = first_template.get("data", [])
            print(f"✅ Parsed JSON: {len(rows)} records extracted (multi-template)")
        elif isinstance(data, dict) and "data" in data:
            rows = data.get("data", [])
            if not isinstance(rows, list):
                rows = [rows]
            print(f"✅ Parsed JSON: Data structure extracted")
        else:
            rows = [data] if isinstance(data, dict) else data
            print(f"✅ Parsed JSON: Single record extracted")
        
        # Fill in missing template fields with empty strings
        if snake_case_fields and rows:
            print(f"📝 Filling missing fields from template...")
            complete_rows = []
            for row in rows:
                complete_row = {}
                for field in snake_case_fields:
                    complete_row[field] = row.get(field, "")
                complete_rows.append(complete_row)
            print(f"✅ All {len(snake_case_fields)} template fields included")
            return {"rows": complete_rows}
        
        elapsed = time.time() - start_time
        print(f"   ⏱️  Structuring completed in {elapsed:.1f}s")
        return {"rows": rows}
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing failed: {e}")
        return {
            "error": f"JSON parsing failed: {e}",
            "raw_response": response[:500],
            "rows": []
        }


def process_extraction(job_id: str, file_path: Path, filename: str):
    """Background task to process file extraction"""
    import time
    overall_start = time.time()
    
    try:
        print(f"\n{'='*60}")
        print(f"🚀 STARTING EXTRACTION JOB: {job_id[:8]}...")
        print(f"📄 File: {filename}")
        print(f"{'='*60}")
        
        extraction_jobs[job_id]["status"] = "processing"
        
        # Initialize PowerMemory if not already done
        global power_memory
        if power_memory is None:
            power_memory = get_power_memory()
        
        # Determine file type
        file_ext = file_path.suffix.lower()
        is_pdf = file_ext == '.pdf'
        
        # Step 1: Extract text
        print(f"\n📖 STEP 1: EXTRACTION")
        step1_start = time.time()
        text_content = extract_file_content(file_path)
        step1_elapsed = time.time() - step1_start
        print(f"   ⏱️  Extraction took {step1_elapsed:.1f}s")
        
        # Save raw extracted text for inspection
        raw_output_dir = Path("output/raw_extraction")
        raw_output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_output_file = raw_output_dir / f"{filename.rsplit('.', 1)[0]}_raw_{timestamp}.txt"
        
        with open(raw_output_file, 'w', encoding='utf-8') as f:
            f.write(f"=== RAW EXTRACTION RESULTS ===\n")
            f.write(f"File: {filename}\n")
            f.write(f"Extracted at: {datetime.now().isoformat()}\n")
            f.write(f"Character count: {len(text_content)}\n")
            f.write(f"{'='*60}\n\n")
            f.write(text_content)
        
        print(f"📝 Raw extraction saved to: {raw_output_file}")
        
        # Step 2: Identify template
        print(f"\n🔍 STEP 2: TEMPLATE IDENTIFICATION")
        step2_start = time.time()
        template_name = identify_template(text_content)
        step2_elapsed = time.time() - step2_start
        print(f"   ⏱️  Template ID took {step2_elapsed:.1f}s")
        
        # Prepare output file path for streaming
        output_dir = Path("output/extract")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{filename.rsplit('.', 1)[0]}_{timestamp}.json"
        
        # Step 3: Structure with LLM - DIFFERENT PATHS FOR PDF vs CSV
        print(f"\n🤖 STEP 3: LLM STRUCTURING")
        step3_start = time.time()
        
        if is_pdf:
            # PDF path: Use specialized PDF structuring with streaming output
            print(f"   📄 Using PDF processing path...")
            structured_data = structure_pdf_with_llm(text_content, template_name, str(output_file))
        else:
            # CSV/Excel path: Use existing chunked processing
            print(f"   📊 Using CSV processing path...")
            structured_data = structure_with_llm(text_content, template_name)
        
        step3_elapsed = time.time() - step3_start
        print(f"   ⏱️  Structuring took {step3_elapsed:.1f}s")
        
        # Step 3.5: Analyze and cache file structure (GLOBAL CACHE)
        if structured_data.get('rows') and power_memory:
            try:
                print(f"\n📊 ANALYZING FILE STRUCTURE (Global Cache)...")
                cache = power_memory.analyze_file(
                    data=structured_data['rows'],
                    file_path=str(output_file),
                    user_id="global"  # Global cache for all users
                )
                
                # Store cache info in metadata
                if 'metadata' not in extraction_jobs[job_id]:
                    extraction_jobs[job_id]['metadata'] = {}
                
                extraction_jobs[job_id]['metadata']['structure_cache'] = {
                    'cache_id': cache.cache_id,
                    'structure_hash': cache.structure_hash,
                    'usage_count': cache.usage_count,
                    'is_cached': cache.usage_count > 1,
                    'total_files_with_structure': len(cache.file_paths)
                }
                
                if cache.usage_count > 1:
                    print(f"   ✅ Structure recognized from {cache.usage_count - 1} previous files")
                else:
                    print(f"   📦 New structure cached for future use")
                    
            except Exception as e:
                print(f"   ⚠️ Structure caching skipped: {e}")
        
        # Step 4: Save result
        print(f"\n💾 STEP 4: SAVING RESULTS")
        extraction_jobs[job_id].update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "metadata": {
                "source_file": filename,
                "processed_at": datetime.now().isoformat(),
                "template": {
                    "name": template_name,
                    "confidence": 1.0
                },
                "extraction_method": "Databricks LLM API Extraction",
                "record_count": len(structured_data.get("rows", []))
            },
            "data": structured_data
        })
        
        # Save to file
        output_dir = Path("output/extract")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{filename.rsplit('.', 1)[0]}_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(extraction_jobs[job_id], f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved to: {output_file}")
        
        # Cleanup uploaded file
        file_path.unlink(missing_ok=True)
        
        overall_elapsed = time.time() - overall_start
        
        print(f"\n{'='*60}")
        print(f"✅ EXTRACTION COMPLETE!")
        print(f"📊 Template: {template_name}")
        print(f"📊 Records extracted: {len(structured_data.get('rows', []))}")
        print(f"📁 Output: {output_file.name}")
        print(f"⏱️  Total time: {overall_elapsed:.1f}s")
        print(f"{'='*60}\n")
        
    except Exception as e:
        extraction_jobs[job_id].update({
            "status": "failed",
            "completed_at": datetime.now().isoformat(),
            "error": str(e)
        })


# API Endpoints
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": "AI-RAG Document Extraction API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "upload": "POST /extract/upload",
            "get_job": "GET /extract/jobs/{job_id}",
            "list_jobs": "GET /extract/list"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "extraction-api"
    }


@app.post("/extract/upload", response_model=ExtractionJob, tags=["Document Extraction"])
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to extract (CSV, Excel, PDF, DOCX, TXT)")
):
    """
    Upload a file for extraction
    
    Supported formats: CSV, Excel (.xlsx, .xls), PDF, DOCX, TXT
    
    Returns a job_id to check the extraction status and retrieve results.
    """
    # Validate file type
    allowed_extensions = {'.csv', '.xlsx', '.xls', '.pdf', '.docx', '.txt'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Create job
    job_id = str(uuid.uuid4())
    uploaded_at = datetime.now().isoformat()
    
    # Save uploaded file temporarily
    upload_dir = Path("output/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{job_id}{file_ext}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create job record
    extraction_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "filename": file.filename,
        "uploaded_at": uploaded_at,
        "completed_at": None,
        "error": None
    }
    
    # Start background processing
    background_tasks.add_task(process_extraction, job_id, file_path, file.filename)
    
    return ExtractionJob(**extraction_jobs[job_id])


@app.get("/extract/jobs/{job_id}", response_model=ExtractionResult, tags=["Document Extraction"])
async def get_extraction_job(job_id: str):
    """
    Get extraction job status and results
    
    Returns the complete extraction result including metadata and extracted data.
    """
    if job_id not in extraction_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return ExtractionResult(**extraction_jobs[job_id])


@app.get("/extract/list", response_model=List[ExtractionJob], tags=["Document Extraction"])
async def list_extraction_jobs(
    status: Optional[str] = None,
    limit: int = 50
):
    """
    List all extraction jobs
    
    Optional filters:
    - status: Filter by status (pending, processing, completed, failed)
    - limit: Maximum number of results (default: 50)
    """
    jobs = list(extraction_jobs.values())
    
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    
    # Sort by upload time (newest first)
    jobs.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
    
    return [ExtractionJob(**job) for job in jobs[:limit]]


@app.delete("/extract/jobs/{job_id}", tags=["Document Extraction"])
async def delete_extraction_job(job_id: str):
    """
    Delete an extraction job and its results
    """
    if job_id not in extraction_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete from memory
    del extraction_jobs[job_id]
    
    # Delete saved file (try both old and new locations)
    output_file = Path(f"output/json/{job_id}.json")
    output_file.unlink(missing_ok=True)
    
    return {"message": "Job deleted successfully", "job_id": job_id}


@app.on_event("startup")
async def startup_event():
    """Initialize PowerMemory on startup"""
    global power_memory
    power_memory = get_power_memory()
    print("🚀 Server startup complete - PowerMemory ready")


if __name__ == "__main__":
    import uvicorn
    from core.env_config import config
    
    # Ensure directories exist
    config.ensure_directories()
    
    print("=" * 60)
    print("AI-RAG Document Processing Engine")
    print("=" * 60)
    print(f"Host: {config.HOST}")
    print(f"Port: {config.PORT}")
    print(f"API Docs: http://localhost:{config.PORT}/docs")
    print("=" * 60)
    
    uvicorn.run(
        app, 
        host=config.HOST, 
        port=config.PORT,
        reload=config.RELOAD
    )

