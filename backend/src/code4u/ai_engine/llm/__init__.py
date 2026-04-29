from __future__ import annotations
"""Self-hosted LLM inference layer for code4u.ai.

This module provides:
- vLLM integration for high-throughput inference
- Cost-aware model routing
- Batched inference with KV caching
- LoRA adapter management
- Rejection & retry policy
- Fallback handling
"""
from code4u.ai_engine.llm.client import LLMClient, LLMResponse, LLMRequest
from code4u.ai_engine.llm.router import ModelRouter, TaskComplexity
from code4u.ai_engine.llm.prompts import PromptBuilder, Prompt
from code4u.ai_engine.llm.rejection import (
    RejectionPolicy,
    RetryManager,
    Rejection,
    RejectionType,
    RejectionReason,
)
from code4u.ai_engine.llm.executor import LLMExecutor, ExecutionResult

__all__ = [
    "LLMClient",
    "LLMResponse",
    "LLMRequest",
    "ModelRouter",
    "TaskComplexity",
    "PromptBuilder",
    "Prompt",
    "RejectionPolicy",
    "RetryManager",
    "Rejection",
    "RejectionType",
    "RejectionReason",
    "LLMExecutor",
    "ExecutionResult",
]
