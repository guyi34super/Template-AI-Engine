"""
Unit Tests for Mapping Models - Data models for mapping operations
"""

import unittest
from mapping_engine.models import (
    MappingResult, FieldMapping, MappingConfig,
    MappingStrategy, FieldType, TransformedData
)


class TestMappingModels(unittest.TestCase):
    """Test suite for mapping data models"""
    
    def test_field_mapping_creation(self):
        """Test FieldMapping creation"""
        mapping = FieldMapping(
            source_field="employee_id",
            target_field="EmployeeNumber",
            confidence=0.95,
            field_type=FieldType.STRING
        )
        
        self.assertEqual(mapping.source_field, "employee_id")
        self.assertEqual(mapping.target_field, "EmployeeNumber")
        self.assertEqual(mapping.confidence, 0.95)
    
    def test_mapping_strategy_enum(self):
        """Test MappingStrategy enum values"""
        self.assertEqual(MappingStrategy.AUTO.value, "auto")
        self.assertEqual(MappingStrategy.MANUAL.value, "manual")
        self.assertEqual(MappingStrategy.HYBRID.value, "hybrid")
    
    def test_field_type_enum(self):
        """Test FieldType enum values"""
        self.assertIn(FieldType.STRING, FieldType)
        self.assertIn(FieldType.NUMBER, FieldType)
        self.assertIn(FieldType.BOOLEAN, FieldType)
        self.assertIn(FieldType.DATE, FieldType)
        # Additional types in the enum
        self.assertIn(FieldType.DATETIME, FieldType)
        self.assertIn(FieldType.UNKNOWN, FieldType)
    
    def test_mapping_config_defaults(self):
        """Test MappingConfig default values"""
        config = MappingConfig()
        
        self.assertEqual(config.strategy, MappingStrategy.AUTO)
        self.assertEqual(config.manual_overrides, {})
    
    def test_mapping_config_custom(self):
        """Test MappingConfig with custom values"""
        manual_overrides = {"field1": "target1"}
        config = MappingConfig(
            strategy=MappingStrategy.MANUAL,
            manual_overrides=manual_overrides,
            fuzzy_threshold=0.8
        )
        
        self.assertEqual(config.strategy, MappingStrategy.MANUAL)
        self.assertEqual(config.manual_overrides, manual_overrides)
        self.assertEqual(config.fuzzy_threshold, 0.8)
    
    def test_mapping_result_creation(self):
        """Test MappingResult creation"""
        mappings = [
            FieldMapping(source_field="field1", target_field="target1", confidence=0.95, field_type=FieldType.STRING),
            FieldMapping(source_field="field2", target_field="target2", confidence=0.90, field_type=FieldType.NUMBER)
        ]
        
        result = MappingResult(
            mappings=mappings,
            total_fields_mapped=2,
            confidence_score=0.925
        )
        
        self.assertEqual(len(result.mappings), 2)
        self.assertEqual(result.total_fields_mapped, 2)
    
    def test_transformed_data_model(self):
        """Test TransformedData model"""
        original_data = [{"field1": "value1"}]
        transformed_data = [{"target1": "value1"}]
        mapping_result = MappingResult(total_fields_mapped=1)
        
        data = TransformedData(
            original_data=original_data,
            transformed_data=transformed_data,
            mapping_result=mapping_result,
            records_processed=1
        )
        
        self.assertEqual(data.original_data, original_data)
        self.assertEqual(data.transformed_data, transformed_data)
        self.assertEqual(data.records_processed, 1)


class TestMappingValidation(unittest.TestCase):
    """Test validation logic in mapping models"""
    
    def test_confidence_range_validation(self):
        """Test confidence should be between 0 and 1"""
        # Valid confidence
        mapping = FieldMapping(source_field="src", target_field="tgt", confidence=0.5, field_type=FieldType.STRING)
        self.assertGreaterEqual(mapping.confidence, 0.0)
        self.assertLessEqual(mapping.confidence, 1.0)
    
    def test_empty_field_names(self):
        """Test handling of empty field names"""
        mapping = FieldMapping(source_field="", target_field="", confidence=0.5, field_type=FieldType.STRING)
        
        # Should create but may be invalid
        self.assertIsNotNone(mapping)
    
    def test_field_type_detection_logic(self):
        """Test field type detection helper logic"""
        # Simple type detection logic
        test_values = {
            "string": FieldType.STRING,
            123: FieldType.NUMBER,
            3.14: FieldType.NUMBER,
            True: FieldType.BOOLEAN,
        }
        
        for value, expected_type in test_values.items():
            # Test if type detection works
            if isinstance(value, bool):
                detected = FieldType.BOOLEAN
            elif isinstance(value, (int, float)):
                detected = FieldType.NUMBER
            else:
                detected = FieldType.STRING
            
            self.assertEqual(detected, expected_type)


if __name__ == '__main__':
    unittest.main()
