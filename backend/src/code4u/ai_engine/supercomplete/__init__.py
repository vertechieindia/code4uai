"""
Supercomplete - Next-Generation Code Completion

Beyond basic autocomplete:
- Multi-line intelligent completions
- Tab-to-accept with smart cursors
- Supercomplete: Multi-step code generation
- Context-aware from Knowledge Graph
- Codebase-aware suggestions
"""

from .engine import SupercompleteEngine
from .tab_engine import TabEngine
from .predictions import PredictionEngine

__all__ = [
    "SupercompleteEngine",
    "TabEngine", 
    "PredictionEngine",
]

