from __future__ import annotations
"""Day 9: Plan execution state machine. Locked states and transitions.

Plans stop being data and start being law.
No step may be skipped, repeated, or run out of order.
"""
from enum import Enum
from typing import Dict, List


class PlanExecutionState(str, Enum):
    """Locked states for running an ExecutionPlan. No new states allowed."""
    INIT = "INIT"
    PLAN_READY = "PLAN_READY"
    CODE_GENERATED = "CODE_GENERATED"
    CODE_VALIDATED = "CODE_VALIDATED"
    DIFF_PREVIEWED = "DIFF_PREVIEWED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"


# Allowed transitions: From -> list of To. Any transition not listed → raise.
ALLOWED_PLAN_TRANSITIONS: Dict[PlanExecutionState, List[PlanExecutionState]] = {
    PlanExecutionState.INIT: [PlanExecutionState.PLAN_READY, PlanExecutionState.FAILED],
    PlanExecutionState.PLAN_READY: [PlanExecutionState.CODE_GENERATED, PlanExecutionState.FAILED],
    PlanExecutionState.CODE_GENERATED: [PlanExecutionState.CODE_VALIDATED, PlanExecutionState.FAILED],
    PlanExecutionState.CODE_VALIDATED: [PlanExecutionState.DIFF_PREVIEWED, PlanExecutionState.FAILED],
    PlanExecutionState.DIFF_PREVIEWED: [PlanExecutionState.APPLIED, PlanExecutionState.FAILED],
    PlanExecutionState.APPLIED: [],
    PlanExecutionState.FAILED: [],
}


def can_transition(current: PlanExecutionState, to: PlanExecutionState) -> bool:
    """Return True only if the transition is allowed."""
    return to in ALLOWED_PLAN_TRANSITIONS.get(current, [])


class PlanStateViolation(Exception):
    """Raised when an invalid plan execution state transition is attempted."""

    def __init__(self, current: PlanExecutionState, attempted: PlanExecutionState, message: str = ""):
        self.current = current
        self.attempted = attempted
        super().__init__(
            message or f"Invalid plan transition: {current.value} → {attempted.value}"
        )
