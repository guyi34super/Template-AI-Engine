"""
Mapping Engine - Intelligent field mapping between JSON structures
"""

from .engine import MappingEngine
from .models import MappingResult, FieldMapping, MappingConfig
from .prompts import AutoMappingPrompt

__all__ = [
    'MappingEngine',
    'MappingResult',
    'FieldMapping',
    'MappingConfig',
    'AutoMappingPrompt'
]
