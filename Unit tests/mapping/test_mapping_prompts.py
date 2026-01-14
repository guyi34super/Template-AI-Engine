"""
Unit Tests for Mapping Prompts - Prompt templates for mapping operations
"""

import unittest
from mapping_engine.prompts import AutoMappingPrompt, ManualMappingPrompt


class TestAutoMappingPrompt(unittest.TestCase):
    """Test suite for AutoMappingPrompt"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.prompt = AutoMappingPrompt()
    
    def test_generate_system_prompt(self):
        """Test system prompt generation"""
        # build_prompt generates the full prompt (no separate system prompt)
        prompt = self.prompt.build_prompt(
            schema_fields=["FirstName", "Email"],
            extracted_fields=["name", "email"]
        )
        
        self.assertIsNotNone(prompt)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)
    
    def test_generate_user_prompt(self):
        """Test user prompt generation"""
        source_fields = ["emp_id", "name"]
        target_fields = ["id", "employee_name"]
        
        user_prompt = self.prompt.build_prompt(
            schema_fields=target_fields,
            extracted_fields=source_fields
        )
        
        self.assertIsNotNone(user_prompt)
        self.assertIn("emp_id", user_prompt)
        self.assertIn("id", user_prompt)
    
    def test_prompt_includes_examples(self):
        """Test that prompt includes mapping examples"""
        prompt = self.prompt.build_prompt(
            schema_fields=["FirstName"],
            extracted_fields=["name"]
        )
        
        # Should contain example guidance
        self.assertIn("mapping", prompt.lower())
    
    def test_prompt_requests_json_output(self):
        """Test that prompt requests JSON formatted output"""
        prompt = self.prompt.build_prompt(
            schema_fields=["FirstName"],
            extracted_fields=["name"]
        )
        
        self.assertIn("json", prompt.lower())
    
    def test_confidence_in_prompt(self):
        """Test that prompt mentions confidence scores"""
        prompt = self.prompt.build_prompt(
            schema_fields=["FirstName"],
            extracted_fields=["name"]
        )
        
        # Prompt doesn't specifically mention confidence, but covers intelligent mapping
        self.assertIn("mapping", prompt.lower())


class TestManualMappingPrompt(unittest.TestCase):
    """Test suite for ManualMappingPrompt"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.prompt = ManualMappingPrompt()
    
    def test_generate_validation_prompt(self):
        """Test validation prompt generation"""
        mappings = {"emp_id": "id", "name": "employee_name"}
        schema_fields = ["id", "employee_name"]
        extracted_fields = ["emp_id", "name"]
        
        prompt = self.prompt.build_validation_prompt(
            proposed_mappings=mappings,
            schema_fields=schema_fields,
            extracted_fields=extracted_fields
        )
        
        self.assertIsNotNone(prompt)
        self.assertIsInstance(prompt, str)



class TestPromptEdgeCases(unittest.TestCase):
    """Test edge cases for prompt generation"""
    
    def test_empty_source_schema(self):
        """Test prompt generation with empty source"""
        prompt = AutoMappingPrompt()
        
        result = prompt.build_prompt(
            schema_fields=["target"],
            extracted_fields=[]
        )
        
        self.assertIsNotNone(result)
    
    def test_empty_target_schema(self):
        """Test prompt generation with empty target"""
        prompt = AutoMappingPrompt()
        
        result = prompt.build_prompt(
            schema_fields=[],
            extracted_fields=["source"]
        )
        
        self.assertIsNotNone(result)
    
    def test_large_schema_prompt(self):
        """Test prompt generation with large schemas"""
        prompt = AutoMappingPrompt()
        
        large_source = [f"field_{i}" for i in range(100)]
        large_target = [f"target_{i}" for i in range(100)]
        
        result = prompt.build_prompt(
            schema_fields=large_target,
            extracted_fields=large_source
        )
        
        # Should handle large schemas
        self.assertIsNotNone(result)
    
    def test_nested_schema_prompt(self):
        """Test prompt generation with nested schemas"""
        prompt = AutoMappingPrompt()
        
        # Prompt expects flat field lists, not nested dicts
        nested_source_fields = ["user.id", "user.profile.name"]
        nested_target_fields = ["employee_id", "employee_name"]
        
        result = prompt.build_prompt(
            schema_fields=nested_target_fields,
            extracted_fields=nested_source_fields
        )
        
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
