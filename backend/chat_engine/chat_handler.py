"""
Chat Handler - Main orchestrator for query-based JSON modification
"""

import json
from typing import Dict, List, Any
from .json_manager import JSONManager
from .hash_protector import HashProtector


class ChatHandler:
    """Handle chat-based JSON modifications with LLM"""
    
    def __init__(self, llm):
        """Initialize with LLM instance"""
        self.llm = llm
        self.json_manager = JSONManager()
        self.hash_protector = HashProtector()
    
    def process_query(
        self,
        json_data: List[Dict],
        query: str,
        file_format: str = 'json'
    ) -> Dict:
        """
        Process a modification query on JSON data
        
        Args:
            json_data: List of records
            query: Natural language query describing changes
            file_format: 'json' or 'jsonl'
        
        Returns:
            {
                'success': bool,
                'operation': str,
                'changes_summary': dict,
                'modified_data': List[Dict]
            }
        """
        print(f"\n🔍 Processing query: {query}")
        print(f"   Total records: {len(json_data)}")
        
        # Step 1: Detect operation type
        print(f"\n📋 Step 1: Analyzing query type...")
        operation = self._detect_operation(query)
        print(f"   Operation: {operation}")
        
        # Step 2: Execute operation
        if operation == "add_column":
            return self._add_column(json_data, query)
        elif operation == "remove_column":
            return self._remove_column(json_data, query)
        elif operation == "remove_rows":
            return self._remove_rows(json_data, query)
        elif operation == "update_values":
            return self._update_values(json_data, query)
        else:
            return {
                'success': False,
                'error': f'Unknown operation: {operation}',
                'modified_data': json_data
            }
    
    def _detect_operation(self, query: str) -> str:
        """Detect operation type from query"""
        query_lower = query.lower()
        
        # Check for add column/field operations
        if any(phrase in query_lower for phrase in [
            "add column", "add field", "add a column", "add a field",
            "create column", "create field", "new column", "new field",
            "insert column", "insert field"
        ]):
            return "add_column"
        
        # Check for remove column operations
        elif any(phrase in query_lower for phrase in [
            "remove column", "delete column", "remove field", "delete field",
            "drop column", "drop field"
        ]):
            return "remove_column"
        
        # Check for remove row operations
        elif any(phrase in query_lower for phrase in [
            "remove row", "delete row", "remove record", "delete record",
            "drop row", "remove where", "delete where"
        ]):
            return "remove_rows"
        
        # Default to update
        else:
            return "update_values"
    
    def _add_column(self, json_data: List[Dict], query: str) -> Dict:
        """Add a new column to records with intelligent positioning"""
        print(f"\n➕ Adding column...")
        
        # Get sample record for column analysis
        sample_record = json_data[0] if json_data else {}
        existing_columns = list(sample_record.keys())
        
        # Extract column details from query with positioning info
        system_prompt = """Extract column addition details from query.
Return JSON with these fields:
- column_name: name of the new column
- default_value: default value for the column (can be empty string)
- position_reference: the column name to position relative to (e.g., "end_time")
- position_type: "after" or "before" (where to place new column relative to reference)
- condition: optional filter condition {"field": "field", "operator": "equals", "value": "val"}

If no specific position is mentioned, set position_reference and position_type to null.
If no condition, set condition to null.

Examples:
- "add column test after end_time" -> {"column_name": "test", "default_value": "", "position_reference": "end_time", "position_type": "after", "condition": null}
- "add test before break_minutes" -> {"column_name": "test", "default_value": "", "position_reference": "break_minutes", "position_type": "before", "condition": null}
- "add status column" -> {"column_name": "status", "default_value": "", "position_reference": null, "position_type": null, "condition": null}"""
        
        user_message = f"""Query: {query}

Existing columns in the data: {', '.join(existing_columns)}

Extract column details as JSON:"""
        
        response = self.llm.chat(
            user_message=user_message,
            system_prompt=system_prompt,
            max_tokens=400,
            temperature=0.0
        )
        
        try:
            import re
            match = re.search(r'\{[^}]*\}', response, re.DOTALL)
            details = json.loads(match.group(0)) if match else {}
        except Exception as e:
            print(f"   ⚠️ Warning: Could not parse LLM response: {e}")
            details = {}
        
        column_name = details.get("column_name", "new_field")
        default_value = details.get("default_value", "")
        condition = details.get("condition")
        position_reference = details.get("position_reference")
        position_type = details.get("position_type", "after")
        
        print(f"   📍 Column: '{column_name}'")
        if position_reference:
            print(f"   📍 Position: {position_type} '{position_reference}'")
        
        # Apply column addition with positioning
        modified_data = []
        modified_count = 0
        
        for record in json_data:
            # Check if condition matches
            should_add = True
            if condition and condition.get("field"):
                field = condition["field"]
                operator = condition.get("operator", "equals")
                value = str(condition.get("value", "")).lower()
                
                if field in record:
                    record_val = str(record[field]).lower()
                    if operator == "equals":
                        should_add = record_val == value
                    elif operator == "contains":
                        should_add = value in record_val
                    else:
                        should_add = False
            
            if should_add and column_name not in record:
                # Create new record with proper column ordering
                new_record = {}
                column_added = False
                
                for key in record.keys():
                    # Add positioned column before reference
                    if position_reference and position_type == "before" and key == position_reference:
                        new_record[column_name] = default_value
                        column_added = True
                    
                    # Copy existing field
                    new_record[key] = record[key]
                    
                    # Add positioned column after reference
                    if position_reference and position_type == "after" and key == position_reference:
                        new_record[column_name] = default_value
                        column_added = True
                
                # If position not found or no position specified, add at end
                if not column_added:
                    new_record[column_name] = default_value
                
                modified_count += 1
                modified_data.append(new_record)
            else:
                modified_data.append(record.copy())
        
        print(f"   ✅ Added column '{column_name}' to {modified_count} records")
        
        return {
            'success': True,
            'operation': 'add_column',
            'changes_summary': {
                'column_name': column_name,
                'records_modified': modified_count,
                'position': f"{position_type} {position_reference}" if position_reference else "at end"
            },
            'modified_data': modified_data
        }
    
    def _remove_column(self, json_data: List[Dict], query: str) -> Dict:
        """Remove a column from all records with intelligent detection"""
        print(f"\n➖ Removing column...")
        
        # Get sample record for column analysis
        sample_record = json_data[0] if json_data else {}
        existing_columns = list(sample_record.keys())
        
        # Extract column name to remove
        system_prompt = """Extract column name(s) to remove from query.
Return JSON: {"column_names": ["name1", "name2", ...]}

Handle various formats:
- "remove column test" -> {"column_names": ["test"]}
- "delete end_time column" -> {"column_names": ["end_time"]}
- "remove test and status columns" -> {"column_names": ["test", "status"]}
- "drop the third column" -> determine from position (requires existing columns context)

If positional (like "third column"), infer from the existing columns list."""
        
        user_message = f"""Query: {query}

Existing columns in the data: {', '.join(existing_columns)}

Extract column name(s) to remove as JSON:"""
        
        response = self.llm.chat(
            user_message=user_message,
            system_prompt=system_prompt,
            max_tokens=300,
            temperature=0.0
        )
        
        try:
            import re
            match = re.search(r'\{[^}]*\}', response, re.DOTALL)
            details = json.loads(match.group(0)) if match else {}
        except Exception as e:
            print(f"   ⚠️ Warning: Could not parse LLM response: {e}")
            details = {}
        
        column_names = details.get("column_names", [])
        
        if not column_names:
            return {
                'success': False,
                'error': 'Could not identify column name(s) to remove',
                'modified_data': json_data
            }
        
        # Remove columns from all records
        modified_data = []
        removed_counts = {col: 0 for col in column_names}
        
        for record in json_data:
            new_record = {}
            for key, value in record.items():
                if key not in column_names:
                    new_record[key] = value
                else:
                    removed_counts[key] += 1
            modified_data.append(new_record)
        
        total_removed = sum(removed_counts.values())
        print(f"   ✅ Removed {len(column_names)} column(s): {', '.join(column_names)}")
        print(f"   📊 Total removals: {total_removed} field instances")
        
        return {
            'success': True,
            'operation': 'remove_column',
            'changes_summary': {
                'column_names': column_names,
                'removal_details': removed_counts
            },
            'modified_data': modified_data
        }
    
    def _remove_rows(self, json_data: List[Dict], query: str) -> Dict:
        """Remove rows with intelligent condition detection"""
        print(f"\n🗑️ Removing rows...")
        
        # Get sample records for context
        sample_records = json_data[:3] if len(json_data) >= 3 else json_data
        sample_columns = list(sample_records[0].keys()) if sample_records else []
        
        # Use LLM to understand the removal criteria
        system_prompt = """Extract row removal criteria from the query.
Return JSON with one of these patterns:

1. Single condition:
{"type": "condition", "field": "field_name", "operator": "equals|contains|greater_than|less_than|not_equals", "value": "value"}

2. Multiple conditions (AND):
{"type": "multi_condition", "conditions": [{"field": "...", "operator": "...", "value": "..."}, ...], "logic": "AND"}

3. Multiple conditions (OR):
{"type": "multi_condition", "conditions": [{"field": "...", "operator": "...", "value": "..."}, ...], "logic": "OR"}

4. Positional (row numbers):
{"type": "positional", "indices": [0, 1, 2]}

5. Empty/null values:
{"type": "empty_field", "field": "field_name"}

Examples:
- "remove rows where employee_number is Flood, Carly" -> {"type": "condition", "field": "employee_number", "operator": "equals", "value": "Flood, Carly"}
- "delete rows with hours > 7" -> {"type": "condition", "field": "hours", "operator": "greater_than", "value": "7"}
- "remove first 5 rows" -> {"type": "positional", "indices": [0, 1, 2, 3, 4]}
- "remove rows where start_time is empty" -> {"type": "empty_field", "field": "start_time"}
- "delete rows where earning_code is Regular and hours < 5" -> {"type": "multi_condition", "conditions": [{"field": "earning_code", "operator": "equals", "value": "Regular"}, {"field": "hours", "operator": "less_than", "value": "5"}], "logic": "AND"}"""
        
        user_message = f"""Query: {query}

Available columns: {', '.join(sample_columns)}

Sample record:
{json.dumps(sample_records[0] if sample_records else {}, indent=2)}

Total records in dataset: {len(json_data)}

Extract the removal criteria as JSON:"""
        
        response = self.llm.chat(
            user_message=user_message,
            system_prompt=system_prompt,
            max_tokens=500,
            temperature=0.0
        )
        
        # Parse removal criteria
        try:
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                criteria = json.loads(match.group(0))
            else:
                criteria = {"type": "condition", "field": None}
        except Exception as e:
            print(f"   ⚠️ Warning: Could not parse criteria: {e}")
            criteria = {"type": "condition", "field": None}
        
        print(f"   🔍 Detection: {criteria.get('type', 'unknown')}")
        
        # Apply removal logic based on criteria type
        indices_to_remove = set()
        
        if criteria.get("type") == "positional":
            indices_to_remove = set(criteria.get("indices", []))
            print(f"   📍 Removing rows at positions: {sorted(list(indices_to_remove))}")
        
        elif criteria.get("type") == "empty_field":
            field = criteria.get("field")
            if field:
                for idx, record in enumerate(json_data):
                    value = record.get(field, "")
                    if value == "" or value is None:
                        indices_to_remove.add(idx)
                print(f"   🔍 Removing {len(indices_to_remove)} rows where '{field}' is empty")
        
        elif criteria.get("type") == "multi_condition":
            conditions = criteria.get("conditions", [])
            logic = criteria.get("logic", "AND")
            
            for idx, record in enumerate(json_data):
                if logic == "AND":
                    # All conditions must match
                    all_match = True
                    for cond in conditions:
                        if not self._evaluate_condition(record, cond):
                            all_match = False
                            break
                    if all_match:
                        indices_to_remove.add(idx)
                else:  # OR logic
                    # Any condition must match
                    for cond in conditions:
                        if self._evaluate_condition(record, cond):
                            indices_to_remove.add(idx)
                            break
            
            print(f"   🔍 Removing {len(indices_to_remove)} rows matching {logic} conditions")
        
        else:  # Single condition
            field = criteria.get("field")
            operator = criteria.get("operator", "equals")
            value = criteria.get("value")
            
            if field:
                for idx, record in enumerate(json_data):
                    if self._evaluate_condition(record, {"field": field, "operator": operator, "value": value}):
                        indices_to_remove.add(idx)
                
                print(f"   🔍 Removing {len(indices_to_remove)} rows where {field} {operator} {value}")
        
        if not indices_to_remove:
            print(f"   ℹ️ No rows matched the removal criteria")
            return {
                'success': True,
                'operation': 'remove_rows',
                'changes_summary': {'rows_removed': 0},
                'modified_data': json_data
            }
        
        # Remove matching records
        modified_data = [rec for idx, rec in enumerate(json_data) if idx not in indices_to_remove]
        
        print(f"   ✅ Removed {len(indices_to_remove)} rows")
        print(f"   📊 Remaining: {len(modified_data)} rows")
        
        return {
            'success': True,
            'operation': 'remove_rows',
            'changes_summary': {
                'rows_removed': len(indices_to_remove),
                'remaining_rows': len(modified_data),
                'criteria': criteria
            },
            'modified_data': modified_data
        }
    
    def _evaluate_condition(self, record: Dict, condition: Dict) -> bool:
        """Evaluate a single condition against a record"""
        field = condition.get("field")
        operator = condition.get("operator", "equals")
        target_value = condition.get("value")
        
        if not field or field not in record:
            return False
        
        record_value = record[field]
        
        # Handle different operators
        if operator == "equals":
            return str(record_value).lower() == str(target_value).lower()
        
        elif operator == "not_equals":
            return str(record_value).lower() != str(target_value).lower()
        
        elif operator == "contains":
            return str(target_value).lower() in str(record_value).lower()
        
        elif operator == "greater_than":
            try:
                return float(record_value) > float(target_value)
            except (ValueError, TypeError):
                return False
        
        elif operator == "less_than":
            try:
                return float(record_value) < float(target_value)
            except (ValueError, TypeError):
                return False
        
        elif operator == "greater_equal":
            try:
                return float(record_value) >= float(target_value)
            except (ValueError, TypeError):
                return False
        
        elif operator == "less_equal":
            try:
                return float(record_value) <= float(target_value)
            except (ValueError, TypeError):
                return False
        
        return False
    
    def _update_values(self, json_data: List[Dict], query: str) -> Dict:
        """Update values in matching records"""
        print(f"\n🔄 Updating values...")
        
        # Get matching indices
        matching_indices = self.json_manager.filter_by_query(json_data, query, self.llm)
        print(f"   Found {len(matching_indices)} matching records")
        
        if not matching_indices:
            return {
                'success': False,
                'error': 'No matching records found',
                'modified_data': json_data
            }
        
        # Extract subset and modify with LLM
        subset = self.json_manager.extract_subset(json_data, matching_indices)
        print(f"\n📦 Extracted {len(subset)} records for modification")
        
        # Add hash protection
        print(f"\n🔒 Adding hash protection...")
        protected_subset, hash_map = self.hash_protector.protect_records(subset)
        
        # Send to LLM for modification
        print(f"\n🤖 Sending to LLM for modification...")
        modified_subset = self._modify_with_llm(protected_subset, query)
        
        # Verify changes
        print(f"\n✅ Verifying changes...")
        verification = self.hash_protector.verify_changes(hash_map, modified_subset)
        
        print(f"   Modified: {len(verification['modified'])} records")
        print(f"   Unchanged: {len(verification['unchanged'])} records")
        print(f"   Invalid: {len(verification['invalid'])} records")
        
        # Merge changes back
        print(f"\n🔄 Merging changes...")
        modified_data = self.hash_protector.merge_changes(json_data, verification['modified'])
        
        # Update subset in original positions
        final_data = self.json_manager.merge_subset(modified_data, 
                                                     [rec for _, _, rec in verification['modified']], 
                                                     [idx for idx, _, _ in verification['modified']])
        
        return {
            'success': True,
            'operation': 'update_values',
            'changes_summary': {
                'total_modified': len(verification['modified']),
                'unchanged': len(verification['unchanged']),
                'invalid': len(verification['invalid'])
            },
            'modified_data': final_data
        }
    
    def _modify_with_llm(self, protected_records: List[Dict], query: str) -> List[Dict]:
        """Send protected records to LLM for modification (with batching for large datasets)"""
        
        # If too many records, process in batches
        BATCH_SIZE = 20  # Process 20 records at a time to stay under token limit
        if len(protected_records) > BATCH_SIZE:
            print(f"   📦 Processing {len(protected_records)} records in batches of {BATCH_SIZE}...")
            all_modified = []
            for i in range(0, len(protected_records), BATCH_SIZE):
                batch = protected_records[i:i+BATCH_SIZE]
                print(f"   Processing batch {i//BATCH_SIZE + 1}/{(len(protected_records)-1)//BATCH_SIZE + 1}...")
                modified_batch = self._modify_batch_with_llm(batch, query)
                all_modified.extend(modified_batch)
            return all_modified
        else:
            return self._modify_batch_with_llm(protected_records, query)
    
    def _modify_batch_with_llm(self, protected_records: List[Dict], query: str) -> List[Dict]:
        """Send a batch of protected records to LLM for modification"""
        
        system_prompt = """You are a JSON data modifier. You will receive:
1. A list of JSON records with hash protection (_hash field)
2. A modification query

CRITICAL RULES:
1. Keep the _hash field EXACTLY as provided for ALL records
2. Modify ONLY the data fields based on the query
3. Return the COMPLETE JSON array with ALL records
4. Preserve all fields, modify only what's requested
5. Return ONLY the JSON array, no explanation

Output format: [{"_hash": "...", "field1": "value1", ...}, {...}]"""
        
        user_message = f"""Modify these records based on the query.

Query: {query}

Records to modify:
{json.dumps(protected_records, indent=2)}

Return the modified JSON array with _hash fields preserved:"""
        
        response = self.llm.chat(
            user_message=user_message,
            system_prompt=system_prompt,
            max_tokens=4096,
            temperature=0.0
        )
        
        # Parse JSON response
        try:
            # Extract JSON array from response
            import re
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                modified = json.loads(match.group(0))
                return modified
            else:
                print(f"   ⚠️ Warning: Could not parse LLM response")
                return protected_records
        except Exception as e:
            print(f"   ❌ Error parsing LLM response: {str(e)}")
            print(f"   Response preview: {response[:500]}...")
            return protected_records
    
    def process_from_file(
        self,
        input_file: str,
        query: str,
        output_file: str = None
    ) -> Dict:
        """
        Process query on JSON/JSONL file
        
        Args:
            input_file: Path to JSON or JSONL file
            query: Modification query
            output_file: Optional output file path
        
        Returns:
            Result dictionary with modified data
        """
        # Detect file format
        is_jsonl = input_file.endswith('.jsonl')
        
        # Load data
        if is_jsonl:
            print(f"📂 Loading JSONL file: {input_file}")
            json_data = self.json_manager.load_jsonl(input_file)
        else:
            print(f"📂 Loading JSON file: {input_file}")
            data = self.json_manager.load_json(input_file)
            # Extract rows if wrapped
            if isinstance(data, dict) and 'rows' in data:
                json_data = data['rows']
            elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], dict) and 'rows' in data['data']:
                json_data = data['data']['rows']
            elif isinstance(data, list):
                json_data = data
            else:
                json_data = [data]
        
        # Process query
        result = self.process_query(json_data, query)
        
        # Save output if specified
        if output_file and result['success']:
            if output_file.endswith('.jsonl'):
                self.json_manager.save_jsonl(result['modified_data'], output_file)
            else:
                self.json_manager.save_json({'rows': result['modified_data']}, output_file)
            print(f"\n💾 Saved to: {output_file}")
        
        return result
