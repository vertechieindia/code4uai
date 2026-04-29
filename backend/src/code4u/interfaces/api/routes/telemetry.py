"""Telemetry API — token usage, cost tracking, and observability.

Endpoints:
  - ``GET /telemetry/summary``       — aggregate cost and token stats.
  - ``GET /telemetry/recent``        — recent execution records.
  - ``GET /telemetry/cost-breakdown``— cost breakdown by agent and model.
  - ``POST /telemetry/record``       — manually record an execution (for testing).
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from code4u.platform_core.telemetry import (
    ExecutionRecord,
    get_telemetry_store,
    estimate_cost,
    TOKEN_COST_PER_1K,
)

router = APIRouter()


class RecordRequest(BaseModel):
    agentType: str = Field("refactor", description="Agent type.")
    model: str = Field("gpt-4o-mini", description="LLM model used.")
    inputTokens: int = Field(0, description="Input token count.")
    outputTokens: int = Field(0, description="Output token count.")
    durationMs: float = Field(0, description="Duration in milliseconds.")
    success: bool = Field(True, description="Whether the execution succeeded.")
    description: str = Field("", description="Task description.")


@router.get("/telemetry/summary")
async def telemetry_summary():
    """Get aggregate cost and token stats."""
    store = get_telemetry_store()
    return store.get_summary()


@router.get("/telemetry/recent")
async def telemetry_recent(limit: int = 20):
    """Get recent execution records."""
    store = get_telemetry_store()
    return {"records": store.get_recent(limit)}


@router.get("/telemetry/cost-breakdown")
async def cost_breakdown():
    """Get detailed cost breakdown by agent and model."""
    store = get_telemetry_store()
    summary = store.get_summary()
    return {
        "byAgent": summary["byAgent"],
        "byModel": summary["byModel"],
        "totalCostUSD": summary["totalCostUSD"],
        "totalTokens": summary["totalTokens"],
        "pricing": {
            model: {
                "inputPer1K": rates["input"],
                "outputPer1K": rates["output"],
            }
            for model, rates in TOKEN_COST_PER_1K.items()
        },
    }


@router.post("/telemetry/record")
async def record_execution(request: RecordRequest):
    """Manually record an execution for testing or external integrations."""
    store = get_telemetry_store()
    rec = ExecutionRecord(
        agent_type=request.agentType,
        model=request.model,
        input_tokens=request.inputTokens,
        output_tokens=request.outputTokens,
        duration_ms=request.durationMs,
        success=request.success,
        task_description=request.description,
    )
    rec.cost_usd = estimate_cost(rec.model, rec.input_tokens, rec.output_tokens)
    store.record(rec)
    return {
        "id": rec.id,
        "costUSD": rec.cost_usd,
        "totalTokens": rec.total_tokens,
    }
