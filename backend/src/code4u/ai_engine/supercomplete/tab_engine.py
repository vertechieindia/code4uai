"""Tab Engine - Smart tab navigation and actions."""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class TabAction(str, Enum):
    """Actions triggered by Tab key."""
    ACCEPT = "accept"           # Accept current completion
    JUMP = "jump"               # Jump to next edit location
    EXPAND = "expand"           # Expand snippet
    IMPORT = "import"           # Add missing import
    CYCLE = "cycle"             # Cycle through completions
    INDENT = "indent"           # Normal indent (fallback)


@dataclass
class TabContext:
    """Context for tab action decision."""
    file_path: str
    cursor_line: int
    cursor_column: int
    
    # Current state
    has_completion: bool = False
    completion_text: Optional[str] = None
    
    # Placeholders
    in_placeholder: bool = False
    placeholder_index: int = 0
    total_placeholders: int = 0
    
    # Errors
    has_missing_import: bool = False
    missing_import: Optional[str] = None
    
    # Selection
    has_selection: bool = False


@dataclass
class TabResult:
    """Result of tab action."""
    action: TabAction
    
    # For ACCEPT
    text_to_insert: Optional[str] = None
    
    # For JUMP
    jump_to_line: Optional[int] = None
    jump_to_column: Optional[int] = None
    select_start: Optional[int] = None
    select_end: Optional[int] = None
    
    # For IMPORT
    import_text: Optional[str] = None
    import_line: int = 0
    
    # For CYCLE
    next_completion_index: int = 0


class TabEngine:
    """
    Smart Tab Key Engine.
    
    Handles:
    1. Accept completions on Tab
    2. Tab-to-jump between placeholders
    3. Tab-to-import for missing imports
    4. Tab-to-expand for snippets
    5. Intelligent fallback to indent
    """
    
    def __init__(self):
        """Initialize tab engine."""
        self._active_placeholders: Dict[str, List[Dict[str, Any]]] = {}
        self._completion_queue: Dict[str, List[Dict[str, Any]]] = {}
    
    def process_tab(self, context: TabContext) -> TabResult:
        """Process a tab key press.
        
        Args:
            context: Current editor context
            
        Returns:
            TabResult with action to perform
        """
        # Priority 1: Accept visible completion
        if context.has_completion and context.completion_text:
            return TabResult(
                action=TabAction.ACCEPT,
                text_to_insert=context.completion_text,
            )
        
        # Priority 2: Jump to next placeholder
        if context.in_placeholder and context.placeholder_index < context.total_placeholders:
            next_placeholder = self._get_next_placeholder(context.file_path, context.placeholder_index)
            if next_placeholder:
                return TabResult(
                    action=TabAction.JUMP,
                    jump_to_line=next_placeholder.get("line"),
                    jump_to_column=next_placeholder.get("column"),
                    select_start=next_placeholder.get("start"),
                    select_end=next_placeholder.get("end"),
                )
        
        # Priority 3: Add missing import
        if context.has_missing_import and context.missing_import:
            import_result = self._generate_import(context.missing_import)
            return TabResult(
                action=TabAction.IMPORT,
                import_text=import_result["text"],
                import_line=import_result["line"],
            )
        
        # Priority 4: Cycle completions if available
        if context.file_path in self._completion_queue:
            completions = self._completion_queue[context.file_path]
            if len(completions) > 1:
                return TabResult(
                    action=TabAction.CYCLE,
                    next_completion_index=1,
                )
        
        # Fallback: Normal indent
        return TabResult(action=TabAction.INDENT)
    
    def register_placeholders(
        self,
        file_path: str,
        placeholders: List[Dict[str, Any]],
    ) -> None:
        """Register placeholders for tab navigation.
        
        Args:
            file_path: File path
            placeholders: List of placeholder positions
        """
        self._active_placeholders[file_path] = placeholders
    
    def clear_placeholders(self, file_path: str) -> None:
        """Clear placeholders for a file."""
        self._active_placeholders.pop(file_path, None)
    
    def _get_next_placeholder(
        self,
        file_path: str,
        current_index: int,
    ) -> Optional[Dict[str, Any]]:
        """Get the next placeholder to jump to."""
        placeholders = self._active_placeholders.get(file_path, [])
        if current_index + 1 < len(placeholders):
            return placeholders[current_index + 1]
        return None
    
    def _generate_import(self, symbol: str) -> Dict[str, Any]:
        """Generate import statement for a symbol."""
        # Common Python imports
        common_imports = {
            "Optional": "from typing import Optional",
            "List": "from typing import List",
            "Dict": "from typing import Dict",
            "Any": "from typing import Any",
            "dataclass": "from dataclasses import dataclass",
            "field": "from dataclasses import field",
            "datetime": "from datetime import datetime",
            "Path": "from pathlib import Path",
            "Enum": "from enum import Enum",
            "asyncio": "import asyncio",
            "json": "import json",
            "re": "import re",
            "os": "import os",
        }
        
        if symbol in common_imports:
            return {"text": common_imports[symbol], "line": 0}
        
        return {"text": f"import {symbol}", "line": 0}
    
    def queue_completions(
        self,
        file_path: str,
        completions: List[Dict[str, Any]],
    ) -> None:
        """Queue completions for cycling."""
        self._completion_queue[file_path] = completions
    
    def clear_completion_queue(self, file_path: str) -> None:
        """Clear completion queue."""
        self._completion_queue.pop(file_path, None)


