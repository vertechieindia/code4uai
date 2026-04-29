from __future__ import annotations
"""State definitions for the Agent Coordination State Machine.

The state machine is AUTHORITATIVE.
This is how you prevent:
- Partial refactors
- Silent failures
- Inconsistent edits

Cursor does NOT have this. That's a hard moat.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionState(str, Enum):
    """
    Execution states for code4u.ai operations.
    
    Transitions are strictly enforced.
    """
    # Initial
    INIT = "INIT"
    
    # Analysis phase
    IMPACT_ANALYZED = "IMPACT_ANALYZED"
    
    # Planning phase
    PLAN_GENERATED = "PLAN_GENERATED"
    
    # Validation phase
    CONTRACT_VALIDATED = "CONTRACT_VALIDATED"
    
    # Generation phase
    CODE_GENERATED = "CODE_GENERATED"
    
    # Verification phase
    VERIFIED = "VERIFIED"
    
    # Human review
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    
    # Terminal states
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Allowed state transitions (CODE-ENFORCED)
ALLOWED_TRANSITIONS: dict[ExecutionState, list[ExecutionState]] = {
    ExecutionState.INIT: [
        ExecutionState.IMPACT_ANALYZED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    ],
    ExecutionState.IMPACT_ANALYZED: [
        ExecutionState.PLAN_GENERATED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    ],
    ExecutionState.PLAN_GENERATED: [
        ExecutionState.CONTRACT_VALIDATED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    ],
    ExecutionState.CONTRACT_VALIDATED: [
        ExecutionState.CODE_GENERATED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    ],
    ExecutionState.CODE_GENERATED: [
        ExecutionState.VERIFIED,
        ExecutionState.CONTRACT_VALIDATED,  # Retry
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    ],
    ExecutionState.VERIFIED: [
        ExecutionState.READY_FOR_REVIEW,
        ExecutionState.CODE_GENERATED,  # Retry
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    ],
    ExecutionState.READY_FOR_REVIEW: [
        ExecutionState.APPLIED,
        ExecutionState.REJECTED,
        ExecutionState.CANCELLED,
    ],
    # Terminal states have no transitions
    ExecutionState.APPLIED: [],
    ExecutionState.REJECTED: [],
    ExecutionState.FAILED: [],
    ExecutionState.CANCELLED: [],
}


# Agent responsibilities by state
STATE_AGENT_MAP: dict[ExecutionState, str] = {
    ExecutionState.INIT: "orchestrator",
    ExecutionState.IMPACT_ANALYZED: "knowledge_graph",
    ExecutionState.PLAN_GENERATED: "planner",
    ExecutionState.CONTRACT_VALIDATED: "contract",
    ExecutionState.CODE_GENERATED: "llm",  # frontend/backend agent
    ExecutionState.VERIFIED: "verifier",
    ExecutionState.READY_FOR_REVIEW: "human",
    ExecutionState.APPLIED: "orchestrator",
    ExecutionState.REJECTED: "orchestrator",
}


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: ExecutionState
    to_state: ExecutionState
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    agent: str = ""
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class StateViolation(Exception):
    """Raised when an invalid state transition is attempted."""
    
    def __init__(
        self,
        current: ExecutionState,
        attempted: ExecutionState,
        message: str = ""
    ):
        self.current = current
        self.attempted = attempted
        super().__init__(
            message or f"Invalid transition: {current.value} → {attempted.value}"
        )

