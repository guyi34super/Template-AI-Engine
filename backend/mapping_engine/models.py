"""
Data models for Mapping Engine
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class MappingStrategy(str, Enum):
    """Mapping strategy types"""
    AUTO = "auto"  # LLM-based intelligent mapping
    MANUAL = "manual"  # User-provided mappings
    HYBRID = "hybrid"  # Combination of auto + manual overrides


class FieldType(str, Enum):
    """Field data types"""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    CURRENCY = "currency"
    EMAIL = "email"
    PHONE = "phone"
    ARRAY = "array"
    OBJECT = "object"
    UNKNOWN = "unknown"


class FieldMapping(BaseModel):
    """Represents a single field mapping"""
    source_field: str = Field(..., description="Field name from source JSON")
    target_field: str = Field(..., description="Field name from target schema")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Mapping confidence score")
    field_type: FieldType = Field(default=FieldType.UNKNOWN, description="Detected field type")
    transformation: Optional[str] = Field(None, description="Transformation function if needed")
    notes: Optional[str] = Field(None, description="Additional mapping notes")


class MappingConfig(BaseModel):
    """Configuration for mapping operation"""
    strategy: MappingStrategy = Field(default=MappingStrategy.AUTO)
    manual_overrides: Dict[str, str] = Field(default_factory=dict, description="Manual field mappings")
    ignore_fields: List[str] = Field(default_factory=list, description="Fields to ignore in source")
    required_fields: List[str] = Field(default_factory=list, description="Required target fields")
    allow_unmapped: bool = Field(default=True, description="Allow unmapped source fields")
    case_sensitive: bool = Field(default=False, description="Case-sensitive field matching")
    fuzzy_threshold: float = Field(default=0.85, ge=0.0, le=1.0, description="Fuzzy matching threshold")


class MappingResult(BaseModel):
    """Result of a mapping operation"""
    mappings: List[FieldMapping] = Field(default_factory=list)
    unmapped_source_fields: List[str] = Field(default_factory=list)
    unmapped_target_fields: List[str] = Field(default_factory=list)
    total_fields_mapped: int = Field(default=0)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    strategy_used: MappingStrategy = Field(default=MappingStrategy.AUTO)
    processing_time_ms: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    llm_response: Optional[str] = Field(None, description="Raw LLM response for debugging")
    error: Optional[str] = Field(None, description="Error message if mapping failed")


class TransformedData(BaseModel):
    """Result of applying mappings to transform data"""
    original_data: List[Dict[str, Any]] = Field(default_factory=list)
    transformed_data: List[Dict[str, Any]] = Field(default_factory=list)
    mapping_result: MappingResult
    records_processed: int = Field(default=0)
    records_failed: int = Field(default=0)
    transformation_errors: List[str] = Field(default_factory=list)
