"""
code4u.ai Rules & Workflows Engine

Provides:
- Custom rules for model behavior
- Reusable workflows (prompts)
- Scoped instructions (.mdc files like Cursor)
- Team-shareable configurations
"""

from .models import (
    Rule,
    RuleScope,
    RuleType,
    Workflow,
    WorkflowStep,
    Memory,
)
from .engine import RulesEngine
from .parser import RuleParser

__all__ = [
    "Rule",
    "RuleScope",
    "RuleType",
    "Workflow",
    "WorkflowStep",
    "Memory",
    "RulesEngine",
    "RuleParser",
]

