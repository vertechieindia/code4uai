"""Context builder for autocomplete requests."""

from __future__ import annotations
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .models import (
    CompletionRequest,
    InlineCompletionRequest,
    AutocompleteContext,
    ContextFile,
)


class ContextBuilder:
    """Builds rich context for autocomplete from code and Knowledge Graph."""
    
    # Language-specific patterns
    IMPORT_PATTERNS = {
        "python": [
            r"^import\s+([\w.]+)",
            r"^from\s+([\w.]+)\s+import",
        ],
        "typescript": [
            r"import\s+.*\s+from\s+['\"](.+?)['\"]",
            r"import\s+['\"](.+?)['\"]",
        ],
        "javascript": [
            r"import\s+.*\s+from\s+['\"](.+?)['\"]",
            r"require\(['\"](.+?)['\"]\)",
        ],
        "java": [
            r"import\s+([\w.]+);",
        ],
        "kotlin": [
            r"import\s+([\w.]+)",
        ],
    }
    
    def __init__(self, knowledge_graph=None):
        """Initialize context builder.
        
        Args:
            knowledge_graph: Optional Knowledge Graph client for enhanced context
        """
        self.knowledge_graph = knowledge_graph
    
    def build_context(
        self, 
        request: CompletionRequest | InlineCompletionRequest
    ) -> AutocompleteContext:
        """Build comprehensive context for autocomplete.
        
        Args:
            request: The completion request
            
        Returns:
            AutocompleteContext with all gathered information
        """
        content = request.content
        cursor_line = request.cursor_line
        cursor_column = request.cursor_column
        language = request.language
        
        # Split content into lines
        lines = content.split("\n")
        current_line = lines[cursor_line] if cursor_line < len(lines) else ""
        
        # Get prefix (text before cursor) and suffix (text after cursor)
        prefix_lines = lines[:cursor_line]
        prefix_lines.append(current_line[:cursor_column])
        prefix = "\n".join(prefix_lines)
        
        suffix_lines = [current_line[cursor_column:]]
        suffix_lines.extend(lines[cursor_line + 1:])
        suffix = "\n".join(suffix_lines)
        
        # Extract imports
        imports = self._extract_imports(content, language)
        
        # Extract symbols in scope
        symbols = self._extract_symbols(content, language)
        
        # Get related files from context
        related_files = []
        if hasattr(request, 'context_files'):
            related_files = [cf.path for cf in request.context_files]
        
        # Build context
        context = AutocompleteContext(
            current_file=request.file_path,
            current_language=language,
            prefix=prefix,
            suffix=suffix,
            current_line=current_line,
            symbols_in_scope=symbols,
            imports=imports,
            related_files=related_files,
        )
        
        # Enhance with Knowledge Graph if available
        if self.knowledge_graph:
            self._enhance_with_knowledge_graph(context, request.file_path)
        
        return context
    
    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements from code.
        
        Args:
            content: Source code
            language: Programming language
            
        Returns:
            List of imported module/package names
        """
        imports = []
        patterns = self.IMPORT_PATTERNS.get(language, [])
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            imports.extend(matches)
        
        return list(set(imports))
    
    def _extract_symbols(self, content: str, language: str) -> List[str]:
        """Extract symbol definitions from code.
        
        Args:
            content: Source code
            language: Programming language
            
        Returns:
            List of defined symbols
        """
        symbols = []
        
        # Common patterns for different languages
        patterns = {
            "python": [
                r"def\s+(\w+)\s*\(",
                r"class\s+(\w+)",
                r"(\w+)\s*=",
            ],
            "typescript": [
                r"function\s+(\w+)",
                r"const\s+(\w+)",
                r"let\s+(\w+)",
                r"class\s+(\w+)",
                r"interface\s+(\w+)",
                r"type\s+(\w+)",
            ],
            "javascript": [
                r"function\s+(\w+)",
                r"const\s+(\w+)",
                r"let\s+(\w+)",
                r"var\s+(\w+)",
                r"class\s+(\w+)",
            ],
            "java": [
                r"class\s+(\w+)",
                r"interface\s+(\w+)",
                r"(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(",
            ],
            "kotlin": [
                r"fun\s+(\w+)",
                r"val\s+(\w+)",
                r"var\s+(\w+)",
                r"class\s+(\w+)",
                r"interface\s+(\w+)",
            ],
        }
        
        lang_patterns = patterns.get(language, [])
        for pattern in lang_patterns:
            matches = re.findall(pattern, content)
            symbols.extend(matches)
        
        return list(set(symbols))
    
    def _enhance_with_knowledge_graph(
        self, 
        context: AutocompleteContext,
        file_path: str
    ) -> None:
        """Enhance context with Knowledge Graph data.
        
        Args:
            context: The context to enhance
            file_path: Current file path
        """
        # Query Knowledge Graph for related functions and types
        # This would connect to your Knowledge Graph service
        try:
            # Example: Get functions that are commonly called from this file
            # related = self.knowledge_graph.get_related_symbols(file_path)
            # context.relevant_functions = related.get("functions", [])
            # context.relevant_types = related.get("types", [])
            pass
        except Exception:
            # Gracefully handle KG unavailability
            pass
    
    def get_trigger_context(
        self,
        content: str,
        cursor_line: int,
        cursor_column: int
    ) -> Tuple[str, str]:
        """Get the trigger character and word being typed.
        
        Args:
            content: Source code
            cursor_line: Current line number
            cursor_column: Current column
            
        Returns:
            Tuple of (trigger_char, current_word)
        """
        lines = content.split("\n")
        if cursor_line >= len(lines):
            return "", ""
        
        line = lines[cursor_line]
        prefix = line[:cursor_column]
        
        # Find trigger character
        trigger = ""
        if prefix and prefix[-1] in ".([{:,= ":
            trigger = prefix[-1]
        
        # Find current word being typed
        word_match = re.search(r"(\w+)$", prefix)
        current_word = word_match.group(1) if word_match else ""
        
        return trigger, current_word

