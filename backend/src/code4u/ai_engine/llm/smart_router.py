"""Smart LLM Router — cost-aware complexity classification and failover.

Performs a "Pre-Flight Check" on every request to route it to the
cheapest capable provider:

  **Level 1 (Cheap):** Intent detection, health checks, symbol naming,
  simple renames → GPT-4o-mini / DeepSeek-V3.

  **Level 2 (Premium):** Complex structural refactoring, cross-file
  logic, creative code generation → Claude 3.5 Sonnet / GPT-4o.

If the primary provider fails (auth error, timeout, rate limit), the
router automatically fails over to the next available provider.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

from code4u.ai_engine.llm.adapters.base import (
    AdapterResponse,
    BaseLLMAdapter,
    UsageMetrics,
)

logger = structlog.get_logger("smart_router")


# ---------------------------------------------------------------------------
# Complexity classification
# ---------------------------------------------------------------------------

class ComplexityLevel:
    CHEAP = "cheap"
    PREMIUM = "premium"


_CHEAP_PATTERNS = [
    r"(?i)rename\s+\w+\s+to\s+\w+",
    r"(?i)^health",
    r"(?i)intent\s+detect",
    r"(?i)classify\s+intent",
    r"(?i)symbol\s+naming",
    r"(?i)unused\s+import",
    r"(?i)dead\s+code",
    r"(?i)formatting",
    r"(?i)lint\s+fix",
]

_PREMIUM_PATTERNS = [
    r"(?i)extract\s+\w+\s+to\s+",
    r"(?i)convert\s+.+\s+to\s+class",
    r"(?i)refactor\s+.+\s+for\s+",
    r"(?i)optim\w*\s+",
    r"(?i)rewrite\s+",
    r"(?i)restructure",
    r"(?i)migrate\s+",
    r"(?i)split\s+.+\s+into\s+",
    r"(?i)merge\s+.+\s+into\s+",
    r"(?i)cross.?file",
    r"(?i)multi.?file",
    r"(?i)architect",
]


def classify_complexity(intent: str, file_count: int = 1) -> str:
    """Classify an intent into cheap or premium tier.

    Multi-file operations (3+ files) are always premium.
    """
    if file_count >= 3:
        return ComplexityLevel.PREMIUM

    for pattern in _CHEAP_PATTERNS:
        if re.search(pattern, intent):
            return ComplexityLevel.CHEAP

    for pattern in _PREMIUM_PATTERNS:
        if re.search(pattern, intent):
            return ComplexityLevel.PREMIUM

    # Default: short intents are cheap, long ones are premium
    return ComplexityLevel.CHEAP if len(intent) < 60 else ComplexityLevel.PREMIUM


# ---------------------------------------------------------------------------
# Model mapping
# ---------------------------------------------------------------------------

CHEAP_MODELS: Dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "ollama": "llama3.1",
    "local": "llama3.1",
}

PREMIUM_MODELS: Dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "ollama": "llama3.1",
    "local": "deepseek-coder-v2",
}

# ---------------------------------------------------------------------------
# Agent-to-model routing table
# ---------------------------------------------------------------------------

MODEL_ROUTING_TABLE: Dict[str, Dict[str, str]] = {
    "index": {"cloud": "gpt-4o-mini", "local": "llama3.1"},
    "graph": {"cloud": "gpt-4o-mini", "local": "llama3.1"},
    "vision": {"cloud": "gpt-4o", "local": "llama3.1"},
    "migration": {"cloud": "claude-sonnet-4-20250514", "local": "deepseek-coder-v2"},
    "heal": {"cloud": "claude-sonnet-4-20250514", "local": "qwen2.5-coder:32b"},
    "jury": {"cloud": "gpt-4o", "local": "deepseek-coder-v2"},
    "recipe": {"cloud": "gpt-4o-mini", "local": "llama3.1"},
    "refactor": {"cloud": "claude-sonnet-4-20250514", "local": "deepseek-coder-v2"},
    "profiler": {"cloud": "gpt-4o-mini", "local": "llama3.1"},
    "deploy": {"cloud": "gpt-4o-mini", "local": "llama3.1"},
    "chat": {"cloud": "gpt-4o-mini", "local": "llama3.1"},
    "chief": {"cloud": "gpt-4o", "local": "deepseek-coder-v2"},
    "documentation": {"cloud": "gpt-4o-mini", "local": "llama3.1"},
    "rename": {"cloud": "gpt-4o-mini", "local": "llama3.1"},
}


def get_model_for_agent(agent_type: str, air_gapped: bool = False) -> str:
    """Look up the recommended model for a given agent type."""
    mode = "local" if air_gapped else "cloud"
    entry = MODEL_ROUTING_TABLE.get(agent_type.lower(), MODEL_ROUTING_TABLE.get("chat", {}))
    return entry.get(mode, entry.get("cloud", "gpt-4o-mini"))


# ---------------------------------------------------------------------------
# Routing result
# ---------------------------------------------------------------------------

@dataclass
class RoutingDecision:
    """Metadata about how a request was routed."""
    complexity: str
    chosen_provider: str
    chosen_model: str
    fallback_used: bool = False
    fallback_provider: Optional[str] = None
    routing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "complexity": self.complexity,
            "chosenProvider": self.chosen_provider,
            "chosenModel": self.chosen_model,
        }
        if self.fallback_used:
            d["fallbackUsed"] = True
            d["fallbackProvider"] = self.fallback_provider
        d["routingTimeMs"] = round(self.routing_time_ms, 1)
        return d


# ---------------------------------------------------------------------------
# SmartRouter
# ---------------------------------------------------------------------------

class SmartRouter:
    """Cost-aware LLM router with automatic failover.

    Holds an ordered list of adapters.  For each request it:
      1. Classifies the intent complexity.
      2. Picks the cheapest adequate model.
      3. Tries the primary adapter; on failure, fails over.
    """

    def __init__(self, adapters: Optional[List[BaseLLMAdapter]] = None):
        self._adapters: List[BaseLLMAdapter] = adapters or []
        self._cumulative_usage: List[UsageMetrics] = []

    def register(self, adapter: BaseLLMAdapter) -> None:
        self._adapters.append(adapter)

    @property
    def adapters(self) -> List[BaseLLMAdapter]:
        return list(self._adapters)

    @property
    def cumulative_cost(self) -> float:
        return sum(u.estimated_cost_usd for u in self._cumulative_usage)

    @property
    def cumulative_tokens(self) -> int:
        return sum(u.total_tokens for u in self._cumulative_usage)

    async def route(
        self,
        messages: List[Dict[str, str]],
        intent: str = "",
        file_count: int = 1,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        force_provider: Optional[str] = None,
        force_model: Optional[str] = None,
    ) -> tuple[AdapterResponse, RoutingDecision]:
        """Route a request to the best available adapter.

        Returns:
            Tuple of (AdapterResponse, RoutingDecision).

        Raises:
            RuntimeError: If no adapter can serve the request.
        """
        t0 = time.perf_counter()
        complexity = classify_complexity(intent, file_count)
        model_map = CHEAP_MODELS if complexity == ComplexityLevel.CHEAP else PREMIUM_MODELS

        ordered = list(self._adapters)
        if force_provider:
            ordered = sorted(
                ordered,
                key=lambda a: 0 if a.provider_name == force_provider else 1,
            )

        last_error: Optional[Exception] = None
        fallback_used = False

        for idx, adapter in enumerate(ordered):
            available = await adapter.is_available()
            if not available:
                continue

            model = force_model or model_map.get(adapter.provider_name, None)

            try:
                response = await adapter.generate_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self._cumulative_usage.append(response.usage)

                decision = RoutingDecision(
                    complexity=complexity,
                    chosen_provider=adapter.provider_name,
                    chosen_model=response.model,
                    fallback_used=fallback_used,
                    fallback_provider=adapter.provider_name if fallback_used else None,
                    routing_time_ms=(time.perf_counter() - t0) * 1000,
                )

                logger.info(
                    "request_routed",
                    complexity=complexity,
                    provider=adapter.provider_name,
                    model=response.model,
                    cost=round(response.usage.estimated_cost_usd, 6),
                    fallback=fallback_used,
                )

                return response, decision

            except Exception as exc:
                last_error = exc
                fallback_used = True
                logger.warning(
                    "adapter_failed_over",
                    provider=adapter.provider_name,
                    error=str(exc)[:200],
                    next_idx=idx + 1,
                )

        raise RuntimeError(
            f"All {len(self._adapters)} adapters failed. Last error: {last_error}"
        )

    async def close(self) -> None:
        for adapter in self._adapters:
            await adapter.close()
