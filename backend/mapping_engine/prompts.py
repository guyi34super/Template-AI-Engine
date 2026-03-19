"""
Prompt strategies for Mapping Engine
"""

from typing import List, Dict
import json


class AutoMappingPrompt:
    """
    Intelligent field mapping prompt strategy
    Analyzes source fields and maps them to target schema fields using LLM
    """
    
    def __init__(self):
        self.prompt_type = "AutoMapping"
    
    def build_prompt(
        self,
        schema_fields: List[str],
        extracted_fields: List[str],
        schema_context: Dict[str, str] = None,
        extracted_context: Dict[str, str] = None
    ) -> str:
        """
        Build intelligent mapping prompt
        
        Args:
            schema_fields: List of target schema field names
            extracted_fields: List of source field names from uploaded file
            schema_context: Optional field descriptions for schema
            extracted_context: Optional sample values for extracted fields
        """
        
        # Format schema fields with context
        schema_text = self._format_fields_with_context(schema_fields, schema_context)
        
        # Format extracted fields with context
        extracted_text = self._format_fields_with_context(extracted_fields, extracted_context)
        
        prompt = f"""
You are an expert data field mapper. Your task is to intelligently map extracted field names from uploaded files to the most appropriate schema field names from a predefined template.

**Available Template Fields (Schema):**
{schema_text}

**Extracted Fields from File Headers:**
{extracted_text}

**Your Task:**
1. Analyze each extracted field name and find the best matching template field name
2. Consider semantic similarity, common naming conventions, and business context
3. Map each extracted field to exactly ONE template field
4. If no good match exists for a field, omit it from the mapping

**Mapping Rules:**
- Prioritize exact matches first (case-insensitive)
- Consider partial matches and synonyms (e.g., "fname" → "FirstName", "emp_id" → "EmployeeNumber")
- Handle common variations (e.g., "email_address" → "Email", "phone_number" → "Phone")
- Consider business context (e.g., "employee_id" → "EmployeeNumber", "dept" → "Department")
- Handle underscores, camelCase, PascalCase variations
- Look for abbreviations (e.g., "addr" → "Address", "dob" → "DateOfBirth")
- Consider sample values to understand field purpose

**Response Format:**
Return ONLY a clean JSON object with the mappings. No explanations, no additional text.

Example:
{{
    "first_name": "FirstName",
    "email_address": "Email",
    "phone_number": "Phone",
    "emp_id": "EmployeeNumber"
}}

**Important:**
- Return only valid JSON (no markdown code blocks, no extra text)
- Use the EXACT template field names from the schema
- Map each extracted field to only one template field
- If uncertain about a mapping, omit it rather than guess incorrectly
- Ensure JSON keys match the extracted field names exactly

Provide your JSON mapping now:
"""
        return prompt.strip()
    
    def _format_fields_with_context(
        self,
        fields: List[str],
        context: Dict[str, str] = None
    ) -> str:
        """Format field list with optional context"""
        if not context:
            return "\n".join(f"- {field}" for field in fields)
        
        lines = []
        for field in fields:
            if field in context:
                lines.append(f"- {field}: {context[field]}")
            else:
                lines.append(f"- {field}")
        return "\n".join(lines)
    
    def parse_llm_response(self, response: str) -> Dict[str, str]:
        """
        Parse LLM response to extract JSON mapping
        
        Args:
            response: Raw LLM response
            
        Returns:
            Dictionary of source_field -> target_field mappings
        """
        # Remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            # Remove first and last lines (``` markers)
            response = "\n".join(lines[1:-1]) if len(lines) > 2 else response
            # Remove json language identifier if present
            if response.strip().startswith("json"):
                response = response.strip()[4:].strip()
        
        # Try to parse JSON
        try:
            mappings = json.loads(response)
            if not isinstance(mappings, dict):
                raise ValueError("Response must be a JSON object")
            return mappings
        except json.JSONDecodeError as e:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except:
                    pass
            raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}")


class ManualMappingPrompt:
    """Manual mapping prompt for user-guided mapping"""
    
    def build_validation_prompt(
        self,
        proposed_mappings: Dict[str, str],
        schema_fields: List[str],
        extracted_fields: List[str]
    ) -> str:
        """Build prompt to validate manual mappings"""
        
        mappings_text = json.dumps(proposed_mappings, indent=2)
        
        prompt = f"""
Review the following manual field mappings for correctness:

**Schema Fields:**
{', '.join(schema_fields)}

**Extracted Fields:**
{', '.join(extracted_fields)}

**Proposed Mappings:**
{mappings_text}

Validate:
1. All mapped fields exist in both source and target
2. No duplicate target mappings
3. Semantically appropriate mappings

Return a JSON response:
{{
    "valid": true/false,
    "errors": ["list of validation errors"],
    "suggestions": {{"source_field": "suggested_target_field"}}
}}
"""
        return prompt.strip()
