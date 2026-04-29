"""
code4u.ai Autocomplete & Tab Completion Engine

Provides intelligent code completions powered by:
- Knowledge Graph context
- Language-specific models
- Multi-file understanding
- User patterns learning
"""

from .engine import AutocompleteEngine
from .models import (
    CompletionRequest,
    CompletionResponse,
    Completion,
    InlineCompletionRequest,
    InlineCompletionResponse,
    ContextFile,
)
from .context import ContextBuilder
from .cache import CompletionCache

__all__ = [
    "AutocompleteEngine",
    "CompletionRequest",
    "CompletionResponse",
    "Completion",
    "InlineCompletionRequest",
    "InlineCompletionResponse",
    "ContextBuilder",
    "CompletionCache",
    "ContextFile",
]

