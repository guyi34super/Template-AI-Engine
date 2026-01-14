"""
Atomic Record Extractor - Clean extraction with schema-based classification
Splits text into atomic records, classifies fields using vector DB, outputs JSONL
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from .vdb import VDB, template_collection
from .embeddings import embed_texts
from .databricks_llm import DatabricksLLM


class AtomicExtractor:
    """Extract and classify atomic records using vector DB schema matching with dual-LLM load balancing"""
    
    def __init__(self, llm_endpoint: str, token: str, small_llm_endpoint: str = None):
        self.llm_70b = DatabricksLLM(endpoint=llm_endpoint, token=token)
        self.llm_7b = DatabricksLLM(endpoint=small_llm_endpoint, token=token) if small_llm_endpoint else None
        self.vdb = VDB(template_collection())
        self.current_llm_index = 0  # For round-robin load balancing
    
    def extract_atomic_records(
        self,
        text: str,
        template_name: str,
        template_fields: List[str],
        output_file: str = None
    ) -> Dict:
        """
        Main extraction pipeline:
        1. Clean and split text into atomic records
        2. Classify fields using vector DB schema
        3. Feed classified data to LLM
        4. Output JSONL format
        """
        print(f"\n🔬 ATOMIC EXTRACTION")
        print(f"   Template: {template_name}")
        print(f"   Fields: {len(template_fields)}")
        print(f"   Text length: {len(text)} chars")
        
        # Step 1: Split into atomic records
        print(f"\n📝 Step 1: Splitting into atomic records...")
        atomic_chunks = self._split_into_atomic_records(text)
        print(f"   Found {len(atomic_chunks)} atomic text chunks")
        
        # Step 2: Classify fields using vector DB
        print(f"\n🔍 Step 2: Classifying fields with vector DB...")
        schema_mappings = self._classify_fields_with_vdb(template_name, template_fields)
        print(f"   Classified {len(schema_mappings)} fields")
        
        # Step 3: Extract structured data from text chunks with LLM (load balanced)
        if self.llm_7b:
            print(f"\n🤖 Step 3: Extracting with DUAL-LLM (load balanced)...")
            print(f"   70B: {self.llm_70b.endpoint.split('/')[-2]}")
            print(f"   7B: {self.llm_7b.endpoint.split('/')[-2]}")
        else:
            print(f"\n🤖 Step 3: Extracting with single LLM...")
        
        records = self._extract_from_text(
            text_chunks=atomic_chunks,
            template_name=template_name,
            template_fields=template_fields,
            schema_mappings=schema_mappings,
            output_file=output_file  # Pass output file for streaming
        )
        print(f"   Extracted {len(records)} records")
        
        # Step 4: Output file already saved via streaming
        if output_file:
            print(f"\n💾 Step 4: JSON output streamed to {output_file}")
        
        return {
            "rows": records,
            "metadata": {
                "template": template_name,
                "fields": template_fields,
                "record_count": len(records),
                "processing_mode": "atomic_extraction"
            }
        }
    
    def _split_into_atomic_records(self, text: str) -> List[str]:
        """
        Split text into atomic records (individual employee entries)
        Detects boundaries by employee numbers, dates, or blank lines
        """
        # Clean text first
        text = self._clean_text(text)
        
        # Split strategies (try multiple)
        chunks = []
        
        # Strategy 1: Split by employee number patterns
        # Matches: "EMP-12345", "Employee: 12345", "ID: 12345", etc.
        emp_pattern = r'(?:employee|emp|id|number|#)\s*:?\s*[A-Z0-9\-]{3,15}'
        matches = list(re.finditer(emp_pattern, text, re.IGNORECASE))
        
        if len(matches) > 5:  # If we found multiple employee markers
            print(f"   Using employee number strategy ({len(matches)} markers)")
            for i, match in enumerate(matches):
                start = match.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                chunk = text[start:end].strip()
                if len(chunk) > 50:  # Minimum viable record
                    chunks.append(chunk)
        else:
            # Strategy 2: Split by multiple blank lines
            print(f"   Using blank line strategy")
            blocks = re.split(r'\n\s*\n\s*\n', text)
            for block in blocks:
                block = block.strip()
                if len(block) > 50:
                    chunks.append(block)
        
        # If still no good chunks, split by size
        if len(chunks) < 3:
            print(f"   Using fixed-size strategy")
            chunk_size = 2500  # ~650 tokens - larger for better context
            chunks = []
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size].strip()
                if chunk:
                    chunks.append(chunk)
        
        return chunks
    
    def _convert_to_jsonl(self, text_chunks: List[str], template_fields: List[str]) -> List[str]:
        """Convert text chunks to JSONL format (one structured record per line)"""
        jsonl_records = []
        snake_fields = [self._to_snake_case(f) for f in template_fields]
        
        for i, chunk in enumerate(text_chunks):
            # Parse chunk into key-value pairs
            lines = chunk.strip().split('\n')
            record = {field: "" for field in snake_fields}
            
            # Try to extract structured data from text
            for line in lines:
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    value = value.strip()
                    
                    # Map to schema fields
                    for field in snake_fields:
                        if key in field or field in key:
                            record[field] = value
                            break
            
            # Convert to JSONL (one line)
            jsonl_records.append(json.dumps(record, ensure_ascii=False))
        
        return jsonl_records
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text - remove noise, normalize spacing"""
        # Remove page numbers
        text = re.sub(r'Page\s+\d+\s+of\s+\d+', '', text, flags=re.IGNORECASE)
        
        # Remove repeated headers/footers
        text = re.sub(r'(Employee\s+Timesheet\s+Report\s*\n){2,}', 'Employee Timesheet Report\n', text, flags=re.IGNORECASE)
        
        # Normalize whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove OCR artifacts
        text = re.sub(r'[^\x00-\x7F]+', '', text)  # Non-ASCII
        
        return text.strip()
    
    def _classify_fields_with_vdb(
        self,
        template_name: str,
        template_fields: List[str]
    ) -> Dict[str, Dict]:
        """
        Use vector DB to match template fields to their schema definitions
        Returns: {field_name: {data_type, format, rules, examples}}
        """
        schema_mappings = {}
        
        for field in template_fields:
            # Query vector DB for this field
            query_text = f"Template field: {field} in {template_name}"
            
            try:
                result = self.vdb.query(
                    query_texts=[query_text],
                    n_results=1
                )
                
                if result and result.get("metadatas"):
                    metadata = result["metadatas"][0][0]
                    
                    # Extract schema information
                    schema_mappings[field] = {
                        "data_type": metadata.get("data_type", "string"),
                        "length_format": metadata.get("length_format", ""),
                        "required": metadata.get("required", False),
                        "allowed_values": metadata.get("allowed_values", []),
                        "field_name": metadata.get("field_name", field)
                    }
                else:
                    # Fallback: infer from field name
                    schema_mappings[field] = self._infer_schema(field)
            
            except Exception as e:
                print(f"   ⚠️ VDB lookup failed for {field}: {e}")
                schema_mappings[field] = self._infer_schema(field)
        
        return schema_mappings
    
    def _infer_schema(self, field_name: str) -> Dict:
        """Infer schema from field name when VDB lookup fails"""
        field_lower = field_name.lower()
        
        # Date fields
        if any(x in field_lower for x in ['date', 'time', 'day']):
            return {
                "data_type": "date",
                "length_format": "YYYY-MM-DD",
                "required": True,
                "allowed_values": []
            }
        
        # Numeric fields
        if any(x in field_lower for x in ['hours', 'amount', 'number', 'count', 'quantity']):
            return {
                "data_type": "numeric",
                "length_format": "decimal(10,2)",
                "required": False,
                "allowed_values": []
            }
        
        # Code fields
        if any(x in field_lower for x in ['code', 'id', 'number']):
            return {
                "data_type": "string",
                "length_format": "varchar(20)",
                "required": False,
                "allowed_values": []
            }
        
        # Default: string
        return {
            "data_type": "string",
            "length_format": "varchar(255)",
            "required": False,
            "allowed_values": []
        }
    
    def _extract_from_text(
        self,
        text_chunks: List[str],
        template_name: str,
        template_fields: List[str],
        schema_mappings: Dict[str, Dict],
        output_file: str = None
    ) -> List[Dict]:
        """
        Extract structured data from text chunks using parallel LLM processing with streaming
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        import threading
        
        all_records = []
        records_lock = threading.Lock()  # For thread-safe record accumulation
        snake_case_fields = [self._to_snake_case(f) for f in template_fields]
        
        # Setup streaming to JSONL file (one record per line)
        streaming_file = None
        if output_file:
            streaming_file = open(output_file.replace('.json', '.jsonl'), 'w', encoding='utf-8')
        
        system_prompt = f"""Extract employee timesheet data to JSON array. Group consecutive records for the same employee together.

