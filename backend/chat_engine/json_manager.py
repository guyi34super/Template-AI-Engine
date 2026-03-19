"""
JSON Manager - Handles JSON breakdown, filtering, and merging
"""

import json
from typing import Dict, List, Any


class JSONManager:
    """Manage JSON data filtering and merging"""
    
    @staticmethod
    def load_json(file_path: str) -> Dict:
        """Load JSON from file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def load_jsonl(file_path: str) -> List[Dict]:
        """Load JSONL from file (one JSON object per line)"""
        records = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
    
    @staticmethod
    def save_json(data: Dict, file_path: str):
        """Save data to JSON file"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def save_jsonl(records: List[Dict], file_path: str):
        """Save records to JSONL file"""
        with open(file_path, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    @staticmethod
    def filter_by_query(records: List[Dict], query: str, llm) -> List[int]:
        """
        Use LLM to extract filter condition, then apply programmatically
        Returns: List of matching record indices
        """
        # Sample a few records to understand structure
        sample = records[:3]
        
        system_prompt = """You are a query analyzer. Extract the filter condition from the query.

Return JSON with:
{
  "field": "field_name",
  "operator": "equals|contains|greater_than|less_than",
  "value": "value_to_match"
}

Examples:
- "employee_number = kiran" -> {"field": "employee_number", "operator": "equals", "value": "kiran"}
- "hours > 8" -> {"field": "hours", "operator": "greater_than", "value": "8"}
- "add end time" (no filter) -> {"field": null, "operator": "all", "value": null}"""
        
        user_message = f"""Query: {query}

Sample record structure:
{json.dumps(sample[0] if sample else {}, indent=2)}

Extract the filter condition as JSON:"""
        
        response = llm.chat(
            user_message=user_message,
            system_prompt=system_prompt,
            max_tokens=500,
            temperature=0.0
        )
        
        # Parse filter condition
        try:
            import re
            match = re.search(r'\{[^}]*\}', response, re.DOTALL)
            if match:
                condition = json.loads(match.group(0))
            else:
                condition = {"field": None, "operator": "all", "value": None}
        except Exception as e:
            print(f"   ⚠️ Warning: Could not parse condition: {str(e)}")
            condition = {"field": None, "operator": "all", "value": None}
        
        # Apply filter programmatically
        matching_indices = []
        
        if condition.get("operator") == "all" or not condition.get("field"):
            # No filter - return all records
            return list(range(len(records)))
        
        field = condition["field"]
        operator = condition["operator"]
        value = condition["value"]
        
        for idx, record in enumerate(records):
            if field not in record:
                continue
            
            record_value = str(record[field]).strip().lower()
            compare_value = str(value).strip().lower()
            
            match = False
            if operator == "equals":
                match = record_value == compare_value
            elif operator == "contains":
                match = compare_value in record_value
            elif operator == "greater_than":
                try:
                    match = float(record_value) > float(compare_value)
                except:
                    pass
            elif operator == "less_than":
                try:
                    match = float(record_value) < float(compare_value)
                except:
                    pass
            
            if match:
                matching_indices.append(idx)
        
        return matching_indices
    
    @staticmethod
    def extract_subset(records: List[Dict], indices: List[int]) -> List[Dict]:
        """Extract subset of records by indices"""
        return [records[i] for i in indices if i < len(records)]
    
    @staticmethod
    def merge_subset(original: List[Dict], modified_subset: List[Dict], indices: List[int]) -> List[Dict]:
        """Merge modified subset back into original records"""
        merged = original.copy()
        for subset_idx, original_idx in enumerate(indices):
            if subset_idx < len(modified_subset) and original_idx < len(merged):
                merged[original_idx] = modified_subset[subset_idx]
        return merged
