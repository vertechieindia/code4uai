"""Telemetry — tracks time, tokens, and cost per agent execution.

Provides:
  - ``@track_execution`` decorator for automatic per-task instrumentation.
  - ``TelemetryStore`` singleton for querying cost breakdowns.
  - Token-to-cost mapping for major LLM providers.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger("telemetry")


# ---------------------------------------------------------------------------
# Cost tables (USD per 1K tokens)
# ---------------------------------------------------------------------------

TOKEN_COST_PER_1K: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    "codestral": {"input": 0.001, "output": 0.003},
    "deepseek-coder": {"input": 0.00014, "output": 0.00028},
    "local-vllm": {"input": 0.0, "output": 0.0},
}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Estimate cost in USD for a given model and token count."""
    rates = TOKEN_COST_PER_1K.get(model, TOKEN_COST_PER_1K.get("gpt-4o-mini", {}))
    input_cost = (input_tokens / 1000) * rates.get("input", 0)
    output_cost = (output_tokens / 1000) * rates.get("output", 0)
    return round(input_cost + output_cost, 6)


# ---------------------------------------------------------------------------
# Execution record
# ---------------------------------------------------------------------------

@dataclass
class ExecutionRecord:
    """One tracked execution (agent task, refactor, swarm run, etc.)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    agent_type: str = ""
    task_description: str = ""
    model: str = "gpt-4o-mini"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0.0
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# TelemetryStore — singleton
# ---------------------------------------------------------------------------

class TelemetryStore:
    """In-memory store for execution telemetry.

    In production, this would flush to Prometheus / OpenTelemetry / Postgres.
    """

    def __init__(self) -> None:
        self._records: List[ExecutionRecord] = []

    def record(self, rec: ExecutionRecord) -> None:
        rec.total_tokens = rec.input_tokens + rec.output_tokens
        rec.cost_usd = estimate_cost(rec.model, rec.input_tokens, rec.output_tokens)
        self._records.append(rec)
        logger.info(
            "execution_recorded",
            agent=rec.agent_type,
            duration_ms=round(rec.duration_ms, 1),
            tokens=rec.total_tokens,
            cost_usd=rec.cost_usd,
        )

    def get_summary(self) -> Dict[str, Any]:
        """Aggregate cost and token stats across all recorded executions."""
        total_cost = sum(r.cost_usd for r in self._records)
        total_tokens = sum(r.total_tokens for r in self._records)
        total_input = sum(r.input_tokens for r in self._records)
        total_output = sum(r.output_tokens for r in self._records)
        total_duration = sum(r.duration_ms for r in self._records)
        success_count = sum(1 for r in self._records if r.success)

        by_agent: Dict[str, Dict[str, Any]] = {}
        for r in self._records:
            key = r.agent_type or "unknown"
            if key not in by_agent:
                by_agent[key] = {"count": 0, "tokens": 0, "cost_usd": 0.0, "duration_ms": 0.0}
            by_agent[key]["count"] += 1
            by_agent[key]["tokens"] += r.total_tokens
            by_agent[key]["cost_usd"] += r.cost_usd
            by_agent[key]["duration_ms"] += r.duration_ms

        by_model: Dict[str, Dict[str, Any]] = {}
        for r in self._records:
            key = r.model or "unknown"
            if key not in by_model:
                by_model[key] = {"count": 0, "tokens": 0, "cost_usd": 0.0}
            by_model[key]["count"] += 1
            by_model[key]["tokens"] += r.total_tokens
            by_model[key]["cost_usd"] += r.cost_usd

        return {
            "totalExecutions": len(self._records),
            "successCount": success_count,
            "failCount": len(self._records) - success_count,
            "totalTokens": total_tokens,
            "totalInputTokens": total_input,
            "totalOutputTokens": total_output,
            "totalCostUSD": round(total_cost, 4),
            "totalDurationMs": round(total_duration, 1),
            "avgCostPerExecution": round(total_cost / max(len(self._records), 1), 6),
            "avgTokensPerExecution": round(total_tokens / max(len(self._records), 1)),
            "byAgent": {k: {**v, "cost_usd": round(v["cost_usd"], 4)} for k, v in by_agent.items()},
            "byModel": {k: {**v, "cost_usd": round(v["cost_usd"], 4)} for k, v in by_model.items()},
        }

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = sorted(self._records, key=lambda r: r.started_at, reverse=True)[:limit]
        return [
            {
                "id": r.id,
                "agent": r.agent_type,
                "model": r.model,
                "tokens": r.total_tokens,
                "costUSD": r.cost_usd,
                "durationMs": round(r.duration_ms, 1),
                "success": r.success,
                "description": r.task_description[:80],
                "timestamp": r.started_at,
            }
            for r in items
        ]


_store: Optional[TelemetryStore] = None


def get_telemetry_store() -> TelemetryStore:
    global _store
    if _store is None:
        _store = TelemetryStore()
    return _store


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def track_execution(
    agent_type: str = "",
    model: str = "gpt-4o-mini",
    estimate_tokens: bool = True,
) -> Callable:
    """Decorator that wraps a function with telemetry tracking.

    Automatically records duration, and optionally estimates token usage
    based on input/output string length heuristics.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            store = get_telemetry_store()
            rec = ExecutionRecord(
                agent_type=agent_type or func.__name__,
                model=model,
                started_at=time.time(),
            )

            try:
                result = func(*args, **kwargs)
                rec.success = True
                return result
            except Exception as e:
                rec.success = False
                rec.error = str(e)
                raise
            finally:
                rec.ended_at = time.time()
                rec.duration_ms = (rec.ended_at - rec.started_at) * 1000

                if estimate_tokens:
                    input_chars = sum(len(str(a)) for a in args) + sum(len(str(v)) for v in kwargs.values())
                    rec.input_tokens = max(input_chars // 4, 10)
                    rec.output_tokens = max(rec.input_tokens // 3, 5)

                rec.cost_usd = estimate_cost(rec.model, rec.input_tokens, rec.output_tokens)
                store.record(rec)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            store = get_telemetry_store()
            rec = ExecutionRecord(
                agent_type=agent_type or func.__name__,
                model=model,
                started_at=time.time(),
            )

            try:
                result = await func(*args, **kwargs)
                rec.success = True
                return result
            except Exception as e:
                rec.success = False
                rec.error = str(e)
                raise
            finally:
                rec.ended_at = time.time()
                rec.duration_ms = (rec.ended_at - rec.started_at) * 1000

                if estimate_tokens:
                    input_chars = sum(len(str(a)) for a in args) + sum(len(str(v)) for v in kwargs.values())
                    rec.input_tokens = max(input_chars // 4, 10)
                    rec.output_tokens = max(rec.input_tokens // 3, 5)

                rec.cost_usd = estimate_cost(rec.model, rec.input_tokens, rec.output_tokens)
                store.record(rec)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
