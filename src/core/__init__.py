"""
Core data models and constants
"""

from .models import (
    ImageInfo,
    StructuredDescription,
    DiagramXML,
    ProcessingResult,
    PaperMetadata
)
from .constants import (
    SUPPORTED_IMAGE_FORMATS,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_MAX_TOKENS
)

__all__ = [
    'ImageInfo',
    'StructuredDescription',
    'DiagramXML',
    'ProcessingResult',
    'PaperMetadata',
    'SUPPORTED_IMAGE_FORMATS',
    'DEFAULT_LLM_TEMPERATURE',
    'DEFAULT_MAX_TOKENS'
]
