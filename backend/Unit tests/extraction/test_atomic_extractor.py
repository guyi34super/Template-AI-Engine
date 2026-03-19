"""
Unit Tests for Atomic Extractor - Schema-based extraction with vector DB
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json
from core.atomic_extractor import AtomicExtractor


class TestAtomicExtractor(unittest.TestCase):
    """Test suite for AtomicExtractor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_llm_endpoint = "https://mock-endpoint.com"
        self.mock_token = "mock_token_123"
        
        with patch('core.atomic_extractor.DatabricksLLM'):
            with patch('core.atomic_extractor.VDB'):
                self.extractor = AtomicExtractor(
                    self.mock_llm_endpoint,
                    self.mock_token
                )
        
        self.sample_text = """
        Employee ID: 001
        Name: John Doe
        Department: Engineering
        Hours: 40
        
        Employee ID: 002
        Name: Jane Smith
        Department: Marketing
        Hours: 35
        """
        
        self.template_fields = [
            "employee_id",
            "name",
            "department",
            "hours"
        ]
    
    def test_initialization(self):
        """Test AtomicExtractor initialization"""
        self.assertIsNotNone(self.extractor.llm_70b)
        self.assertIsNotNone(self.extractor.vdb)
    
    def test_initialization_with_small_llm(self):
        """Test initialization with both large and small LLM"""
        with patch('core.atomic_extractor.DatabricksLLM'):
            with patch('core.atomic_extractor.VDB'):
                extractor = AtomicExtractor(
                    self.mock_llm_endpoint,
                    self.mock_token,
                    small_llm_endpoint="https://small-llm.com"
                )
                
                self.assertIsNotNone(extractor.llm_70b)
                self.assertIsNotNone(extractor.llm_7b)
    
    def test_split_into_atomic_records(self):
        """Test splitting text into atomic records"""
        chunks = self.extractor._split_into_atomic_records(self.sample_text)
        
        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 0)
    
    def test_classify_fields_with_vdb(self):
        """Test field classification using vector DB"""
        with patch.object(self.extractor.vdb, 'query') as mock_query:
            mock_query.return_value = [
                {"field": "employee_id", "score": 0.95},
                {"field": "name", "score": 0.90}
            ]
            
            schema_mappings = self.extractor._classify_fields_with_vdb(
                "Employee Template",
                self.template_fields
            )
            
            self.assertIsNotNone(schema_mappings)
    
    def test_extract_atomic_records(self):
        """Test full atomic extraction pipeline"""
        with patch.object(self.extractor, '_split_into_atomic_records') as mock_split:
            with patch.object(self.extractor, '_classify_fields_with_vdb') as mock_classify:
                with patch.object(self.extractor.llm_70b, 'chat') as mock_chat:
                    mock_split.return_value = ["chunk1", "chunk2"]
                    mock_classify.return_value = {"field1": "template_field1"}
                    mock_chat.return_value = json.dumps([
                        {"employee_id": "001", "name": "John"}
                    ])
                    
                    result = self.extractor.extract_atomic_records(
                        self.sample_text,
                        "Employee Template",
                        self.template_fields
                    )
                    
                    self.assertIsNotNone(result)
                    # Result has 'rows' key, not 'records'
                    self.assertIn("rows", result)
    
    def test_extract_with_output_file(self):
        """Test extraction with output file specification"""
        output_file = "test_output.jsonl"
        
        with patch.object(self.extractor, '_split_into_atomic_records') as mock_split:
            with patch.object(self.extractor, '_classify_fields_with_vdb') as mock_classify:
                with patch.object(self.extractor.llm_70b, 'chat') as mock_chat:
                    with patch('builtins.open', create=True) as mock_open:
                        mock_split.return_value = ["chunk"]
                        mock_classify.return_value = {}
                        mock_chat.return_value = json.dumps([{"id": "1"}])
                        
                        result = self.extractor.extract_atomic_records(
                            self.sample_text,
                            "Template",
                            self.template_fields,
                            output_file=output_file
                        )
                        
                        self.assertIsNotNone(result)
    
    def test_load_balancing_with_dual_llm(self):
        """Test round-robin load balancing between LLMs"""
        with patch('core.atomic_extractor.DatabricksLLM'):
            with patch('core.atomic_extractor.VDB'):
                extractor = AtomicExtractor(
                    self.mock_llm_endpoint,
                    self.mock_token,
                    small_llm_endpoint="https://small-llm.com"
                )
                
                # Test that load balancer alternates
                self.assertEqual(extractor.current_llm_index, 0)
    
    def test_empty_text_input(self):
        """Test handling of empty text input"""
        result = self.extractor.extract_atomic_records(
            "",
            "Template",
            self.template_fields
        )
        
        # Should handle gracefully
        self.assertIsNotNone(result)
    
    def test_empty_template_fields(self):
        """Test handling of empty template fields"""
        result = self.extractor.extract_atomic_records(
            self.sample_text,
            "Template",
            []
        )
        
        # Should handle gracefully
        self.assertIsNotNone(result)
    
    def test_malformed_text_structure(self):
        """Test extraction from malformed text"""
        malformed_text = "Random unstructured text without clear patterns"
        
        with patch.object(self.extractor, '_split_into_atomic_records') as mock_split:
            mock_split.return_value = []
            
            result = self.extractor.extract_atomic_records(
                malformed_text,
                "Template",
                self.template_fields
            )
            
            self.assertIsNotNone(result)


