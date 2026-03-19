"""
File Structure Intelligence - detects and caches file structures for quick manipulation
"""

import re
import hashlib
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from ..models import FileStructureCache


class FileStructureIntelligence:
    """Intelligent file structure detection and caching"""
    
    def __init__(self, session_store):
        """Initialize with session store"""
        self.session_store = session_store
    
    def analyze_file_structure(
        self,
        data: List[Dict[str, Any]],
        file_path: str,
        user_id: str = "global"
    ) -> FileStructureCache:
        """
        Analyze file structure and check cache
        
        Args:
            data: List of records from file
            file_path: Path to the file
            user_id: User identifier (default: "global" for cross-user caching)
        
        Returns:
            FileStructureCache object (existing or new)
        """
        
        if not data:
            raise ValueError("Empty data provided")
        
        # Extract file type from path
        file_type = Path(file_path).suffix.lstrip('.')
        
        # Build column schema
        sample = data[0]
        column_schema = {}
        
        for key, value in sample.items():
            # Infer type
            if isinstance(value, bool):
                col_type = "boolean"
            elif isinstance(value, int):
                col_type = "integer"
            elif isinstance(value, float):
                col_type = "float"
            elif isinstance(value, str):
                if value == "":
                    col_type = "string"
                elif self._is_date(value):
                    col_type = "date"
                else:
                    col_type = "string"
            else:
                col_type = "string"
            
            column_schema[key] = col_type
        
        # Create structure hash
        structure_hash = self._hash_structure(column_schema)
        
        # Check if cache exists
        existing_cache = self.session_store.find_file_cache(
            user_id=user_id,
            structure_hash=structure_hash,
            file_type=file_type
        )
        
        if existing_cache:
            print(f"   ✅ Found cached structure (used {existing_cache.usage_count} times globally)")
            print(f"   📁 Previously seen in {len(existing_cache.file_paths)} files")
            # Update usage
            self.session_store.update_file_cache_usage(existing_cache.cache_id, file_path)
            return existing_cache
        
        # Create new cache entry
        sample_data = data[:5] if len(data) >= 5 else data
        
        cache = FileStructureCache(
            cache_id=str(uuid.uuid4()),
            user_id=user_id,
            file_type=file_type,
            structure_hash=structure_hash,
            column_schema=column_schema,
            sample_data=sample_data,
            total_records=len(data),
            file_paths=[file_path]
        )
        
        self.session_store.create_file_cache(cache)
        print(f"   📦 Created new structure cache (global)")
        print(f"   🔑 Structure hash: {structure_hash}")
        
        return cache
    
    def get_manipulation_context(
        self,
        cache: FileStructureCache,
        query: str,
        llm
    ) -> Dict[str, Any]:
        """
        Get intelligent context for file manipulation using cached structure
        
        Args:
            cache: Cached file structure
            query: User query for manipulation
            llm: LLM instance
        
        Returns:
            Context dict with operation details
        """
        
        system_prompt = f"""You are analyzing a data manipulation query for a file with this structure:

File Type: {cache.file_type}
Columns: {', '.join(cache.column_schema.keys())}
Column Types: {json.dumps(cache.column_schema, indent=2)}
Total Records: {cache.total_records}
Previous Files with Same Structure: {len(cache.file_paths)}

Based on the cached structure, provide optimized manipulation strategy.

Return JSON:
{{
  "operation": "add_column|remove_column|remove_rows|update_values|transform",
  "complexity": "simple|medium|complex",
  "estimated_time": "fast|medium|slow",
  "requires_llm": true|false,
  "batch_size": 10-100,
  "strategy": "Brief description of approach",
  "warnings": ["Any potential issues"]
}}"""
        
        user_message = f"""Query: {query}

Sample data:
{json.dumps(cache.sample_data[:2], indent=2)}

Provide manipulation strategy as JSON:"""
        
        try:
            response = llm.chat(
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=500,
                temperature=0.0
            )
            
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            
            return {"operation": "unknown", "complexity": "medium"}
        except:
            return {"operation": "unknown", "complexity": "medium"}
    
    def _hash_structure(self, column_schema: Dict[str, str]) -> str:
        """Create hash of column structure"""
        # Sort columns for consistent hashing
        sorted_schema = json.dumps(column_schema, sort_keys=True)
        return hashlib.sha256(sorted_schema.encode()).hexdigest()[:16]
    
    def _is_date(self, value: str) -> bool:
        """Check if string looks like a date"""
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # DD-MM-YYYY
        ]
        
        for pattern in date_patterns:
            if re.match(pattern, value):
                return True
        return False
    
    def get_cached_structures(self, user_id: str) -> List[FileStructureCache]:
        """Get all cached structures for a user"""
        return self.session_store.get_user_file_caches(user_id)
