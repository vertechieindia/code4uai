"""Main autocomplete engine."""

from __future__ import annotations
import time
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .models import (
    CompletionRequest,
    CompletionResponse,
    Completion,
    CompletionType,
    InlineCompletionRequest,
    InlineCompletionResponse,
    TabToJumpSuggestion,
    TabToImportSuggestion,
)
from .context import ContextBuilder
from .cache import CompletionCache, TenantCache


class AutocompleteEngine:
    """
    Main autocomplete engine for code4u.ai.
    
    Provides:
    - Traditional completions (popup)
    - Inline completions (ghost text, Tab to accept)
    - Tab-to-Jump suggestions
    - Tab-to-Import suggestions
    """
    
    def __init__(
        self,
        llm_client=None,
        knowledge_graph=None,
        cache: Optional[TenantCache] = None,
    ):
        """Initialize the autocomplete engine.
        
        Args:
            llm_client: LLM client for generating completions
            knowledge_graph: Knowledge Graph client for context
            cache: Tenant-aware completion cache
        """
        self.llm_client = llm_client
        self.context_builder = ContextBuilder(knowledge_graph)
        self.cache = cache or TenantCache()
        
        # Language-specific completion providers
        self._language_providers: Dict[str, Any] = {}
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completions for a request.
        
        Args:
            request: The completion request
            
        Returns:
            CompletionResponse with suggestions
        """
        start_time = time.time()
        
        # Check cache
        tenant_cache = self.cache.get_cache(request.tenant_id)
        content_hash = CompletionCache.hash_content(request.content)
        cache_key = CompletionCache.make_key(
            request.file_path,
            request.cursor_line,
            request.cursor_column,
            content_hash,
        )
        
        cached = tenant_cache.get(cache_key)
        if cached:
            return CompletionResponse(
                completions=cached,
                cache_hit=True,
                latency_ms=(time.time() - start_time) * 1000,
            )
        
        # Build context
        context = self.context_builder.build_context(request)
        
        # Get trigger information
        trigger, current_word = self.context_builder.get_trigger_context(
            request.content,
            request.cursor_line,
            request.cursor_column,
        )
        
        completions: List[Completion] = []
        
        # Add local symbol completions
        completions.extend(
            self._get_local_completions(context, current_word)
        )
        
        # Add import-based completions
        completions.extend(
            self._get_import_completions(context, current_word)
        )
        
        # Add LLM-powered completions if available
        if self.llm_client:
            llm_completions = await self._get_llm_completions(
                context, current_word, request.max_completions
            )
            completions.extend(llm_completions)
        
        # Sort by score and limit
        completions.sort(key=lambda c: c.score, reverse=True)
        completions = completions[:request.max_completions]
        
        # Cache results
        tenant_cache.set(cache_key, completions)
        
        return CompletionResponse(
            completions=completions,
            cache_hit=False,
            latency_ms=(time.time() - start_time) * 1000,
        )
    
    async def inline_complete(
        self, 
        request: InlineCompletionRequest
    ) -> InlineCompletionResponse:
        """Generate inline (Tab) completion.
        
        Args:
            request: The inline completion request
            
        Returns:
            InlineCompletionResponse with suggestion
        """
        start_time = time.time()
        
        if not self.llm_client:
            return InlineCompletionResponse(suggestion=None)
        
        # Build context
        context = self.context_builder.build_context(request)
        
        # Build prompt for inline completion
        prompt = self._build_inline_prompt(context, request)
        
        try:
            # Generate completion using LLM
            response = await self.llm_client.generate(
                prompt=prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stop=["\n\n", "```", "def ", "class ", "function "],
            )
            
            suggestion = self._post_process_inline(
                response.text, 
                context.current_line,
                context.suffix,
            )
            
            return InlineCompletionResponse(
                suggestion=suggestion,
                multi_line="\n" in suggestion if suggestion else False,
                confidence=response.confidence if hasattr(response, 'confidence') else 0.8,
                latency_ms=(time.time() - start_time) * 1000,
                stop_reason=response.stop_reason if hasattr(response, 'stop_reason') else None,
            )
        except Exception as e:
            return InlineCompletionResponse(
                suggestion=None,
                latency_ms=(time.time() - start_time) * 1000,
            )
    
    async def suggest_jump(
        self,
        file_path: str,
        content: str,
        cursor_line: int,
        cursor_column: int,
        language: str,
    ) -> Optional[TabToJumpSuggestion]:
        """Suggest next edit location (Tab-to-Jump).
        
        Args:
            file_path: Current file
            content: File content
            cursor_line: Current line
            cursor_column: Current column
            language: Programming language
            
        Returns:
            Jump suggestion or None
        """
        # Analyze code structure to find likely next edit location
        lines = content.split("\n")
        
        # Common patterns for next edit locations
        patterns = [
            # After function signature, suggest body
            (r"def\s+\w+\([^)]*\):\s*$", 1, 4),
            # After class definition, suggest method
            (r"class\s+\w+.*:\s*$", 1, 4),
            # After if/for/while, suggest body
            (r"(if|for|while)\s+.*:\s*$", 1, 4),
            # After opening brace, suggest content
            (r"{\s*$", 1, 2),
        ]
        
        import re
        current_line_text = lines[cursor_line] if cursor_line < len(lines) else ""
        
        for pattern, line_offset, col_offset in patterns:
            if re.search(pattern, current_line_text):
                target_line = cursor_line + line_offset
                if target_line < len(lines):
                    return TabToJumpSuggestion(
                        file_path=file_path,
                        line=target_line,
                        column=col_offset,
                        preview=lines[target_line][:50] if target_line < len(lines) else "",
                        confidence=0.85,
                        reason="After block start",
                    )
        
        return None
    
    async def suggest_import(
        self,
        file_path: str,
        content: str,
        cursor_line: int,
        cursor_column: int,
        language: str,
        symbol: str,
    ) -> Optional[TabToImportSuggestion]:
        """Suggest import for undefined symbol (Tab-to-Import).
        
        Args:
            file_path: Current file
            content: File content
            cursor_line: Current line
            cursor_column: Current column
            language: Programming language
            symbol: Symbol that might need importing
            
        Returns:
            Import suggestion or None
        """
        # Common imports database (would be enhanced by Knowledge Graph)
        common_imports = {
            "python": {
                "List": "from typing import List",
                "Dict": "from typing import Dict",
                "Optional": "from typing import Optional",
                "dataclass": "from dataclasses import dataclass",
                "datetime": "from datetime import datetime",
                "Path": "from pathlib import Path",
                "json": "import json",
                "os": "import os",
                "re": "import re",
                "asyncio": "import asyncio",
            },
            "typescript": {
                "useState": "import { useState } from 'react'",
                "useEffect": "import { useEffect } from 'react'",
                "Component": "import { Component } from 'react'",
                "Observable": "import { Observable } from 'rxjs'",
            },
            "javascript": {
                "useState": "import { useState } from 'react'",
                "useEffect": "import { useEffect } from 'react'",
            },
        }
        
        lang_imports = common_imports.get(language, {})
        if symbol in lang_imports:
            import_stmt = lang_imports[symbol]
            
            # Check if already imported
            if import_stmt in content or f"import {symbol}" in content:
                return None
            
            return TabToImportSuggestion(
                import_statement=import_stmt,
                symbol=symbol,
                source_module=import_stmt.split("from ")[-1].split(" import")[0] if "from" in import_stmt else symbol,
                confidence=0.95,
            )
        
        return None
    
    def _get_local_completions(
        self, 
        context: 'AutocompleteContext',
        current_word: str,
    ) -> List[Completion]:
        """Get completions from local symbols.
        
        Args:
            context: Autocomplete context
            current_word: Word being typed
            
        Returns:
            List of completions
        """
        completions = []
        
        for symbol in context.symbols_in_scope:
            if current_word and not symbol.lower().startswith(current_word.lower()):
                continue
            
            completions.append(Completion(
                text=symbol,
                display_text=symbol,
                type=CompletionType.VARIABLE,
                score=0.8,
                detail="Local symbol",
            ))
        
        return completions
    
    def _get_import_completions(
        self,
        context: 'AutocompleteContext',
        current_word: str,
    ) -> List[Completion]:
        """Get completions from imported modules.
        
        Args:
            context: Autocomplete context
            current_word: Word being typed
            
        Returns:
            List of completions
        """
        completions = []
        
        for imp in context.imports:
            module_name = imp.split(".")[-1]
            if current_word and not module_name.lower().startswith(current_word.lower()):
                continue
            
            completions.append(Completion(
                text=module_name,
                display_text=module_name,
                type=CompletionType.MODULE,
                score=0.7,
                detail=f"from {imp}",
            ))
        
        return completions
    
    async def _get_llm_completions(
        self,
        context: 'AutocompleteContext',
        current_word: str,
        max_completions: int,
    ) -> List[Completion]:
        """Get LLM-powered completions.
        
        Args:
            context: Autocomplete context
            current_word: Word being typed
            max_completions: Maximum completions to return
            
        Returns:
            List of completions
        """
        # Build prompt for LLM
        prompt = f"""Complete the following {context.current_language} code.
