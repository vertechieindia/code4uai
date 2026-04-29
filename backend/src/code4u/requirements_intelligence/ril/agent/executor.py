"""Requirement execution coordinator."""

from __future__ import annotations
import uuid
from typing import List, Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..models import StructuredRequirement, RequirementStatus
from .planner import ExecutionPlan, PlanStatus


class ExecutionMode(str, Enum):
    """Execution modes."""
    LISTEN_ONLY = "listen_only"     # Default - capture only
    GENERATE_PRD = "generate_prd"    # Create PRD
    GENERATE_PLAN = "generate_plan"  # Create technical plan
    EXECUTE = "execute"              # Full execution (requires approval)


class ExecutionStatus(str, Enum):
    """Execution status."""
    PENDING = "pending"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionRequest:
    """A request to execute requirements."""
    id: str
    mode: ExecutionMode
    
    # Requirements
    requirement_ids: List[str] = field(default_factory=list)
    
    # Status
    status: ExecutionStatus = ExecutionStatus.PENDING
    
    # Plan
    plan_id: Optional[str] = None
    
    # Approval
    requires_approval: bool = True
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    # Execution result
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Audit
    created_by: str = ""
    tenant_id: str = ""


class RequirementExecutor:
    """
    Orchestrates requirement execution.
    
    Modes:
    1. Listen-only (default) - No execution
    2. Generate PRD - Creates PRD document
    3. Generate Plan - Creates implementation plan
    4. Execute - Triggers code4u.ai agents (requires approval)
    """
    
    def __init__(
        self,
        planner=None,
        agent_coordinator=None,
    ):
        """Initialize executor.
        
        Args:
            planner: RequirementPlanner instance
            agent_coordinator: Agent coordinator for execution
        """
        self.planner = planner
        self.agent_coordinator = agent_coordinator
        
        self._requests: Dict[str, ExecutionRequest] = {}
        self._requirements: Dict[str, StructuredRequirement] = {}
        
        # Callbacks
        self._on_approval_needed: List[Callable[[ExecutionRequest], Awaitable[None]]] = []
        self._on_execution_complete: List[Callable[[ExecutionRequest], Awaitable[None]]] = []
    
    def add_requirement(self, requirement: StructuredRequirement) -> None:
        """Add a requirement to the executor.
        
        Args:
            requirement: Structured requirement
        """
        self._requirements[requirement.id] = requirement
    
    async def create_execution_request(
        self,
        requirement_ids: List[str],
        mode: ExecutionMode,
        created_by: str,
        tenant_id: str,
    ) -> ExecutionRequest:
        """Create an execution request.
        
        Args:
            requirement_ids: Requirements to execute
            mode: Execution mode
            created_by: User creating the request
            tenant_id: Tenant ID
            
        Returns:
            Execution request
        """
        request = ExecutionRequest(
            id=str(uuid.uuid4()),
            mode=mode,
            requirement_ids=requirement_ids,
            requires_approval=(mode == ExecutionMode.EXECUTE),
            created_by=created_by,
            tenant_id=tenant_id,
        )
        
        self._requests[request.id] = request
        
        # Process based on mode
        if mode == ExecutionMode.LISTEN_ONLY:
            request.status = ExecutionStatus.COMPLETED
            request.result = {"mode": "listen_only", "captured": len(requirement_ids)}
        
        elif mode in [ExecutionMode.GENERATE_PRD, ExecutionMode.GENERATE_PLAN]:
            await self._generate_plan(request)
        
        elif mode == ExecutionMode.EXECUTE:
            await self._prepare_execution(request)
        
        return request
    
    async def _generate_plan(self, request: ExecutionRequest) -> None:
        """Generate a plan for the request."""
        request.status = ExecutionStatus.PLANNING
        
        # Get requirements
        requirements = [
            self._requirements[rid]
            for rid in request.requirement_ids
            if rid in self._requirements
        ]
        
        if not requirements:
            request.status = ExecutionStatus.FAILED
            request.error = "No valid requirements found"
            return
        
        try:
            if request.mode == ExecutionMode.GENERATE_PRD:
                plan = await self.planner.create_prd(
                    requirements,
                    created_by=request.created_by,
                )
            else:
                plan = await self.planner.create_technical_plan(
                    requirements,
                    created_by=request.created_by,
                )
            
            request.plan_id = plan.id
            request.status = ExecutionStatus.COMPLETED
            request.completed_at = datetime.utcnow()
            request.result = plan.to_dict()
            
        except Exception as e:
            request.status = ExecutionStatus.FAILED
            request.error = str(e)
    
    async def _prepare_execution(self, request: ExecutionRequest) -> None:
        """Prepare for full execution."""
        request.status = ExecutionStatus.PLANNING
        
        # Get requirements
        requirements = [
            self._requirements[rid]
            for rid in request.requirement_ids
            if rid in self._requirements
        ]
        
        if not requirements:
            request.status = ExecutionStatus.FAILED
            request.error = "No valid requirements found"
            return
        
        try:
            # Generate implementation plan
            plan = await self.planner.create_technical_plan(
                requirements,
                created_by=request.created_by,
            )
            
            request.plan_id = plan.id
            request.status = ExecutionStatus.AWAITING_APPROVAL
            
            # Notify approval needed
            await self._notify_approval_needed(request)
            
        except Exception as e:
            request.status = ExecutionStatus.FAILED
            request.error = str(e)
    
    async def approve_execution(
        self,
        request_id: str,
        approved_by: str,
    ) -> bool:
        """Approve an execution request.
        
        Args:
            request_id: Request ID
            approved_by: User approving
            
        Returns:
            True if approved and execution started
        """
        request = self._requests.get(request_id)
        if not request:
            return False
        
        if request.status != ExecutionStatus.AWAITING_APPROVAL:
            return False
        
        request.approved_by = approved_by
        request.approved_at = datetime.utcnow()
        request.status = ExecutionStatus.APPROVED
        
        # Also approve the plan
        if request.plan_id and self.planner:
            self.planner.approve_plan(request.plan_id, approved_by)
        
        # Start execution
        await self._execute(request)
        
        return True
    
    async def reject_execution(
        self,
        request_id: str,
        reason: str,
    ) -> bool:
        """Reject an execution request.
        
        Args:
            request_id: Request ID
            reason: Rejection reason
            
        Returns:
            True if rejected
        """
        request = self._requests.get(request_id)
        if not request:
            return False
        
        request.status = ExecutionStatus.CANCELLED
        request.error = f"Rejected: {reason}"
        request.completed_at = datetime.utcnow()
        
        # Also reject the plan
        if request.plan_id and self.planner:
            self.planner.reject_plan(request.plan_id, reason)
        
        return True
    
    async def _execute(self, request: ExecutionRequest) -> None:
        """Execute the approved request."""
        request.status = ExecutionStatus.EXECUTING
        request.started_at = datetime.utcnow()
        
        try:
            if not self.agent_coordinator:
                # Simulate execution
                request.result = {
                    "status": "simulated",
                    "message": "Agent coordinator not configured",
                    "plan_id": request.plan_id,
                }
                request.status = ExecutionStatus.COMPLETED
            else:
                # Get the plan
                plan = self.planner.get_plan(request.plan_id)
                if not plan:
                    raise ValueError("Plan not found")
                
                # Execute each task
                results = []
                for task in plan.tasks:
                    # Call agent coordinator
                    result = await self.agent_coordinator.execute_task(
                        task_id=task.id,
                        service=task.assigned_service,
                        description=task.description,
                        tenant_id=request.tenant_id,
                    )
                    results.append(result)
                
                request.result = {
                    "status": "completed",
                    "tasks_executed": len(results),
                    "results": results,
                }
                request.status = ExecutionStatus.COMPLETED
                
                # Update requirements status
                for rid in request.requirement_ids:
                    if rid in self._requirements:
                        self._requirements[rid].status = RequirementStatus.IMPLEMENTED
            
            request.completed_at = datetime.utcnow()
            
            # Notify completion
            await self._notify_execution_complete(request)
            
        except Exception as e:
            request.status = ExecutionStatus.FAILED
            request.error = str(e)
            request.completed_at = datetime.utcnow()
    
    def on_approval_needed(
        self,
        callback: Callable[[ExecutionRequest], Awaitable[None]],
    ) -> None:
        """Register callback for approval needed.
        
        Args:
            callback: Async callback
        """
        self._on_approval_needed.append(callback)
    
    def on_execution_complete(
        self,
        callback: Callable[[ExecutionRequest], Awaitable[None]],
    ) -> None:
        """Register callback for execution complete.
        
        Args:
            callback: Async callback
        """
        self._on_execution_complete.append(callback)
    
    async def _notify_approval_needed(self, request: ExecutionRequest) -> None:
        """Notify that approval is needed."""
        for callback in self._on_approval_needed:
            try:
                await callback(request)
            except:
                pass
    
    async def _notify_execution_complete(self, request: ExecutionRequest) -> None:
        """Notify that execution is complete."""
        for callback in self._on_execution_complete:
            try:
                await callback(request)
            except:
                pass
    
    def get_request(self, request_id: str) -> Optional[ExecutionRequest]:
        """Get an execution request."""
        return self._requests.get(request_id)
    
    def list_requests(
        self,
        tenant_id: str,
        status: Optional[ExecutionStatus] = None,
    ) -> List[ExecutionRequest]:
        """List execution requests.
        
        Args:
            tenant_id: Tenant ID
            status: Optional status filter
            
        Returns:
            List of requests
        """
        results = []
        for req in self._requests.values():
            if req.tenant_id != tenant_id:
                continue
            if status and req.status != status:
                continue
            results.append(req)
        return results

