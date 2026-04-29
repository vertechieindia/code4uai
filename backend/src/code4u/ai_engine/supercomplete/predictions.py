"""Prediction Engine - ML-based code predictions."""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PredictionType(str, Enum):
    """Types of predictions."""
    NEXT_TOKEN = "next_token"
    NEXT_LINE = "next_line"
    NEXT_BLOCK = "next_block"
    REFACTOR = "refactor"
    FIX = "fix"


@dataclass
class Prediction:
    """A code prediction."""
    id: str
    type: PredictionType
    
    # Content
    text: str
    score: float = 0.0
    
    # Position
    line: int = 0
    column: int = 0
    
    # Metadata
    reason: str = ""
    source: str = "model"


class PredictionEngine:
    """
    ML-based prediction engine for code.
    
    Uses multiple signals:
    - Syntax patterns
    - Semantic understanding
    - Project-specific patterns
    - User behavior
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize prediction engine."""
        self.tenant_id = tenant_id
        self._model = None
        self._user_patterns: Dict[str, List[Dict[str, Any]]] = {}
    
    async def predict_next(
        self,
        file_path: str,
        content: str,
        cursor_line: int,
        cursor_column: int,
        language: str = "python",
    ) -> List[Prediction]:
        """Predict next code to type.
        
        Args:
            file_path: Current file
            content: File content
            cursor_line: Cursor line
            cursor_column: Cursor column
            language: Programming language
            
        Returns:
            List of predictions
        """
        predictions = []
        
        lines = content.split('\n')
        if cursor_line >= len(lines):
            return predictions
        
        current_line = lines[cursor_line]
        prefix = current_line[:cursor_column]
        
        # Pattern-based predictions
        predictions.extend(self._pattern_predictions(prefix, language))
        
        # Context-based predictions
        context = self._extract_context(lines, cursor_line)
        predictions.extend(self._context_predictions(context, language))
        
        # User pattern predictions
        user_preds = self._user_pattern_predictions(file_path, prefix)
        predictions.extend(user_preds)
        
        # Sort by score
        predictions.sort(key=lambda p: p.score, reverse=True)
        
        return predictions[:5]
    
    def _pattern_predictions(
        self,
        prefix: str,
        language: str,
    ) -> List[Prediction]:
        """Generate predictions based on syntax patterns."""
        predictions = []
        prefix_stripped = prefix.strip()
        
        if language == "python":
            patterns = [
                # Control flow
                ("if ", ":", 0.9),
                ("elif ", ":", 0.9),
                ("else", ":", 0.9),
                ("for ", " in :", 0.85),
                ("while ", ":", 0.85),
                ("try", ":", 0.9),
                ("except ", " as e:", 0.85),
                ("finally", ":", 0.9),
                ("with ", " as :", 0.85),
                
                # Definitions
                ("def ", "(self):", 0.8),
                ("async def ", "(self):", 0.8),
                ("class ", ":", 0.9),
                
                # Common patterns
                ("return ", "", 0.7),
                ("raise ", "Exception()", 0.75),
                ("self.", "", 0.6),
                ("await ", "", 0.7),
                
                # Comprehensions
                ("[x for ", " in ]", 0.8),
                ("{k: v for ", " in .items()}", 0.8),
            ]
            
            for trigger, completion, score in patterns:
                if prefix_stripped.endswith(trigger.strip()):
                    predictions.append(Prediction(
                        id=str(uuid.uuid4()),
                        type=PredictionType.NEXT_TOKEN,
                        text=completion,
                        score=score,
                        reason=f"Pattern: {trigger}",
                    ))
        
        elif language in ["typescript", "javascript"]:
            patterns = [
                ("if (", ") {}", 0.9),
                ("for (", ") {}", 0.9),
                ("while (", ") {}", 0.9),
                ("switch (", ") {}", 0.85),
                ("function ", "() {}", 0.8),
                ("const ", " = ", 0.85),
                ("let ", " = ", 0.85),
                ("async ", "function", 0.8),
                ("await ", "", 0.7),
                ("return ", "", 0.7),
                ("throw new ", "Error()", 0.75),
                ("console.", "log()", 0.6),
                ("export ", "const", 0.8),
                ("import ", " from ''", 0.85),
            ]
            
            for trigger, completion, score in patterns:
                if prefix_stripped.endswith(trigger.strip()):
                    predictions.append(Prediction(
                        id=str(uuid.uuid4()),
                        type=PredictionType.NEXT_TOKEN,
                        text=completion,
                        score=score,
                        reason=f"Pattern: {trigger}",
                    ))
        
        return predictions
    
    def _extract_context(
        self,
        lines: List[str],
        cursor_line: int,
    ) -> Dict[str, Any]:
        """Extract context from surrounding code."""
        context = {
            "in_class": False,
            "in_function": False,
            "class_name": None,
            "function_name": None,
            "indent_level": 0,
        }
        
        # Look backwards for class/function definitions
        for i in range(cursor_line, -1, -1):
            line = lines[i]
            stripped = line.strip()
            
            if stripped.startswith("class ") and ":" in stripped:
                context["in_class"] = True
                context["class_name"] = stripped.split()[1].split("(")[0].split(":")[0]
                break
            elif (stripped.startswith("def ") or stripped.startswith("async def ")) and ":" in stripped:
                context["in_function"] = True
                parts = stripped.replace("async ", "").split()[1]
                context["function_name"] = parts.split("(")[0]
        
        # Get indent level
        if cursor_line < len(lines):
            current = lines[cursor_line]
            context["indent_level"] = len(current) - len(current.lstrip())
        
        return context
    
    def _context_predictions(
        self,
        context: Dict[str, Any],
        language: str,
    ) -> List[Prediction]:
        """Generate predictions based on code context."""
        predictions = []
        
        if language == "python":
            # In class, suggest methods
            if context["in_class"] and not context["in_function"]:
                predictions.append(Prediction(
                    id=str(uuid.uuid4()),
                    type=PredictionType.NEXT_LINE,
                    text="def __init__(self):",
                    score=0.85,
                    reason="Class method: __init__",
                ))
                predictions.append(Prediction(
                    id=str(uuid.uuid4()),
                    type=PredictionType.NEXT_LINE,
                    text="def __str__(self):",
                    score=0.7,
                    reason="Class method: __str__",
                ))
            
            # In function, suggest return
            if context["in_function"]:
                predictions.append(Prediction(
                    id=str(uuid.uuid4()),
                    type=PredictionType.NEXT_LINE,
                    text="return",
                    score=0.6,
                    reason="Function return",
                ))
        
        return predictions
    
    def _user_pattern_predictions(
        self,
        file_path: str,
        prefix: str,
    ) -> List[Prediction]:
        """Generate predictions from user's typing patterns."""
        predictions = []
        patterns = self._user_patterns.get(file_path, [])
        
        for pattern in patterns:
            if prefix.endswith(pattern.get("trigger", "")):
                predictions.append(Prediction(
                    id=str(uuid.uuid4()),
                    type=PredictionType.NEXT_TOKEN,
                    text=pattern.get("completion", ""),
                    score=pattern.get("frequency", 0.5),
                    reason="Your pattern",
                    source="user_history",
                ))
        
        return predictions
    
    def record_acceptance(
        self,
        file_path: str,
        trigger: str,
        completion: str,
    ) -> None:
        """Record when user accepts a completion.
        
        Args:
            file_path: File path
            trigger: What triggered the completion
            completion: What was completed
        """
        if file_path not in self._user_patterns:
            self._user_patterns[file_path] = []
        
        # Update frequency
        for pattern in self._user_patterns[file_path]:
            if pattern["trigger"] == trigger and pattern["completion"] == completion:
                pattern["frequency"] = min(1.0, pattern["frequency"] + 0.1)
                return
        
        # Add new pattern
        self._user_patterns[file_path].append({
            "trigger": trigger,
            "completion": completion,
            "frequency": 0.5,
            "count": 1,
        })
    
    def get_user_patterns(self, file_path: str) -> List[Dict[str, Any]]:
        """Get user patterns for a file."""
        return self._user_patterns.get(file_path, [])

