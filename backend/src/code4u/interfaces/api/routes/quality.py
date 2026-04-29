"""Quality Gate API — code review, guardrails, and consensus.

Endpoints:
  - ``POST /quality/review``     — run Critic + Guardrails on code.
  - ``POST /quality/guardrails`` — run only the static guardrails.
  - ``POST /quality/consensus``  — full Worker-Critic-Judge pipeline.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from code4u.agents.review.critic import CriticAgent
from code4u.core.guardrails import StaticGuardrail, GuardrailViolation
from code4u.core.consensus import ReviewOrchestrator, Verdict

router = APIRouter()


class ReviewRequest(BaseModel):
    content: str = Field(..., description="Code content to review.")
    filePath: str = Field("", description="File path for context.")


class GuardrailRequest(BaseModel):
    content: str = Field(..., description="Code content to scan.")
    filePath: str = Field("", description="File path for context.")


class PlanReviewRequest(BaseModel):
    operations: List[Dict] = Field(..., description="List of file operations.")
    threshold: int = Field(7, description="Minimum score to pass (1-10).")


class ConsensusRequest(BaseModel):
    operations: List[Dict] = Field(..., description="List of file operations.")
    threshold: int = Field(7, description="Minimum score to pass (1-10).")
    strictGuardrails: bool = Field(True, description="Raise on first guardrail violation.")


class _MockOp:
    """Lightweight adapter so dict-based operations work with the Critic."""
    def __init__(self, d: Dict):
        self.file_path = d.get("filePath", d.get("file_path", ""))
        self.content = d.get("content", "")
        self.action = d.get("action", "edit")
        self.original_content = d.get("originalContent", d.get("original_content", ""))


@router.post("/quality/review")
async def review_code(request: ReviewRequest):
    """Run the Critic on a single file's content."""
    critic = CriticAgent()
    review = critic.review_content(request.content, request.filePath)
    return {"review": review.to_dict()}


@router.post("/quality/guardrails")
async def check_guardrails(request: GuardrailRequest):
    """Run deterministic guardrails on code content."""
    guardrail = StaticGuardrail(strict=False)
    result = guardrail.scan_content(request.content, request.filePath)
    return {"result": result.to_dict()}


@router.post("/quality/plan-review")
async def review_plan(request: PlanReviewRequest):
    """Run full Critic review on a set of operations."""
    ops = [_MockOp(d) for d in request.operations]
    critic = CriticAgent(threshold=request.threshold)
    review = critic.review_plan(ops)
    return {"review": review.to_dict()}


@router.post("/quality/consensus")
async def run_consensus(request: ConsensusRequest):
    """Run the full Worker-Critic-Judge consensus pipeline."""
    ops = [_MockOp(d) for d in request.operations]
    orchestrator = ReviewOrchestrator(
        threshold=request.threshold,
        strict_guardrails=request.strictGuardrails,
    )

    try:
        result = orchestrator.review(ops)
    except GuardrailViolation as exc:
        return {
            "result": {
                "verdict": "guardrail_block",
                "approved": False,
                "violation": exc.to_dict(),
            }
        }

    return {"result": result.to_dict()}
