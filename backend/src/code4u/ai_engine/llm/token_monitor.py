"""Token Monitor — budget enforcement and hallucination kill-switch.

Tracks cumulative token usage across a refactoring session and aborts
the job if:
  - A single response exceeds ``max_response_tokens`` (default 10,000) —
    a sign of a "hallucination loop" where the LLM is generating runaway
    output.
  - The total session cost exceeds ``max_session_cost_usd``.

Because the Day 1 "Safety Cage" guarantees atomic rollback, a budget-
aborted job results in a perfect rollback with zero half-written files.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

from code4u.ai_engine.llm.adapters.base import UsageMetrics

logger = structlog.get_logger("token_monitor")

_DEFAULT_MAX_RESPONSE_TOKENS = 10_000
_DEFAULT_MAX_SESSION_COST = 1.00  # USD


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TokenBudgetExceeded(Exception):
    """Raised when a response exceeds the token budget."""

    def __init__(self, tokens: int, limit: int, message: Optional[str] = None):
        self.tokens = tokens
        self.limit = limit
        super().__init__(
            message or (
                f"Response exceeded token budget: {tokens:,} tokens "
                f"(limit: {limit:,}). Possible hallucination loop detected. "
                f"Job aborted — rollback guaranteed."
            )
        )


class CostBudgetExceeded(Exception):
    """Raised when cumulative session cost exceeds the budget."""

    def __init__(self, cost: float, limit: float, message: Optional[str] = None):
        self.cost = cost
        self.limit = limit
        super().__init__(
            message or (
                f"Session cost exceeded budget: ${cost:.4f} "
                f"(limit: ${limit:.2f}). Job aborted — rollback guaranteed."
            )
        )


# ---------------------------------------------------------------------------
# TokenMonitor
# ---------------------------------------------------------------------------

@dataclass
class TokenMonitor:
    """Tracks token usage and enforces budget constraints.

    Attach to a PlanExecutor session. After every LLM call, invoke
    ``check(usage)`` to verify the response is within bounds.
    """
    max_response_tokens: int = _DEFAULT_MAX_RESPONSE_TOKENS
    max_session_cost_usd: float = _DEFAULT_MAX_SESSION_COST

    # Accumulated state
    calls: List[UsageMetrics] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    aborted: bool = False
    abort_reason: Optional[str] = None

    def check(self, usage: UsageMetrics) -> None:
        """Record usage and enforce limits.

        Raises:
            TokenBudgetExceeded: If the response exceeds max_response_tokens.
            CostBudgetExceeded: If cumulative cost exceeds max_session_cost_usd.
        """
        self.calls.append(usage)
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.total_tokens += usage.total_tokens
        self.total_cost_usd += usage.estimated_cost_usd

        if usage.output_tokens > self.max_response_tokens:
            self.aborted = True
            self.abort_reason = "token_budget_exceeded"
            logger.error(
                "token_budget_exceeded",
                output_tokens=usage.output_tokens,
                limit=self.max_response_tokens,
                model=usage.model,
            )
            raise TokenBudgetExceeded(
                tokens=usage.output_tokens,
                limit=self.max_response_tokens,
            )

        if self.total_cost_usd > self.max_session_cost_usd:
            self.aborted = True
            self.abort_reason = "cost_budget_exceeded"
            logger.error(
                "cost_budget_exceeded",
                total_cost=self.total_cost_usd,
                limit=self.max_session_cost_usd,
            )
            raise CostBudgetExceeded(
                cost=self.total_cost_usd,
                limit=self.max_session_cost_usd,
            )

    @property
    def summary(self) -> Dict[str, Any]:
        return {
            "totalCalls": len(self.calls),
            "totalInputTokens": self.total_input_tokens,
            "totalOutputTokens": self.total_output_tokens,
            "totalTokens": self.total_tokens,
            "totalCostUsd": round(self.total_cost_usd, 6),
            "aborted": self.aborted,
            "abortReason": self.abort_reason,
        }