FIELDS: {', '.join(snake_case_fields)}

RULES:
1. Return ONLY valid JSON array: [{{}}, {{}}]
2. NO markdown, NO ```json, NO text
3. Group data by employee - if same employee appears multiple times, extract all their records
4. Include all {len(snake_case_fields)} fields per record (use "" for empty)
5. Return ONLY JSON array starting with ["""
        
        # Split chunks: first 10 small for 7B, rest for 70B (split further)
        chunks_7b = text_chunks[:10]  # First 10 for 7B
        remaining = text_chunks[10:]  # Rest to split further
        
        # Split remaining into smaller chunks (1500 chars) for 70B
        chunks_70b = []
        for chunk in remaining:
            if len(chunk) > 1500:
                # Split large chunk into smaller pieces
                for i in range(0, len(chunk), 1500):
                    piece = chunk[i:i+1500].strip()
                    if piece:
                        chunks_70b.append(piece)
            else:
                chunks_70b.append(chunk)
        
        print(f"   Split: {len(chunks_7b)} chunks for 7B, {len(chunks_70b)} chunks for 70B")
        
        # Phase 1: Start 7B processing (should take ~95s)
        # Process 7B chunks individually (1 chunk per batch) for speed
        batches_7b = [(i, [chunk]) for i, chunk in enumerate(chunks_7b)]
        
        # Phase 2: 70B processes in batches of 2
        batches_70b = []
        for i in range(0, len(chunks_70b), 2):
            batch = chunks_70b[i:i+2]
            batches_70b.append((i, batch))
        
        print(f"   Phase 1: {len(batches_7b)} batches for 7B (1 chunk each)")
        print(f"   Phase 2: {len(batches_70b)} batches for 70B (2 chunks each)")
        start_time = time.time()
        
        def process_batch(batch_info, llm_type):
            """Process a single batch with assigned LLM"""
            batch_idx, texts = batch_info
            batch_start = time.time()
            
            # Select LLM
            if llm_type == '7B' and self.llm_7b:
                llm = self.llm_7b
                llm_name = "7B"
            else:
                llm = self.llm_70b
                llm_name = "70B"
            
            # Combine text chunks
            combined_text = "\n\n---\n\n".join(texts)
            
            user_message = f"""Extract all timesheet data from this text:

{combined_text}

Return JSON array with {len(snake_case_fields)} fields: {', '.join(snake_case_fields[:5])}...

JSON array:"""
            
            try:
                response = llm.chat(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    max_tokens=8000,
                    temperature=0.0
                )
                
                parsed = self._parse_json_response(response)
                elapsed = time.time() - batch_start
                if parsed:
                    # Stream records to JSONL file immediately (one record per line)
                    if streaming_file:
                        with records_lock:
                            for record in parsed:
                                complete = {field: record.get(field, "") for field in snake_case_fields}
                                streaming_file.write(json.dumps(complete, ensure_ascii=False) + '\n')
                                streaming_file.flush()
                                all_records.append(complete)
                    
                    print(f"      ✅ [{llm_name}] Batch {batch_idx}: {len(parsed)} records ({elapsed:.1f}s)")
                    return (batch_idx, parsed, None, llm_name)
                else:
                    print(f"      ⚠️ [{llm_name}] Batch {batch_idx}: Parse failed ({elapsed:.1f}s)")
                    return (batch_idx, None, texts, llm_name)
            
            except Exception as e:
                elapsed = time.time() - batch_start
                print(f"      ❌ [{llm_name}] Batch {batch_idx}: {str(e)[:60]} ({elapsed:.1f}s)")
                return (batch_idx, None, texts, llm_name)
        
        # Phase 1: Process all 7B batches in parallel (should take ~95s)
        failed_batches = []
        batch_results = []
        remaining_70b_batches = list(batches_70b)  # For phase 3
        
        print(f"   🚀 Phase 1 & 2: Starting parallel processing (7B + 70B)...")
        
        # Submit both 7B and 70B batches to same executor for true parallelism
        num_workers = 6  # 4 for 7B + 2 for 70B
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all 7B batches
            futures_7b = {executor.submit(process_batch, batch, '7B'): ('7B', idx) 
                         for idx, batch in enumerate(batches_7b)}
            
            # Submit all 70B batches simultaneously
            futures_70b = {executor.submit(process_batch, batch, '70B'): ('70B', idx) 
                          for idx, batch in enumerate(batches_70b)}
            
            # Combine all futures
            all_futures = {**futures_7b, **futures_70b}
            
            # Collect results as they complete (both models running together)
            for future in as_completed(all_futures):
                model_type, batch_idx = all_futures[future]
                result_idx, parsed, failed_texts, llm_name = future.result()
                
                if parsed:
                    if model_type == '7B':
                        batch_results.append((batch_idx, parsed))
                    else:
                        batch_results.append((len(batches_7b) + batch_idx, parsed))
                elif failed_texts:
                    if model_type == '7B':
                        failed_batches.append((batch_idx, failed_texts, llm_name))
                    else:
                        failed_batches.append((len(batches_7b) + batch_idx, failed_texts, llm_name))
        
        elapsed_phase12 = time.time() - start_time
        print(f"   ✅ Phase 1 & 2 complete: {elapsed_phase12:.1f}s")
        
        # Phase 3: Use 7B to process any remaining failed batches from 70B
        if failed_batches and self.llm_7b:
            print(f"   🚀 Starting Phase 3: 7B cleanup ({len(failed_batches)} failed batches)...")
            phase3_start = time.time()
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures_retry = {executor.submit(process_batch, (idx, texts), '7B'): idx 
                               for idx, texts, _ in failed_batches}
                
                for future in as_completed(futures_retry):
                    batch_idx, parsed, failed_texts, llm_name = future.result()
                    
                    if parsed:
                        # Stream retry records to JSONL
                        if streaming_file:
                            with records_lock:
                                for record in parsed:
                                    complete = {field: record.get(field, "") for field in snake_case_fields}
                                    streaming_file.write(json.dumps(complete, ensure_ascii=False) + '\n')
                                    streaming_file.flush()
                                    all_records.append(complete)
                        batch_results.append((batch_idx, parsed))
            
            elapsed_phase3 = time.time() - phase3_start
            print(f"   ✅ Phase 3 complete: {elapsed_phase3:.1f}s")
        
        elapsed_total = time.time() - start_time
        print(f"   ⏱️  Total processing took {elapsed_total:.1f}s")
        
        # Sort results by batch index to maintain order (already added to all_records via streaming)
        batch_results.sort(key=lambda x: x[0])
        
        # Final retry for any still-failed batches with 70B
        remaining_failed = [fb for fb in failed_batches 
                          if not any(fb[0] == br[0] for br in batch_results)]
        
        if remaining_failed:
            print(f"\n   🔄 Final retry: {len(remaining_failed)} batches with 70B...")
            for batch_idx, texts, orig_llm in remaining_failed:
                llm = self.llm_70b
                llm_name = "70B"
                
                combined_text = "\n\n---\n\n".join(texts)
                user_message = f"""Extract all timesheet data from this text:

{combined_text}

Return JSON array with {len(snake_case_fields)} fields.

JSON array:"""
                
                try:
                    response = llm.chat(
                        user_message=user_message,
                        system_prompt=system_prompt,
                        max_tokens=6000,
                        temperature=0.0
                    )
                    
                    parsed = self._parse_json_response(response)
                    if parsed:
                        # Stream final retry records to JSONL
                        if streaming_file:
                            with records_lock:
                                for record in parsed:
                                    complete = {field: record.get(field, "") for field in snake_case_fields}
                                    streaming_file.write(json.dumps(complete, ensure_ascii=False) + '\n')
                                    streaming_file.flush()
                                    all_records.append(complete)
                        print(f"      ✅ [{llm_name}] Retry {len(texts)} chunks: {len(parsed)} records")
                    else:
                        fallback = self._parse_json_fallback(response, snake_case_fields)
                        if fallback:
                            # Stream fallback records to JSONL
                            if streaming_file:
                                with records_lock:
                                    for record in fallback:
                                        streaming_file.write(json.dumps(record, ensure_ascii=False) + '\n')
                                        streaming_file.flush()
                            all_records.extend(fallback)
                            print(f"      ✅ [{llm_name}] Retry fallback: {len(fallback)} records")
                except Exception as e:
                    print(f"      ❌ [{llm_name}] Retry failed: {str(e)[:60]}")
        
        # Close JSONL streaming file
        if streaming_file:
            streaming_file.close()
        
        return all_records
    def _parse_json_response(self, response: str) -> Optional[List[Dict]]:
        """Parse JSON from LLM response"""
        try:
            # Remove markdown
            response = re.sub(r'```json\s*', '', response)
            response = re.sub(r'```\s*', '', response)
            
            # Find JSON array
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                json_str = match.group(0)
                data = json.loads(json_str)
                return data if isinstance(data, list) else [data]
            
            return None
        
        except Exception as e:
            return None
    
    def _parse_json_fallback(self, response: str, fields: List[str]) -> Optional[List[Dict]]:
        """Fallback parser for malformed JSON"""
        try:
            # Try to find any JSON objects
            objects = re.findall(r'\{[^}]+\}', response, re.DOTALL)
            if objects:
                records = []
                for obj_str in objects:
                    try:
                        obj = json.loads(obj_str)
                        # Ensure all fields present
                        complete = {field: obj.get(field, "") for field in fields}
                        records.append(complete)
                    except:
                        continue
                return records if records else None
            return None
        except:
            return None
    
    def _write_json(self, records: List[Dict], template_name: str, template_fields: List[str], output_file: str):
        """Write records to JSON format (standard JSON array with metadata)"""
        output_path = Path(output_file)
        
        result = {
            "rows": records,
            "metadata": {
                "template": template_name,
                "fields": [self._to_snake_case(f) for f in template_fields],
                "record_count": len(records),
                "processing_mode": "atomic_extraction"
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    
    def _to_snake_case(self, name: str) -> str:
        """Convert to snake_case"""
        name = re.sub(r'[\s/\-]+', '_', name)
        name = re.sub(r'[^\w_]', '', name)
        return name.lower()


def extract_atomic(
    text: str,
    template_name: str,
    template_fields: List[str],
    llm_endpoint: str,
    token: str,
    small_llm_endpoint: str = None,
    output_file: str = None
) -> Dict:
    """
    Main entry point for atomic extraction with dual-LLM load balancing
    """
    extractor = AtomicExtractor(
        llm_endpoint=llm_endpoint,
        token=token,
        small_llm_endpoint=small_llm_endpoint
    )
    return extractor.extract_atomic_records(
        text=text,
        template_name=template_name,
        template_fields=template_fields,
        output_file=output_file
    )
