"""
Hash Protector - Protects JSON data with hash for integrity verification
"""

import hashlib
import json
from typing import Dict, List, Any, Tuple


class HashProtector:
    """Protect and verify JSON data integrity using hashing"""
    
    @staticmethod
    def hash_record(record: Dict) -> str:
        """Generate SHA256 hash for a single record"""
        # Sort keys for consistent hashing
        sorted_json = json.dumps(record, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(sorted_json.encode('utf-8')).hexdigest()
    
    @staticmethod
    def protect_records(records: List[Dict]) -> Tuple[List[Dict], Dict[str, Dict]]:
        """
        Add hash protection to records
        Returns: (protected_records, hash_map)
        """
        protected = []
        hash_map = {}
        
        for record in records:
            record_hash = HashProtector.hash_record(record)
            protected_record = {
                "_hash": record_hash,
                **record
            }
            protected.append(protected_record)
            hash_map[record_hash] = record.copy()
        
        return protected, hash_map
    
    @staticmethod
    def verify_changes(original_hash_map: Dict[str, Dict], modified_records: List[Dict]) -> Dict:
        """
        Verify which records were changed
        Returns: {
            'modified': [(index, old_record, new_record)],
            'unchanged': [index],
            'invalid': [index]  # Hash mismatch
        }
        """
        result = {
            'modified': [],
            'unchanged': [],
            'invalid': []
        }
        
        for idx, record in enumerate(modified_records):
            if '_hash' not in record:
                result['invalid'].append(idx)
                continue
            
            original_hash = record.get('_hash')
            
            # Remove hash for comparison
            record_without_hash = {k: v for k, v in record.items() if k != '_hash'}
            new_hash = HashProtector.hash_record(record_without_hash)
            
            if original_hash not in original_hash_map:
                result['invalid'].append(idx)
            elif original_hash == new_hash:
                result['unchanged'].append(idx)
            else:
                original_record = original_hash_map[original_hash]
                result['modified'].append((idx, original_record, record_without_hash))
        
        return result
    
    @staticmethod
    def merge_changes(original_records: List[Dict], changes: List[Tuple[int, Dict, Dict]]) -> List[Dict]:
        """
        Merge verified changes back into original records
        changes: [(index, old_record, new_record)]
        """
        merged = original_records.copy()
        
        for idx, old_record, new_record in changes:
            if idx < len(merged):
                merged[idx] = new_record
        
        return merged
