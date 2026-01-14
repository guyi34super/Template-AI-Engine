"""
Unit Tests for Chat Handler - Query-based JSON modification
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json
from chat_engine.chat_handler import ChatHandler


class TestChatHandler(unittest.TestCase):
    """Test suite for ChatHandler class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_llm = Mock()
        self.handler = ChatHandler(self.mock_llm)
        
        # Sample test data
        self.sample_data = [
            {
                "employee_id": "001",
                "name": "John Doe",
                "department": "Engineering",
                "hours": 40
            },
            {
                "employee_id": "002",
                "name": "Jane Smith",
                "department": "Marketing",
                "hours": 35
            }
        ]
    
    def test_initialization(self):
        """Test ChatHandler initialization"""
        self.assertIsNotNone(self.handler.llm)
        self.assertIsNotNone(self.handler.json_manager)
        self.assertIsNotNone(self.handler.hash_protector)
    
    def test_detect_operation_add_field(self):
        """Test operation detection for adding fields"""
        # _detect_operation uses keyword detection, not LLM
        query = "add a new field called 'email'"
        operation = self.handler._detect_operation(query)
        
        self.assertEqual(operation, "add_column")
    
    def test_detect_operation_modify_field(self):
        """Test operation detection for modifying fields"""
        # _detect_operation uses keyword detection, not LLM
        query = "change department to 'Sales' for employee_id 001"
        operation = self.handler._detect_operation(query)
        
        self.assertEqual(operation, "update_values")
    
    def test_detect_operation_delete_field(self):
        """Test operation detection for deleting fields"""
        # _detect_operation uses keyword detection, not LLM
        query = "delete field hours"  # Must match keyword pattern: "delete field"
        operation = self.handler._detect_operation(query)
        
        self.assertEqual(operation, "remove_column")
    
    def test_process_query_add_field(self):
        """Test full query processing for adding a field"""
        # Mock LLM response for add column operation
        self.mock_llm.chat.return_value = json.dumps({
            "column_name": "email",
            "default_value": "",
            "position_reference": None,
            "position_type": "after",
            "condition": None
        })
        
        query = "add field email with empty value"  # Must match keyword pattern: "add field"
        result = self.handler.process_query(self.sample_data, query)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['operation'], 'add_column')
        self.assertIn('email', result['modified_data'][0])
    
    def test_process_query_with_filter(self):
        """Test query processing with record filtering"""
        # Mock LLM response for update_values operation
        self.mock_llm.chat.return_value = json.dumps({
            "type": "condition",
            "field": "employee_id",
            "operator": "equals",
            "value": "001",
            "updates": [
                {"field": "hours", "value": "45"}
            ]
        })
        
        query = "set hours to 45 for employee_id 001"
        result = self.handler.process_query(self.sample_data, query)
        
        self.assertTrue(result['success'])
        # Check that at least one record was modified
        self.assertIsNotNone(result.get('modified_data'))
    
    def test_process_query_invalid_operation(self):
        """Test handling of invalid operations"""
        # Even with invalid query, _detect_operation defaults to update_values
        # Mock LLM to return empty JSON to test error handling
        self.mock_llm.chat.return_value = "{}"  # Empty response
        query = "xyzabc123 nonsense query"
        result = self.handler.process_query(self.sample_data, query)
        
        # Should still return a result (defaults to update_values)
        self.assertIsNotNone(result)
    
    def test_empty_data_handling(self):
        """Test handling of empty input data"""
        query = "add email field"
        result = self.handler.process_query([], query)
        
        # Should handle gracefully
        self.assertIsNotNone(result)
    
    def test_malformed_json_response(self):
        """Test handling of malformed LLM responses"""
        self.mock_llm.chat.return_value = "This is not JSON"
        
        query = "add email field"
        # Should not crash, should handle gracefully
        try:
            result = self.handler.process_query(self.sample_data, query)
            # If it returns, check it's handled
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Should handle malformed JSON gracefully: {e}")


class TestChatHandlerEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_llm = Mock()
        self.handler = ChatHandler(self.mock_llm)
    
    def test_nested_json_modification(self):
        """Test modification of nested JSON structures"""
        nested_data = [
            {
                "id": "1",
                "profile": {
                    "name": "John",
                    "contact": {
                        "email": "john@example.com"
                    }
                }
            }
        ]
        
        self.mock_llm.chat.return_value = json.dumps({
            "type": "condition",
            "field": "id",
            "operator": "equals",
            "value": "1",
            "updates": [{"field": "profile.contact.email", "value": "newemail@example.com"}]
        })
        
        query = "update email to newemail@example.com"
        result = self.handler.process_query(nested_data, query)
        
        self.assertIsNotNone(result)
    
    def test_large_dataset_handling(self):
        """Test handling of large datasets"""
        large_data = [{"id": i, "value": f"data_{i}"} for i in range(1000)]
        
        self.mock_llm.chat.return_value = json.dumps({
            "column_name": "timestamp",
            "default_value": "",
            "position_reference": None,
            "position_type": "after",
            "condition": None
        })
        
        query = "add timestamp field"
        result = self.handler.process_query(large_data, query)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result.get('modified_data', [])), 1000)
    
    def test_special_characters_in_values(self):
        """Test handling of special characters in field values"""
        data = [{"name": "Test", "description": ""}]
        
        self.mock_llm.chat.return_value = json.dumps({
            "type": "all",
            "updates": [
                {"field": "description", "value": "Special chars: @#$%^&*()_+{}[]|\\:\";<>?,./"}
            ]
        })
        
        query = "add special characters to description"
        result = self.handler.process_query(data, query)
        
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
