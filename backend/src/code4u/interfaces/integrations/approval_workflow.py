"""
Approval Workflow System

Manages the complete flow from requirement extraction to task execution:
1. Requirements extracted from meetings/tickets
2. Presented to team for review
3. Team can edit/approve/reject
4. Approved requirements trigger code4u.ai agent
5. Progress reported back to source platform
"""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    DRAFT = "draft"
    PENDING = "pending"
    PARTIAL = "partial"  # Some approvers approved
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TaskExecutionStatus(str, Enum):
    """Status of task execution after approval."""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    """An approval request for requirements."""
    id: str
    
    # Source
    source_type: str  # meeting, jira, servicenow, etc.
    source_id: str
    source_url: Optional[str] = None
    
    # Content
    title: str = ""
    description: str = ""
    requirements: List[Dict[str, Any]] = field(default_factory=list)
    
    # Approval settings
    approvers: List[str] = field(default_factory=list)
    required_approvals: int = 1  # Number of approvals needed
    
    # Status tracking
    status: ApprovalStatus = ApprovalStatus.DRAFT
    approved_by: List[str] = field(default_factory=list)
    rejected_by: List[str] = field(default_factory=list)
    
    # Comments/feedback
    comments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Modifications
    original_requirements: List[Dict[str, Any]] = field(default_factory=list)
    modifications: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Execution
    execution_status: Optional[TaskExecutionStatus] = None
    execution_id: Optional[str] = None
    
    # Notifications
    notification_channel: Optional[str] = None
    notification_platform: str = "slack"
    notification_message_id: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of executing approved requirements."""
    request_id: str
    status: TaskExecutionStatus
    
    # Results per requirement
    requirement_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Artifacts
    pull_requests: List[str] = field(default_factory=list)
    commits: List[str] = field(default_factory=list)
    
    # Stats
    files_changed: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Errors
    errors: List[str] = field(default_factory=list)


class ApprovalWorkflow:
    """
    Central approval workflow manager.
    
    Orchestrates:
    1. Creating approval requests from various sources
    2. Distributing to appropriate channels
    3. Collecting votes and modifications
    4. Triggering execution after approval
    5. Reporting results back
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize approval workflow.
        
        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id
        self._requests: Dict[str, ApprovalRequest] = {}
        self._execution_callbacks: List[Callable[[ApprovalRequest], Awaitable[ExecutionResult]]] = []
        self._notification_callbacks: Dict[str, Callable] = {}
    
    def create_request(
        self,
        source_type: str,
        source_id: str,
        title: str,
        requirements: List[Dict[str, Any]],
        approvers: List[str],
        required_approvals: int = 1,
        description: str = "",
        notification_channel: Optional[str] = None,
        notification_platform: str = "slack",
    ) -> ApprovalRequest:
        """Create a new approval request.
        
        Args:
            source_type: Source of requirements (meeting, jira, etc.)
            source_id: ID in source system
            title: Request title
            requirements: List of requirements to approve
            approvers: List of approver user IDs
            required_approvals: Number of approvals needed
            description: Additional description
            notification_channel: Channel to notify
            notification_platform: Platform for notifications
            
        Returns:
            Created ApprovalRequest
        """
        request = ApprovalRequest(
            id=str(uuid.uuid4()),
            source_type=source_type,
            source_id=source_id,
            title=title,
            description=description,
            requirements=requirements,
            original_requirements=requirements.copy(),
            approvers=approvers,
            required_approvals=required_approvals,
            status=ApprovalStatus.PENDING,
            notification_channel=notification_channel,
            notification_platform=notification_platform,
        )
        
        self._requests[request.id] = request
        return request
    
    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request."""
        return self._requests.get(request_id)
    
    def list_requests(
        self,
        status: Optional[ApprovalStatus] = None,
        source_type: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """List approval requests.
        
        Args:
            status: Filter by status
            source_type: Filter by source
            
        Returns:
            List of matching requests
        """
        requests = list(self._requests.values())
        
        if status:
            requests = [r for r in requests if r.status == status]
        if source_type:
            requests = [r for r in requests if r.source_type == source_type]
        
        return sorted(requests, key=lambda r: r.created_at, reverse=True)
    
    async def approve(
        self,
        request_id: str,
        user_id: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an approval.
        
        Args:
            request_id: Request to approve
            user_id: Approving user
            comment: Optional approval comment
            
        Returns:
            Updated status
        """
        request = self._requests.get(request_id)
        if not request:
            return {"error": "Request not found"}
        
        if user_id not in request.approvers:
            return {"error": "User not authorized to approve"}
        
        if user_id in request.approved_by:
            return {"error": "Already approved by this user"}
        
        request.approved_by.append(user_id)
        request.updated_at = datetime.utcnow()
        
        if comment:
            request.comments.append({
                "user_id": user_id,
                "type": "approval",
                "text": comment,
                "timestamp": datetime.utcnow().isoformat(),
            })
        
        # Check if fully approved
        if len(request.approved_by) >= request.required_approvals:
            request.status = ApprovalStatus.APPROVED
            request.approved_at = datetime.utcnow()
            
            # Trigger execution
            result = await self._execute(request)
            
            return {
                "status": "approved",
                "execution_started": True,
                "execution_id": result.request_id if result else None,
            }
        else:
            request.status = ApprovalStatus.PARTIAL
            return {
                "status": "partial",
                "approved_count": len(request.approved_by),
                "required": request.required_approvals,
            }
    
    async def reject(
        self,
        request_id: str,
        user_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Reject an approval request.
        
        Args:
            request_id: Request to reject
            user_id: Rejecting user
            reason: Rejection reason
            
        Returns:
            Updated status
        """
        request = self._requests.get(request_id)
        if not request:
            return {"error": "Request not found"}
        
        request.rejected_by.append(user_id)
        request.status = ApprovalStatus.REJECTED
        request.updated_at = datetime.utcnow()
        
        request.comments.append({
            "user_id": user_id,
            "type": "rejection",
            "text": reason,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return {"status": "rejected", "reason": reason}
    
    async def modify_requirements(
        self,
        request_id: str,
        user_id: str,
        modifications: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Modify requirements before approval.
        
        Args:
            request_id: Request to modify
            user_id: Modifying user
            modifications: List of modifications
            
        Returns:
            Updated requirements
        """
        request = self._requests.get(request_id)
        if not request:
            return {"error": "Request not found"}
        
        # Apply modifications
        for mod in modifications:
            req_id = mod.get("requirement_id")
            for req in request.requirements:
                if req.get("id") == req_id:
                    if "title" in mod:
                        req["title"] = mod["title"]
                    if "description" in mod:
                        req["description"] = mod["description"]
                    if "priority" in mod:
                        req["priority"] = mod["priority"]
                    if "type" in mod:
                        req["type"] = mod["type"]
                    break
            else:
                # If no matching requirement and it's a new one
                if mod.get("action") == "add":
                    request.requirements.append({
                        "id": str(uuid.uuid4()),
                        "title": mod.get("title", ""),
                        "description": mod.get("description", ""),
                        "priority": mod.get("priority", "medium"),
                        "type": mod.get("type", "task"),
                    })
                elif mod.get("action") == "remove" and req_id:
                    request.requirements = [r for r in request.requirements if r.get("id") != req_id]
        
        # Track modification
        request.modifications.append({
            "user_id": user_id,
            "changes": modifications,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        request.updated_at = datetime.utcnow()
        
        return {
            "status": "modified",
            "requirements_count": len(request.requirements),
        }
    
    async def _execute(self, request: ApprovalRequest) -> Optional[ExecutionResult]:
        """Execute approved requirements.
        
        Args:
            request: Approved request
            
        Returns:
            Execution result
        """
        request.execution_status = TaskExecutionStatus.IN_PROGRESS
        request.execution_id = str(uuid.uuid4())
        
        result = ExecutionResult(
            request_id=request.id,
            status=TaskExecutionStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )
        
        # Call registered execution callbacks
        for callback in self._execution_callbacks:
            try:
                callback_result = await callback(request)
                # Merge results
                result.requirement_results.extend(callback_result.requirement_results)
                result.pull_requests.extend(callback_result.pull_requests)
                result.commits.extend(callback_result.commits)
            except Exception as e:
                result.errors.append(str(e))
        
        result.status = TaskExecutionStatus.COMPLETED if not result.errors else TaskExecutionStatus.FAILED
        result.completed_at = datetime.utcnow()
        
        if result.started_at:
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        
        request.execution_status = result.status
        
        return result
    
    def on_execution(
        self,
        callback: Callable[[ApprovalRequest], Awaitable[ExecutionResult]],
    ) -> None:
        """Register execution callback.
        
        Args:
            callback: Async function to execute approved requests
        """
        self._execution_callbacks.append(callback)
    
    def get_pending_for_user(self, user_id: str) -> List[ApprovalRequest]:
        """Get pending approvals for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of pending requests
        """
        return [
            r for r in self._requests.values()
            if r.status in [ApprovalStatus.PENDING, ApprovalStatus.PARTIAL]
            and user_id in r.approvers
            and user_id not in r.approved_by
            and user_id not in r.rejected_by
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        requests = list(self._requests.values())
        
        return {
            "total_requests": len(requests),
            "by_status": {
                status.value: len([r for r in requests if r.status == status])
                for status in ApprovalStatus
            },
            "by_source": {},
            "avg_approval_time_hours": self._calc_avg_approval_time(requests),
            "total_requirements_processed": sum(len(r.requirements) for r in requests if r.status == ApprovalStatus.APPROVED),
        }
    
    def _calc_avg_approval_time(self, requests: List[ApprovalRequest]) -> float:
        """Calculate average approval time."""
        approved = [r for r in requests if r.approved_at]
        if not approved:
            return 0.0
        
        total_hours = sum(
            (r.approved_at - r.created_at).total_seconds() / 3600
            for r in approved
        )
        return total_hours / len(approved)

