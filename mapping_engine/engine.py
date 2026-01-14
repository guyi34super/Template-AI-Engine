"""
Mapping Engine - Intelligent JSON field mapping
"""

import json
import time
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from datetime import datetime
import re

from .models import (
    MappingResult, FieldMapping, MappingConfig, TransformedData,
    MappingStrategy, FieldType
)
from .prompts import AutoMappingPrompt, ManualMappingPrompt


class MappingEngine:
    """
    Intelligent field mapping engine that maps source JSON to target schema
    
    Features:
    - LLM-based intelligent mapping
    - Manual mapping overrides
    - Field type detection
    - Data transformation
    - Fuzzy field matching
    """
    
    def __init__(self, llm=None):
        """
        Initialize Mapping Engine
        
        Args:
            llm: LLM instance for intelligent mapping
        """
        self.llm = llm
        self.auto_prompt = AutoMappingPrompt()
        self.manual_prompt = ManualMappingPrompt()
    
    def map_json_fields(
        self,
        source_json: Union[Dict, List[Dict], str, Path],
        target_schema: Union[Dict, List[str], str, Path],
        config: Optional[MappingConfig] = None
    ) -> MappingResult:
        """
        Map fields from source JSON to target schema
        
        Args:
            source_json: Source JSON data (dict, list of dicts, file path, or JSON string)
            target_schema: Target schema (dict with field names, list of field names, or file path)
            config: Mapping configuration
            
        Returns:
            MappingResult with field mappings
        """
        start_time = time.time()
        config = config or MappingConfig()
        
        try:
            # Parse inputs
            source_fields, source_context = self._extract_source_fields(source_json)
            target_fields, target_context = self._extract_target_fields(target_schema)
            
            # Apply ignore filters
            source_fields = [f for f in source_fields if f not in config.ignore_fields]
            
            # Determine mapping strategy
            if config.strategy == MappingStrategy.MANUAL:
                mappings = self._apply_manual_mappings(
                    source_fields, target_fields, config.manual_overrides
                )
            elif config.strategy == MappingStrategy.AUTO:
                mappings = self._apply_auto_mappings(
                    source_fields, target_fields, source_context, target_context
                )
            else:  # HYBRID
                mappings = self._apply_hybrid_mappings(
                    source_fields, target_fields, config.manual_overrides,
                    source_context, target_context
                )
            
            # Build result
            result = self._build_mapping_result(
                mappings, source_fields, target_fields, config, start_time
            )
            
            return result
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            return MappingResult(
                error=str(e),
                processing_time_ms=processing_time,
                strategy_used=config.strategy
            )
    
    def transform_data(
        self,
        source_data: Union[List[Dict], str, Path],
        mapping_result: MappingResult,
        fill_unmapped: bool = False
    ) -> TransformedData:
        """
        Transform source data using mapping result
        
        Args:
            source_data: Source data to transform
            mapping_result: Mapping result from map_json_fields
            fill_unmapped: Whether to include unmapped fields in output
            
        Returns:
            TransformedData with transformed records
        """
        # Load source data
        if isinstance(source_data, (str, Path)):
            with open(source_data, 'r', encoding='utf-8') as f:
                source_data = json.load(f)
        
        if not isinstance(source_data, list):
            source_data = [source_data]
        
        transformed_records = []
        errors = []
        failed_count = 0
        
        # Build mapping dictionary
        mapping_dict = {m.source_field: m.target_field for m in mapping_result.mappings}
        
        # Transform each record
        for idx, record in enumerate(source_data):
            try:
                transformed_record = {}
                
                for source_field, value in record.items():
                    if source_field in mapping_dict:
                        target_field = mapping_dict[source_field]
                        transformed_record[target_field] = value
                    elif fill_unmapped:
                        transformed_record[source_field] = value
                
                transformed_records.append(transformed_record)
                
            except Exception as e:
                failed_count += 1
                errors.append(f"Record {idx}: {str(e)}")
        
        return TransformedData(
            original_data=source_data,
            transformed_data=transformed_records,
            mapping_result=mapping_result,
            records_processed=len(source_data) - failed_count,
            records_failed=failed_count,
            transformation_errors=errors
        )
    
    def _extract_source_fields(
        self, source: Union[Dict, List[Dict], str, Path]
    ) -> tuple[List[str], Dict[str, str]]:
        """Extract field names and sample values from source"""
        # Load from file if path
        if isinstance(source, (str, Path)):
            with open(source, 'r', encoding='utf-8') as f:
                source = json.load(f)
        
        # Get first record if list
        if isinstance(source, list):
            if not source:
                return [], {}
            sample_record = source[0]
        else:
            sample_record = source
        
        # Extract fields and sample values
        fields = list(sample_record.keys())
        context = {
            field: self._get_sample_value_context(sample_record[field])
            for field in fields
        }
        
        return fields, context
    
    def _extract_target_fields(
        self, target: Union[Dict, List[str], str, Path]
    ) -> tuple[List[str], Dict[str, str]]:
        """Extract field names and descriptions from target schema"""
        # Load from file if path
        if isinstance(target, (str, Path)):
            with open(target, 'r', encoding='utf-8') as f:
                target = json.load(f)
        
        # Handle different target formats
        if isinstance(target, list):
            # Simple list of field names
            return target, {}
        elif isinstance(target, dict):
            # Dict with field descriptions or sample record
            fields = list(target.keys())
            context = {
                field: self._get_field_description(field, target[field])
                for field in fields
            }
            return fields, context
        
        return [], {}
    
    def _apply_manual_mappings(
        self,
        source_fields: List[str],
        target_fields: List[str],
        manual_overrides: Dict[str, str]
    ) -> List[FieldMapping]:
        """Apply manual mappings"""
        mappings = []
        
        for source_field, target_field in manual_overrides.items():
            if source_field in source_fields and target_field in target_fields:
                mappings.append(FieldMapping(
                    source_field=source_field,
                    target_field=target_field,
                    confidence=1.0,
                    notes="Manual mapping"
                ))
        
        return mappings
    
    def _apply_auto_mappings(
        self,
        source_fields: List[str],
        target_fields: List[str],
        source_context: Dict[str, str],
        target_context: Dict[str, str]
    ) -> List[FieldMapping]:
        """Apply LLM-based intelligent mappings"""
        if not self.llm:
            # Fallback to fuzzy matching
            return self._apply_fuzzy_mappings(source_fields, target_fields)
        
        # Build prompt
        prompt = self.auto_prompt.build_prompt(
            schema_fields=target_fields,
            extracted_fields=source_fields,
            schema_context=target_context,
            extracted_context=source_context
        )
        
        # Get LLM response
        try:
            response = self.llm.invoke(prompt)
            mapping_dict = self.auto_prompt.parse_llm_response(response)
            
            # Convert to FieldMapping objects
            mappings = []
            for source_field, target_field in mapping_dict.items():
                if source_field in source_fields and target_field in target_fields:
                    mappings.append(FieldMapping(
                        source_field=source_field,
                        target_field=target_field,
                        confidence=0.9,  # High confidence from LLM
                        notes="LLM intelligent mapping"
                    ))
            
            return mappings
            
        except Exception as e:
            print(f"⚠️ LLM mapping failed: {e}, falling back to fuzzy matching")
            return self._apply_fuzzy_mappings(source_fields, target_fields)
    
    def _apply_hybrid_mappings(
        self,
        source_fields: List[str],
        target_fields: List[str],
        manual_overrides: Dict[str, str],
        source_context: Dict[str, str],
        target_context: Dict[str, str]
    ) -> List[FieldMapping]:
        """Apply hybrid: manual overrides + auto mappings"""
        # Start with manual mappings
        mappings = self._apply_manual_mappings(source_fields, target_fields, manual_overrides)
        mapped_sources = {m.source_field for m in mappings}
        
        # Apply auto mappings for unmapped fields
        remaining_sources = [f for f in source_fields if f not in mapped_sources]
        if remaining_sources:
            auto_mappings = self._apply_auto_mappings(
                remaining_sources, target_fields, source_context, target_context
            )
            mappings.extend(auto_mappings)
        
        return mappings
    
    def _apply_fuzzy_mappings(
        self, source_fields: List[str], target_fields: List[str]
    ) -> List[FieldMapping]:
        """Apply fuzzy string matching as fallback"""
        mappings = []
        
        for source_field in source_fields:
            best_match = None
            best_score = 0.0
            
            source_normalized = self._normalize_field_name(source_field)
            
            for target_field in target_fields:
                target_normalized = self._normalize_field_name(target_field)
                score = self._fuzzy_match_score(source_normalized, target_normalized)
                
                if score > best_score and score >= 0.7:  # Threshold
                    best_score = score
                    best_match = target_field
            
            if best_match:
                mappings.append(FieldMapping(
                    source_field=source_field,
                    target_field=best_match,
                    confidence=best_score,
                    notes="Fuzzy matching"
                ))
        
        return mappings
    
    def _normalize_field_name(self, field: str) -> str:
        """Normalize field name for comparison"""
        # Remove underscores, lowercase
        normalized = field.replace("_", "").replace("-", "").lower()
        # Handle camelCase -> lowercase
        normalized = re.sub(r'([A-Z])', r'\1', normalized).lower()
        return normalized
    
    def _fuzzy_match_score(self, str1: str, str2: str) -> float:
        """Calculate fuzzy match score between two strings"""
        # Simple Levenshtein-based similarity
        if str1 == str2:
            return 1.0
        
        # Check if one contains the other
        if str1 in str2 or str2 in str1:
            return 0.85
        
        # Check common prefixes/suffixes
        common_prefix = len(self._common_prefix(str1, str2))
        common_suffix = len(self._common_suffix(str1, str2))
        max_len = max(len(str1), len(str2))
        
        if max_len == 0:
            return 0.0
        
        return (common_prefix + common_suffix) / max_len
    
    def _common_prefix(self, str1: str, str2: str) -> str:
        """Find common prefix"""
        prefix = []
        for c1, c2 in zip(str1, str2):
            if c1 == c2:
                prefix.append(c1)
            else:
                break
        return ''.join(prefix)
    
    def _common_suffix(self, str1: str, str2: str) -> str:
        """Find common suffix"""
        return self._common_prefix(str1[::-1], str2[::-1])[::-1]
    
    def _get_sample_value_context(self, value: Any) -> str:
        """Get context from sample value"""
        if isinstance(value, str):
            if len(value) > 50:
                return f"string (sample: {value[:50]}...)"
            return f"string (sample: {value})"
        elif isinstance(value, (int, float)):
            return f"number (sample: {value})"
        elif isinstance(value, bool):
            return f"boolean (sample: {value})"
        elif isinstance(value, list):
            return f"array (length: {len(value)})"
        elif isinstance(value, dict):
            return f"object (keys: {', '.join(list(value.keys())[:3])})"
        return str(type(value).__name__)
    
    def _get_field_description(self, field: str, value: Any) -> str:
        """Get field description from schema"""
        if isinstance(value, str):
            return value  # Description provided
        return self._get_sample_value_context(value)
    
    def _build_mapping_result(
        self,
        mappings: List[FieldMapping],
        source_fields: List[str],
        target_fields: List[str],
        config: MappingConfig,
        start_time: float
    ) -> MappingResult:
        """Build final mapping result"""
        mapped_sources = {m.source_field for m in mappings}
        mapped_targets = {m.target_field for m in mappings}
        
        unmapped_sources = [f for f in source_fields if f not in mapped_sources]
        unmapped_targets = [f for f in target_fields if f not in mapped_targets]
        
        # Calculate average confidence
        avg_confidence = (
            sum(m.confidence for m in mappings) / len(mappings)
            if mappings else 0.0
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return MappingResult(
            mappings=mappings,
            unmapped_source_fields=unmapped_sources,
            unmapped_target_fields=unmapped_targets,
            total_fields_mapped=len(mappings),
            confidence_score=avg_confidence,
            strategy_used=config.strategy,
            processing_time_ms=processing_time,
            created_at=datetime.utcnow()
        )
