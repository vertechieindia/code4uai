from __future__ import annotations
"""State machine implementation for code4u.ai.

Enforces deterministic state transitions.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import structlog

from code4u.platform_core.state_machine.states import (
    ExecutionState,
    StateTransition,
    StateViolation,
    ALLOWED_TRANSITIONS,
    STATE_AGENT_MAP,
)

logger = structlog.get_logger("state_machine")


@dataclass
class ExecutionContext:
    """
    Context for a single execution.
    
    Tracks state, history, and all artifacts.
    """
    # Identity
    execution_id: str
    tenant_id: str
    user_id: str
    
    # Current state
    state: ExecutionState = ExecutionState.INIT
    
    # History
    transitions: list[StateTransition] = field(default_factory=list)
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Request
    intent: str = ""
    target_file: str = ""
    instruction: str = ""
    
    # Artifacts (populated during execution)
    impact_analysis: Dict[str, Any] | None = None
    execution_plan: Dict[str, Any] | None = None
    contract_validation: Dict[str, Any] | None = None
    generated_diffs: list[Dict[str, Any]] = field(default_factory=list)
    verification_result: Dict[str, Any] | None = None
    
    # Metadata
    retry_count: int = 0
    model_used: str = ""
    tokens_used: int = 0
    
    @property
    def is_terminal(self) -> bool:
        """Check if execution is in a terminal state."""
        return self.state in (
            ExecutionState.APPLIED,
            ExecutionState.REJECTED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
        )
    
    @property
    def current_agent(self) -> str:
        """Get the agent responsible for current state."""
        return STATE_AGENT_MAP.get(self.state, "unknown")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "state": self.state.value,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "intent": self.intent,
            "target_file": self.target_file,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "transition_count": len(self.transitions),
            "is_terminal": self.is_terminal,
        }


class StateMachine:
    """
    State machine for agent coordination.
    
    Enforces:
    - Valid state transitions only
    - No skipping states
    - Full audit trail
    """
    
    def __init__(self):
        self._contexts: dict[str, ExecutionContext] = {}
    
    def create_context(
        self,
        execution_id: str,
        tenant_id: str,
        user_id: str,
        intent: str = "",
        target_file: str = "",
        instruction: str = "",
    ) -> ExecutionContext:
        """Create a new execution context."""
        context = ExecutionContext(
            execution_id=execution_id,
            tenant_id=tenant_id,
            user_id=user_id,
            intent=intent,
            target_file=target_file,
            instruction=instruction,
        )
        
        self._contexts[execution_id] = context
        
        logger.info(
            "context_created",
            execution_id=execution_id,
            tenant_id=tenant_id,
            state=context.state.value
        )
        
        return context
    
    def get_context(self, execution_id: str) -> ExecutionContext | None:
        """Get an execution context."""
        return self._contexts.get(execution_id)
    
    def transition(
        self,
        execution_id: str,
        to_state: ExecutionState,
        agent: str = "",
        reason: str = "",
        metadata: Dict[str, Any] | None = None
    ) -> ExecutionContext:
        """
        Transition to a new state.
        
        Raises StateViolation if transition is not allowed.
        """
        context = self._contexts.get(execution_id)
        if not context:
            raise ValueError(f"Unknown execution: {execution_id}")
        
        current = context.state
        
        # Validate transition
        if to_state not in ALLOWED_TRANSITIONS.get(current, []):
            logger.error(
                "state_violation",
                execution_id=execution_id,
                current=current.value,
                attempted=to_state.value
            )
            raise StateViolation(current, to_state)
        
        # Create transition record
        transition = StateTransition(
            from_state=current,
            to_state=to_state,
            agent=agent or STATE_AGENT_MAP.get(to_state, "unknown"),
            reason=reason,
            metadata=metadata or {},
        )
        
        # Update context
        context.state = to_state
        context.transitions.append(transition)
        context.updated_at = datetime.utcnow().isoformat()
        
        logger.info(
            "state_transitioned",
            execution_id=execution_id,
            from_state=current.value,
            to_state=to_state.value,
            agent=transition.agent
        )
        
        return context
    
    def transition_with_artifact(
        self,
        execution_id: str,
        to_state: ExecutionState,
        artifact_key: str,
        artifact_value: Any,
        agent: str = "",
        reason: str = "",
    ) -> ExecutionContext:
        """Transition and store an artifact."""
        context = self.transition(
            execution_id=execution_id,
            to_state=to_state,
            agent=agent,
            reason=reason,
            metadata={"artifact": artifact_key}
        )
        
        # Store artifact
        if artifact_key == "impact_analysis":
            context.impact_analysis = artifact_value
        elif artifact_key == "execution_plan":
            context.execution_plan = artifact_value
        elif artifact_key == "contract_validation":
            context.contract_validation = artifact_value
        elif artifact_key == "generated_diffs":
            context.generated_diffs = artifact_value
        elif artifact_key == "verification_result":
            context.verification_result = artifact_value
        
        return context
    
    def fail(
        self,
        execution_id: str,
        reason: str,
        error: Optional[str] = None
    ) -> ExecutionContext:
        """Transition to FAILED state."""
        return self.transition(
            execution_id=execution_id,
            to_state=ExecutionState.FAILED,
            agent="error_handler",
            reason=reason,
            metadata={"error": error} if error else None
        )
    
    def cancel(self, execution_id: str, reason: str = "User cancelled") -> ExecutionContext:
        """Transition to CANCELLED state."""
        return self.transition(
            execution_id=execution_id,
            to_state=ExecutionState.CANCELLED,
            agent="user",
            reason=reason
        )
    
    def get_history(self, execution_id: str) -> list[StateTransition]:
        """Get transition history."""
        context = self._contexts.get(execution_id)
        return context.transitions if context else []
    
    def get_allowed_transitions(self, execution_id: str) -> list[ExecutionState]:
        """Get allowed next states."""
        context = self._contexts.get(execution_id)
        if not context:
            return []
        return ALLOWED_TRANSITIONS.get(context.state, [])