class TabToJump:
    """
    Tab-to-Jump: Predictive cursor navigation.
    
    Predicts where the developer will need to type next
    and allows jumping there with Tab.
    """
    
    def __init__(self):
        """Initialize tab-to-jump."""
        self._predictions: Dict[str, List[Dict[str, Any]]] = {}
    
    def predict_next_edits(
        self,
        file_path: str,
        content: str,
        cursor_line: int,
        cursor_column: int,
    ) -> List[Dict[str, Any]]:
        """Predict next edit locations.
        
        Args:
            file_path: File path
            content: File content
            cursor_line: Current line
            cursor_column: Current column
            
        Returns:
            List of predicted edit locations
        """
        predictions = []
        lines = content.split('\n')
        
        # Pattern: After function definition, predict docstring location
        if cursor_line < len(lines):
            current_line = lines[cursor_line]
            if current_line.strip().endswith(':') and 'def ' in current_line:
                predictions.append({
                    "line": cursor_line + 1,
                    "column": len(current_line) - len(current_line.lstrip()) + 4,
                    "reason": "docstring",
                    "suggestion": '"""',
                })
        
        # Pattern: After class definition, predict __init__
        if cursor_line < len(lines):
            current_line = lines[cursor_line]
            if 'class ' in current_line and current_line.strip().endswith(':'):
                predictions.append({
                    "line": cursor_line + 1,
                    "column": 4,
                    "reason": "init_method",
                    "suggestion": "def __init__(self)",
                })
        
        # Pattern: Empty function body
        if cursor_line + 1 < len(lines):
            next_line = lines[cursor_line + 1].strip()
            if next_line == "pass":
                predictions.append({
                    "line": cursor_line + 1,
                    "column": 0,
                    "reason": "implementation",
                    "suggestion": "",
                })
        
        self._predictions[file_path] = predictions
        return predictions
    
    def get_next_jump(
        self,
        file_path: str,
        current_line: int,
    ) -> Optional[Dict[str, Any]]:
        """Get next jump location after current line."""
        predictions = self._predictions.get(file_path, [])
        for pred in predictions:
            if pred["line"] > current_line:
                return pred
        return None


class TabToImport:
    """
    Tab-to-Import: Quick import insertion.
    
    Detects missing imports and offers to add them with Tab.
    """
    
    def __init__(self):
        """Initialize tab-to-import."""
        self._missing_imports: Dict[str, List[str]] = {}
    
    def detect_missing_imports(
        self,
        file_path: str,
        content: str,
        diagnostics: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect missing imports from diagnostics.
        
        Args:
            file_path: File path
            content: File content
            diagnostics: Linter diagnostics
            
        Returns:
            List of missing imports with suggestions
        """
        missing = []
        
        for diag in diagnostics:
            message = diag.get("message", "")
            
            # Python: undefined name
            if "undefined name" in message.lower():
                import re
                match = re.search(r"'(\w+)'", message)
                if match:
                    symbol = match.group(1)
                    import_suggestion = self._suggest_import(symbol)
                    if import_suggestion:
                        missing.append({
                            "symbol": symbol,
                            "line": diag.get("line", 0),
                            "import": import_suggestion,
                        })
        
        self._missing_imports[file_path] = [m["symbol"] for m in missing]
        return missing
    
    def _suggest_import(self, symbol: str) -> Optional[str]:
        """Suggest import for a symbol."""
        # Python standard library
        stdlib = {
            "Optional": "from typing import Optional",
            "List": "from typing import List",
            "Dict": "from typing import Dict",
            "Any": "from typing import Any",
            "Union": "from typing import Union",
            "Tuple": "from typing import Tuple",
            "Callable": "from typing import Callable",
            "dataclass": "from dataclasses import dataclass",
            "field": "from dataclasses import field",
            "Enum": "from enum import Enum",
            "auto": "from enum import auto",
            "datetime": "from datetime import datetime",
            "timedelta": "from datetime import timedelta",
            "Path": "from pathlib import Path",
            "asyncio": "import asyncio",
            "json": "import json",
            "re": "import re",
            "os": "import os",
            "sys": "import sys",
            "uuid": "import uuid",
            "logging": "import logging",
            "ABC": "from abc import ABC",
            "abstractmethod": "from abc import abstractmethod",
        }
        
        return stdlib.get(symbol)
    
    def apply_import(
        self,
        file_path: str,
        content: str,
        import_text: str,
    ) -> str:
        """Apply an import to file content.
        
        Args:
            file_path: File path
            content: Current content
            import_text: Import to add
            
        Returns:
            Updated content
        """
        lines = content.split('\n')
        
        # Find best position for import
        import_line = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_line = i + 1
            elif line.strip() and not line.startswith('#') and not line.startswith('"""'):
                break
        
        lines.insert(import_line, import_text)
        return '\n'.join(lines)

