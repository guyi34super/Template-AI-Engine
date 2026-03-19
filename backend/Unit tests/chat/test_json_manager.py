"""
Unit Tests for JSON Manager - JSON manipulation utilities
"""

import unittest
import tempfile
import json
import os
from unittest.mock import Mock, patch
from chat_engine.json_manager import JSONManager


class TestJSONManager(unittest.TestCase):
    """Test suite for JSONManager class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = JSONManager()
        self.test_data = {
            "name": "Test",
            "value": 123,
            "items": ["a", "b", "c"]
        }
        self.test_records = [
            {"id": 1, "name": "Alice", "score": 85},
            {"id": 2, "name": "Bob", "score": 92},
            {"id": 3, "name": "Charlie", "score": 78}
        ]
    
    def test_load_json(self):
        """Test loading JSON from file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.test_data, f)
            temp_path = f.name
        
        try:
            loaded = self.manager.load_json(temp_path)
            self.assertEqual(loaded, self.test_data)
        finally:
            os.unlink(temp_path)
    
    def test_save_json(self):
        """Test saving JSON to file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            self.manager.save_json(self.test_data, temp_path)
            
            # Verify saved content
            with open(temp_path, 'r') as f:
                loaded = json.load(f)
            
            self.assertEqual(loaded, self.test_data)
        finally:
            os.unlink(temp_path)
    
    def test_load_jsonl(self):
        """Test loading JSONL from file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for record in self.test_records:
                f.write(json.dumps(record) + '\n')
            temp_path = f.name
        
        try:
            loaded = self.manager.load_jsonl(temp_path)
            self.assertEqual(loaded, self.test_records)
        finally:
            os.unlink(temp_path)
    
    def test_save_jsonl(self):
        """Test saving JSONL to file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = f.name
        
        try:
            self.manager.save_jsonl(self.test_records, temp_path)
            
            # Verify saved content
            loaded = []
            with open(temp_path, 'r') as f:
                for line in f:
                    loaded.append(json.loads(line.strip()))
            
            self.assertEqual(loaded, self.test_records)
        finally:
            os.unlink(temp_path)
    
    def test_filter_by_query_equals(self):
        """Test filtering with equals operator"""
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps({
            "field": "name",
            "operator": "equals",
            "value": "Bob"
        })
        
        indices = self.manager.filter_by_query(self.test_records, "name equals Bob", mock_llm)
        
        self.assertEqual(len(indices), 1)
        self.assertEqual(self.test_records[indices[0]]['name'], "Bob")
    
    def test_filter_by_query_greater_than(self):
        """Test filtering with greater_than operator"""
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps({
            "field": "score",
            "operator": "greater_than",
            "value": "80"
        })
        
        indices = self.manager.filter_by_query(self.test_records, "score > 80", mock_llm)
        
        self.assertGreater(len(indices), 0)
        for idx in indices:
            self.assertGreater(self.test_records[idx]['score'], 80)
    
    def test_filter_by_query_contains(self):
        """Test filtering with contains operator"""
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps({
            "field": "name",
            "operator": "contains",
            "value": "li"
        })
        
        indices = self.manager.filter_by_query(self.test_records, "name contains li", mock_llm)
        
        self.assertGreater(len(indices), 0)
    
    def test_filter_by_query_all(self):
        """Test filtering with 'all' operator (no filter)"""
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps({
            "field": None,
            "operator": "all",
            "value": None
        })
        
        indices = self.manager.filter_by_query(self.test_records, "all records", mock_llm)
        
        self.assertEqual(len(indices), len(self.test_records))
    
    def test_filter_empty_records(self):
        """Test filtering on empty record list"""
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps({
            "field": "name",
            "operator": "equals",
            "value": "Test"
        })
        
        indices = self.manager.filter_by_query([], "test query", mock_llm)
        
        self.assertEqual(len(indices), 0)
    
    def test_filter_invalid_field(self):
        """Test filtering with non-existent field"""
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps({
            "field": "nonexistent_field",
            "operator": "equals",
            "value": "test"
        })
        
        indices = self.manager.filter_by_query(self.test_records, "test query", mock_llm)
        
        # Should handle gracefully, likely returning empty
        self.assertIsInstance(indices, list)
    
    def test_unicode_handling(self):
        """Test handling of Unicode characters"""
        unicode_data = {"name": "测试", "emoji": "🎉", "text": "Café"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            self.manager.save_json(unicode_data, temp_path)
            loaded = self.manager.load_json(temp_path)
            
            self.assertEqual(loaded, unicode_data)
        finally:
            os.unlink(temp_path)


class TestJSONManagerEdgeCases(unittest.TestCase):
    """Test edge cases for JSON Manager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = JSONManager()
    
    def test_empty_jsonl_file(self):
        """Test loading empty JSONL file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = f.name
        
        try:
            loaded = self.manager.load_jsonl(temp_path)
            self.assertEqual(loaded, [])
        finally:
            os.unlink(temp_path)
    
    def test_jsonl_with_blank_lines(self):
        """Test JSONL with blank lines"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"id": 1}\n')
            f.write('\n')
            f.write('{"id": 2}\n')
            f.write('  \n')
            f.write('{"id": 3}\n')
            temp_path = f.name
        
        try:
            loaded = self.manager.load_jsonl(temp_path)
            self.assertEqual(len(loaded), 3)
        finally:
            os.unlink(temp_path)
    
    def test_deeply_nested_json(self):
        """Test handling of deeply nested JSON"""
        nested = {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            self.manager.save_json(nested, temp_path)
            loaded = self.manager.load_json(temp_path)
            
            self.assertEqual(loaded, nested)
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()