Current line: {context.current_line}
Word being typed: {current_word}

Provide up to {max_completions} completions as a JSON array of strings.
Only return the completion text, not the full line.
"""
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                max_tokens=200,
                temperature=0.3,
            )
            
            # Parse completions from response
            import json
            suggestions = json.loads(response.text)
            
            return [
                Completion(
                    text=s,
                    display_text=s,
                    type=CompletionType.TEXT,
                    score=0.9 - (i * 0.05),
                )
                for i, s in enumerate(suggestions[:max_completions])
            ]
        except Exception:
            return []
    
    def _build_inline_prompt(
        self,
        context: 'AutocompleteContext',
        request: InlineCompletionRequest,
    ) -> str:
        """Build prompt for inline completion.
        
        Args:
            context: Autocomplete context
            request: Inline completion request
            
        Returns:
            Prompt string
        """
        return f"""<|fim_prefix|>{request.prefix}<|fim_suffix|>{request.suffix}<|fim_middle|>"""
    
    def _post_process_inline(
        self,
        suggestion: str,
        current_line: str,
        suffix: str,
    ) -> Optional[str]:
        """Post-process inline completion suggestion.
        
        Args:
            suggestion: Raw suggestion from LLM
            current_line: Current line text
            suffix: Text after cursor
            
        Returns:
            Cleaned suggestion or None
        """
        if not suggestion:
            return None
        
        # Remove leading/trailing whitespace
        suggestion = suggestion.strip()
        
        # Don't suggest if it duplicates suffix
        if suffix.strip().startswith(suggestion.strip()):
            return None
        
        # Limit length
        if len(suggestion) > 500:
            suggestion = suggestion[:500]
        
        return suggestion if suggestion else None

