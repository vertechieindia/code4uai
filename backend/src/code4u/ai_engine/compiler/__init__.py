from __future__ import annotations
"""Context → Prompt Compiler (CPC) for code4u.ai.

The most important system after the Knowledge Graph.

Its job is to convert deterministic system knowledge 
into a constrained LLM execution contract.

The LLM never sees:
- The whole repo
- Irrelevant files
- Ambiguous instructions
- Human phrasing

It sees MACHINE-CURATED INTENT.
"""
from code4u.ai_engine.compiler.prompt_compiler import (
    PromptCompiler,
    PromptBundle,
    CompilerInput,
    CompiledScope,
)
from code4u.ai_engine.compiler.constraints import (
    Constraint,
    ConstraintType,
    ConstraintEncoder,
)
from code4u.ai_engine.compiler.scope_reducer import ScopeReducer

__all__ = [
    "PromptCompiler",
    "PromptBundle", 
    "CompilerInput",
    "CompiledScope",
    "Constraint",
    "ConstraintType",
    "ConstraintEncoder",
    "ScopeReducer",
]

