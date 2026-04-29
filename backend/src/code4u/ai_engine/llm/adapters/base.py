"""Base LLM Adapter — the contract every provider must follow.

Every adapter implements ``generate_completion`` (request-response) and
``stream_completion`` (async generator yielding chunks).  Both return
``AdapterResponse`` which includes ``UsageMetrics`` for cost tracking.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional


# ---------------------------------------------------------------------------
# Usage & Cost Tracking
# ---------------------------------------------------------------------------

# Per-1K-token pricing (approximate, as of early 2026)
COST_TABLE: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "llama3.1": {"input": 0.0, "output": 0.0},
    "deepseek-coder-v2": {"input": 0.00014, "output": 0.00028},
    "local": {"input": 0.0, "output": 0.0},
}


@dataclass
class UsageMetrics:
    """Token usage and estimated cost for a single LLM call."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model: str = ""
    provider: str = ""
    latency_ms: float = 0.0

    @staticmethod
    def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        rates = COST_TABLE.get(model, {"input": 0.0, "output": 0.0})
        return (input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "totalTokens": self.total_tokens,
            "estimatedCostUsd": round(self.estimated_cost_usd, 6),
            "model": self.model,
            "provider": self.provider,
            "latencyMs": round(self.latency_ms, 1),
        }


# ---------------------------------------------------------------------------
# Adapter Response
# ---------------------------------------------------------------------------

@dataclass
class AdapterResponse:
    """Unified response from any LLM adapter."""
    content: str
    model: str
    provider: str
    usage: UsageMetrics
    finish_reason: str = "stop"
    raw: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base Adapter
# ---------------------------------------------------------------------------

class BaseLLMAdapter(ABC):
    """Abstract base class for LLM provider adapters.

    Every concrete adapter must implement:
      - ``generate_completion`` — single request/response call.
      - ``stream_completion``  — async generator yielding text chunks.
      - ``provider_name``      — returns the provider identifier.
      - ``is_available``       — checks if the provider is configured/reachable.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for this provider (e.g. 'openai', 'anthropic')."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this adapter is configured and reachable."""
        ...

    @abstractmethod
    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        stop: Optional[List[str]] = None,
    ) -> AdapterResponse:
        """Generate a single completion."""
        ...

    @abstractmethod
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Yield text chunks as the LLM generates them."""
        ...
        yield ""  # pragma: no cover

    async def close(self) -> None:
        """Release any resources held by this adapter."""
        pass
