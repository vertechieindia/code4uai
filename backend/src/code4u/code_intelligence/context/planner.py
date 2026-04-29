from __future__ import annotations
"""Change planner for code4u.ai.

The Change Planner creates execution plans BEFORE involving LLM.
LLM fills in code, but decisions are made HERE.

Day 8: Deterministic ExecutionPlan from RefactorBlastContext. Fixed step order; no LLM.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Tuple
import structlog

from code4u.code_intelligence.context.compiler import (
    CompiledContext,
    RefactorContext,
    RefactorBlastContext,
)

logger = structlog.get_logger("context.planner")


# ----- Day 8: Execution plan from RefactorBlastContext (deterministic, fixed order) -----

_DAY8_STEP_KINDS: Tuple[str, ...] = (
    "GENERATE_CODE",
    "VALIDATE_CODE",
    "PREVIEW_DIFF",
    "APPLY_DIFF",
)


@dataclass(frozen=True)
class ExecutionStep:
    """Single step in an execution plan. kind is one of the allowed step kinds."""
    step_id: str
    kind: str
    files: Tuple[str, ...]


@dataclass(frozen=True)
class ExecutionPlan:
    """
    Day 8: Deterministic execution plan from RefactorBlastContext.
    steps in fixed order; affected_files and metadata mirror context.
    """
    steps: Tuple[ExecutionStep, ...]
    affected_files: Tuple[str, ...]
    metadata: Dict[str, Any]


def plan_from_blast_context(context: RefactorBlastContext) -> ExecutionPlan:
    """
    Generate a single deterministic ExecutionPlan from an assembled RefactorBlastContext.
    No LLM, no file I/O, no recomputation. Step order fixed; all affected files per step.
    """
    if context is None:
        raise ValueError("context is required")
    if not getattr(context, "is_complete", False):
        raise ValueError("context.is_complete must be True")
    blast = context.blast_radius
    if "file_count" not in blast:
        raise ValueError("context.blast_radius must contain 'file_count'")
    if "has_cross_owner" not in blast:
        raise ValueError("context.blast_radius must contain 'has_cross_owner'")
    affected = context.affected_files
    if not affected or len(affected) == 0:
        raise ValueError("context.affected_files must not be empty")

    steps_list: List[ExecutionStep] = []
    for i, kind in enumerate(_DAY8_STEP_KINDS):
        steps_list.append(
            ExecutionStep(
                step_id=str(i + 1),
                kind=kind,
                files=affected,
            )
        )

    metadata = {
        "file_count": blast["file_count"],
        "has_cross_owner": blast["has_cross_owner"],
    }

    return ExecutionPlan(
        steps=tuple(steps_list),
        affected_files=affected,
        metadata=metadata,
    )


# ----- Day-2 minimal plan (deterministic, no LLM) -----

@dataclass
class MinimalExecutionPlan:
    """Minimal execution plan for refactor pipeline. Steps only; no intelligence yet."""
    steps: List[str]
    files: List[str]


def plan_refactor(context: RefactorContext) -> MinimalExecutionPlan:
    """
    Return deterministic execution plan for refactor.
    No intelligence yet. Just structure: GENERATE_CODE on target file.
    """
    return MinimalExecutionPlan(
        steps=["GENERATE_CODE"],
        files=[context.target_file],
    )


class ChangeStepType(str, Enum):
    """Types of change steps."""
    VALIDATE_CONTRACTS = "validate_contracts"
    GENERATE_DIFF = "generate_diff"
    UPDATE_SCHEMA = "update_schema"
    UPDATE_FRONTEND = "update_frontend"
    UPDATE_BACKEND = "update_backend"
    RUN_TYPECHECK = "run_typecheck"
    RUN_TESTS = "run_tests"
    NOTIFY_OWNERS = "notify_owners"


@dataclass
class ChangeStep:
    """A single step in the change plan."""
    step_type: ChangeStepType
    target: str
    description: str
    agent: str  # Which agent handles this
    depends_on: List[str] = field(default_factory=list)
    optional: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChangePlan:
    """
    Complete execution plan for a change.
    
    The plan is deterministic and fully auditable.
    LLM is called ONLY in execute phase.
    """
    plan_id: str
    intent: str
    steps: list[ChangeStep]
    
    # Impact analysis
    blast_radius: Dict[str, int] = field(default_factory=dict)
    breaking_change: bool = False
    affected_teams: List[str] = field(default_factory=list)
    
    # Rollback strategy
    rollback_steps: list[ChangeStep] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "intent": self.intent,
            "steps": [
                {
                    "type": s.step_type.value,
                    "target": s.target,
                    "description": s.description,
                    "agent": s.agent,
                }
                for s in self.steps
            ],
            "blast_radius": self.blast_radius,
            "breaking_change": self.breaking_change,
            "affected_teams": self.affected_teams,
        }


class ChangePlanner:
    """
    Create deterministic execution plans.
    
    Decisions made HERE, not in LLM:
    - Which files to modify
    - Order of changes
    - Validation requirements
    - Rollback strategy
    """
    
    def __init__(self):
        self.logger = logger
    
    def plan(self, context: CompiledContext) -> ChangePlan:
        """
        Create an execution plan for the compiled context.
        
        This is the DECISION POINT. Once a plan is created,
        execution is deterministic.
        """
        import uuid
        
        self.logger.info(
            "creating_plan",
            task_type=context.task_type,
            intent=context.intent
        )
        
        steps: list[ChangeStep] = []
        
        # Step 1: Always validate contracts first
        steps.append(ChangeStep(
            step_type=ChangeStepType.VALIDATE_CONTRACTS,
            target=context.primary_file.path,
            description="Validate existing contracts and schemas",
            agent="contract",
        ))
        
        # Step 2: Generate the actual diff
        steps.append(ChangeStep(
            step_type=ChangeStepType.GENERATE_DIFF,
            target=context.primary_file.path,
            description=f"Generate diff for: {context.intent}",
            agent="llm",  # This is where LLM is called
            depends_on=["validate_contracts"],
            metadata={
                "input_code": context.primary_file.content,
                "context": context.to_llm_context(),
                "constraints": context.constraints,
            }
        ))
        
        # Step 3: Language-specific updates
        if context.language == "python" and "fastapi" in context.frameworks:
            steps.append(ChangeStep(
                step_type=ChangeStepType.UPDATE_BACKEND,
                target=context.primary_file.path,
                description="Update FastAPI service",
                agent="backend",
                depends_on=["generate_diff"],
            ))
        
        if context.language in ("typescript", "javascript"):
            if "react" in context.frameworks:
                steps.append(ChangeStep(
                    step_type=ChangeStepType.UPDATE_FRONTEND,
                    target=context.primary_file.path,
                    description="Update React component",
                    agent="frontend",
                    depends_on=["generate_diff"],
                ))
        
        # Step 4: Always run typecheck
        steps.append(ChangeStep(
            step_type=ChangeStepType.RUN_TYPECHECK,
            target=context.primary_file.path,
            description="Run type checker",
            agent="verifier",
            depends_on=["generate_diff"],
        ))
        
        # Step 5: Run tests if available
        steps.append(ChangeStep(
            step_type=ChangeStepType.RUN_TESTS,
            target=context.primary_file.path,
            description="Run related tests",
            agent="verifier",
            depends_on=["run_typecheck"],
            optional=True,
        ))
        
        # Step 6: Notify owners if cross-team impact
        if context.owner_teams:
            steps.append(ChangeStep(
                step_type=ChangeStepType.NOTIFY_OWNERS,
                target="",
                description=f"Notify teams: {', '.join(context.owner_teams)}",
                agent="orchestrator",
                depends_on=["run_typecheck"],
                optional=True,
            ))
        
        # Calculate blast radius
        blast_radius = {
            "files": 1 + len(context.related_files),
            "repositories": len(context.affected_repositories) or 1,
            "components": len(context.affected_components),
            "teams": len(context.owner_teams),
        }
        
        return ChangePlan(
            plan_id=str(uuid.uuid4()),
            intent=context.intent,
            steps=steps,
            blast_radius=blast_radius,
            breaking_change=context.breaking_change,
            affected_teams=context.owner_teams,
        )
    
    def plan_rollback(self, plan: ChangePlan) -> list[ChangeStep]:
        """Generate rollback steps for a plan."""
        rollback_steps = []
        
        # Reverse order, skip validation steps
        for step in reversed(plan.steps):
            if step.step_type in (
                ChangeStepType.GENERATE_DIFF,
                ChangeStepType.UPDATE_FRONTEND,
                ChangeStepType.UPDATE_BACKEND,
            ):
                rollback_steps.append(ChangeStep(
                    step_type=step.step_type,
                    target=step.target,
                    description=f"ROLLBACK: {step.description}",
                    agent=step.agent,
                    metadata={"rollback": True}
                ))
        
        return rollback_steps

