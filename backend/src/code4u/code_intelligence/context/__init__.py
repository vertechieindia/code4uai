from __future__ import annotations
"""Context compilation and planning for code4u.ai.

The Context Compiler is the BRAIN of code4u.ai.
LLM is just the code-filling tool.

Flow:
  Knowledge Graph → Context Compiler → Change Planner → LLM → Validator
"""
from code4u.code_intelligence.context.compiler import ContextCompiler, CompiledContext
from code4u.code_intelligence.context.planner import ChangePlanner, ChangePlan

__all__ = ["ContextCompiler", "CompiledContext", "ChangePlanner", "ChangePlan"]

