"""Data models for autocomplete system."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class CompletionType(str, Enum):
    """Types of code completions."""
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    VARIABLE = "variable"
    PROPERTY = "property"
    INTERFACE = "interface"
    MODULE = "module"
    ENUM = "enum"
    SNIPPET = "snippet"
    KEYWORD = "keyword"
    TEXT = "text"


@dataclass
class ContextFile:
    """A file used as context for completions."""
    path: str
    content: str
    

@dataclass
class CompletionRequest:
    """Request for code completions."""
    file_path: str
    content: str
    cursor_line: int
    cursor_column: int
    language: str
    context_files: List[ContextFile] = field(default_factory=list)
    max_completions: int = 5
    include_documentation: bool = True
    tenant_id: str = "default"
    

@dataclass
class Completion:
    """A single completion suggestion."""
    text: str
    display_text: str
    type: CompletionType
    score: float
    documentation: Optional[str] = None
    insert_text: Optional[str] = None
    detail: Optional[str] = None
    sort_text: Optional[str] = None
    filter_text: Optional[str] = None
    preselect: bool = False
    

@dataclass
class CompletionResponse:
    """Response containing completions."""
    completions: List[Completion]
    cache_hit: bool = False
    latency_ms: float = 0.0
    model_version: str = "1.0.0"
    

@dataclass
class InlineCompletionRequest:
    """Request for inline (Tab) completions."""
    file_path: str
    content: str
    cursor_line: int
    cursor_column: int
    language: str
    prefix: str
    suffix: str
    max_tokens: int = 256
    temperature: float = 0.1
    tenant_id: str = "default"
    

@dataclass
class InlineCompletionResponse:
    """Response containing inline completion."""
    suggestion: Optional[str]
    multi_line: bool = False
    confidence: float = 0.0
    latency_ms: float = 0.0
    stop_reason: Optional[str] = None


@dataclass
class TabToJumpSuggestion:
    """Suggestion for Tab-to-Jump feature."""
    file_path: str
    line: int
    column: int
    preview: str
    confidence: float
    reason: str


@dataclass
class TabToImportSuggestion:
    """Suggestion for Tab-to-Import feature."""
    import_statement: str
    symbol: str
    source_module: str
    confidence: float


@dataclass 
class AutocompleteContext:
    """Context gathered for autocomplete."""
    # Current file context
    current_file: str
    current_language: str
    prefix: str
    suffix: str
    current_line: str
    
    # Symbol information
    symbols_in_scope: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    
    # Project context
    related_files: List[str] = field(default_factory=list)
    recent_edits: List[Dict[str, Any]] = field(default_factory=list)
    
    # Knowledge Graph context
    relevant_functions: List[Dict[str, Any]] = field(default_factory=list)
    relevant_types: List[Dict[str, Any]] = field(default_factory=list)
    
    # User patterns
    frequent_completions: List[str] = field(default_factory=list)

