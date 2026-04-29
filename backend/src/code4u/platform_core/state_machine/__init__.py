from __future__ import annotations
"""Agent Coordination State Machine for code4u.ai.

Agents do NOT chat. They advance state.

States:
INIT → IMPACT_ANALYZED → PLAN_GENERATED → CONTRACT_VALIDATED 
     → CODE_GENERATED → VERIFIED → READY_FOR_REVIEW → APPLIED | REJECTED

Day 9: Plan execution states (plan_states) for running ExecutionPlan.
"""
from code4u.platform_core.state_machine.states import (
    ExecutionState,
    StateTransition,
    ALLOWED_TRANSITIONS,
)
from code4u.platform_core.state_machine.machine import StateMachine, ExecutionContext
from code4u.platform_core.state_machine.coordinator import AgentCoordinator
from code4u.platform_core.state_machine.plan_states import (
    PlanExecutionState,
    PlanStateViolation,
    ALLOWED_PLAN_TRANSITIONS,
    can_transition,
)

__all__ = [
    "ExecutionState",
    "StateTransition",
    "ALLOWED_TRANSITIONS",
    "StateMachine",
    "ExecutionContext",
    "AgentCoordinator",
    "PlanExecutionState",
    "PlanStateViolation",
    "ALLOWED_PLAN_TRANSITIONS",
    "can_transition",
]