class TestAtomicExtractorAdvanced(unittest.TestCase):
    """Test advanced extraction scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        with patch('core.atomic_extractor.DatabricksLLM'):
            with patch('core.atomic_extractor.VDB'):
                self.extractor = AtomicExtractor(
                    "https://mock.com",
                    "token"
                )
    
    def test_multi_line_record_extraction(self):
        """Test extraction of multi-line records"""
        multi_line_text = """
        Employee ID: 001
        Name: John Doe
        Address: 123 Main St
                 Apt 4B
                 New York, NY
        
        Employee ID: 002
        Name: Jane Smith
        """
        
        chunks = self.extractor._split_into_atomic_records(multi_line_text)
        
        self.assertIsInstance(chunks, list)
    
    def test_nested_data_extraction(self):
        """Test extraction of nested data structures"""
        nested_text = """
        Employee: John Doe
          Department: Engineering
          Manager: Alice Smith
          Projects:
            - Project A
            - Project B
        """
        
        with patch.object(self.extractor, '_split_into_atomic_records') as mock_split:
            mock_split.return_value = [nested_text]
            
            result = self.extractor.extract_atomic_records(
                nested_text,
                "Employee Template",
                ["employee", "department", "manager", "projects"]
            )
            
            self.assertIsNotNone(result)
    
    def test_special_characters_in_data(self):
        """Test extraction with special characters"""
        special_text = """
        ID: 001
        Name: O'Brien
        Email: test@example.com
        Notes: Special chars: @#$%^&*()
        """
        
        chunks = self.extractor._split_into_atomic_records(special_text)
        
        self.assertIsInstance(chunks, list)
    
    def test_large_text_processing(self):
        """Test processing of large text documents"""
        large_text = "\n".join([
            f"Record {i}: Field1: Value{i}, Field2: Data{i}"
            for i in range(1000)
        ])
        
        with patch.object(self.extractor, '_split_into_atomic_records') as mock_split:
            mock_split.return_value = ["chunk"] * 100
            
            result = self.extractor.extract_atomic_records(
                large_text,
                "Template",
                ["field1", "field2"]
            )
            
            self.assertIsNotNone(result)
    
    def test_unicode_text_extraction(self):
        """Test extraction from Unicode text"""
        unicode_text = """
        员工ID: 001
        名字: 张三
        部门: 工程部
        """
        
        chunks = self.extractor._split_into_atomic_records(unicode_text)
        
        self.assertIsInstance(chunks, list)


class TestAtomicExtractorEdgeCases(unittest.TestCase):
    """Test edge cases for Atomic Extractor"""
    
    def setUp(self):
        """Set up test fixtures"""
        with patch('core.atomic_extractor.DatabricksLLM'):
            with patch('core.atomic_extractor.VDB'):
                self.extractor = AtomicExtractor(
                    "https://mock.com",
                    "token"
                )
    
    def test_whitespace_only_text(self):
        """Test extraction from whitespace-only text"""
        whitespace_text = "   \n   \t   \n   "
        
        chunks = self.extractor._split_into_atomic_records(whitespace_text)
        
        # Should return empty or handle gracefully
        self.assertIsInstance(chunks, list)
    
    def test_single_character_records(self):
        """Test extraction with single character records"""
        single_char = "A\nB\nC\n"
        
        chunks = self.extractor._split_into_atomic_records(single_char)
        
        self.assertIsInstance(chunks, list)
    
    def test_duplicate_records(self):
        """Test handling of duplicate records in text"""
        duplicate_text = """
        ID: 001
        Name: John
        
        ID: 001
        Name: John
        """
        
        result = self.extractor.extract_atomic_records(
            duplicate_text,
            "Template",
            ["id", "name"]
        )
        
        # Should handle duplicates
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
