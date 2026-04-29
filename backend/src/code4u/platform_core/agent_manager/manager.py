"""Agent Manager - Control agents from any interface."""

from __future__ import annotations
import uuid
import asyncio
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """Status of an agent task."""
    QUEUED = "queued"
    STARTING = "starting"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Priority of a task."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskSource(str, Enum):
    """Where the task was initiated."""
    IDE = "ide"
    WEB = "web"
    MOBILE = "mobile"
    CLI = "cli"
    SLACK = "slack"
    TEAMS = "teams"
    JIRA = "jira"
    SERVICENOW = "servicenow"
    MEETING = "meeting"
    API = "api"


@dataclass
class TaskStep:
    """A step in task execution."""
    id: str
    name: str
    status: str = "pending"
    
    # Progress
    progress: float = 0.0
    message: str = ""
    
    # Output
    output: Optional[Dict[str, Any]] = None
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class AgentTask:
    """A task being executed by an agent."""
    id: str
    tenant_id: str
    
    # What to do
    intent: str
    description: str = ""
    
    # Context
    source: TaskSource = TaskSource.API
    source_id: Optional[str] = None  # Jira ticket, Slack message, etc.
    
    # Workspace
    workspace_id: Optional[str] = None
    repository: Optional[str] = None
    branch: Optional[str] = None
    
    # Status
    status: TaskStatus = TaskStatus.QUEUED
    priority: TaskPriority = TaskPriority.NORMAL
    
    # Progress
    steps: List[TaskStep] = field(default_factory=list)
    current_step: int = 0
    progress: float = 0.0
    
    # Results
    analysis: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    changes: List[Dict[str, Any]] = field(default_factory=list)
    pull_request_url: Optional[str] = None
    
    # Review
    reviewers: List[str] = field(default_factory=list)
    approved_by: List[str] = field(default_factory=list)
    rejected_by: List[str] = field(default_factory=list)
    review_comments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Notifications
    notify_on_complete: List[str] = field(default_factory=list)
    notify_channel: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # User
    created_by: Optional[str] = None
    
    # Error
    error_message: Optional[str] = None


@dataclass
class TaskFilter:
    """Filter for listing tasks."""
    status: Optional[List[TaskStatus]] = None
    source: Optional[TaskSource] = None
    priority: Optional[TaskPriority] = None
    created_by: Optional[str] = None
    workspace_id: Optional[str] = None
    since: Optional[datetime] = None
    limit: int = 50


class AgentManager:
    """
    Central manager for agent tasks.
    
    Provides a unified interface for:
    - Creating tasks from any source
    - Monitoring progress in real-time
    - Approving/rejecting changes
    - Viewing history
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize agent manager.
        
        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id
        self._tasks: Dict[str, AgentTask] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._notification_service = None
    
    async def create_task(
        self,
        intent: str,
        description: str = "",
        source: TaskSource = TaskSource.API,
        source_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        repository: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        reviewers: Optional[List[str]] = None,
        created_by: Optional[str] = None,
        notify_on_complete: Optional[List[str]] = None,
        notify_channel: Optional[str] = None,
    ) -> AgentTask:
        """Create a new agent task.
        
        Args:
            intent: What to do (e.g., "Refactor user authentication")
            description: Additional details
            source: Where the request came from
            source_id: ID in source system
            workspace_id: Workspace to operate in
            repository: Repository URL
            priority: Task priority
            reviewers: Users who should review
            created_by: User who created the task
            notify_on_complete: Users to notify
            notify_channel: Channel for notifications
            
        Returns:
            Created task
        """
        task = AgentTask(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            intent=intent,
            description=description,
            source=source,
            source_id=source_id,
            workspace_id=workspace_id,
            repository=repository,
            priority=priority,
            reviewers=reviewers or [],
            created_by=created_by,
            notify_on_complete=notify_on_complete or [],
            notify_channel=notify_channel,
        )
        
        # Define standard steps
        task.steps = [
            TaskStep(id="1", name="Analyzing codebase"),
            TaskStep(id="2", name="Generating plan"),
            TaskStep(id="3", name="Validating changes"),
            TaskStep(id="4", name="Executing modifications"),
            TaskStep(id="5", name="Creating pull request"),
        ]
        
        self._tasks[task.id] = task
        
        # Start execution
        asyncio.create_task(self._execute_task(task))
        
        return task
    
    async def _execute_task(self, task: AgentTask) -> None:
        """Execute a task.
        
        Args:
            task: Task to execute
        """
        task.status = TaskStatus.STARTING
        task.started_at = datetime.utcnow()
        await self._notify_subscribers(task)
        
        try:
            # Step 1: Analyze
            task.status = TaskStatus.ANALYZING
            task.current_step = 0
            task.steps[0].status = "running"
            task.steps[0].started_at = datetime.utcnow()
            await self._notify_subscribers(task)
            
            # Would call Knowledge Graph analysis
            await asyncio.sleep(0.5)  # Simulated
            
            task.steps[0].status = "completed"
            task.steps[0].completed_at = datetime.utcnow()
            task.analysis = f"Analyzed codebase for: {task.intent}"
            task.progress = 0.2
            
            # Step 2: Plan
            task.status = TaskStatus.PLANNING
            task.current_step = 1
            task.steps[1].status = "running"
            task.steps[1].started_at = datetime.utcnow()
            await self._notify_subscribers(task)
            
            # Would call Planner Agent
            await asyncio.sleep(0.5)
            
            task.steps[1].status = "completed"
            task.steps[1].completed_at = datetime.utcnow()
            task.plan = {"steps": ["modify_file", "update_tests", "create_pr"]}
            task.progress = 0.4
            
            # Step 3: Validate
            task.current_step = 2
            task.steps[2].status = "running"
            task.steps[2].started_at = datetime.utcnow()
            await self._notify_subscribers(task)
            
            await asyncio.sleep(0.3)
            
            task.steps[2].status = "completed"
            task.steps[2].completed_at = datetime.utcnow()
            task.progress = 0.6
            
            # Step 4: Execute
            task.status = TaskStatus.EXECUTING
            task.current_step = 3
            task.steps[3].status = "running"
            task.steps[3].started_at = datetime.utcnow()
            await self._notify_subscribers(task)
            
            await asyncio.sleep(0.5)
            
            task.steps[3].status = "completed"
            task.steps[3].completed_at = datetime.utcnow()
            task.changes = [
                {"file": "src/auth.py", "additions": 15, "deletions": 8},
                {"file": "tests/test_auth.py", "additions": 25, "deletions": 0},
            ]
            task.progress = 0.8
            
            # Step 5: Create PR
            task.current_step = 4
            task.steps[4].status = "running"
            task.steps[4].started_at = datetime.utcnow()
            await self._notify_subscribers(task)
            
            await asyncio.sleep(0.3)
            
            task.steps[4].status = "completed"
            task.steps[4].completed_at = datetime.utcnow()
            task.pull_request_url = f"https://github.com/example/repo/pull/{uuid.uuid4().hex[:6]}"
            task.progress = 1.0
            
            # Await review if reviewers specified
            if task.reviewers:
                task.status = TaskStatus.AWAITING_REVIEW
            else:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
            
            await self._notify_subscribers(task)
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            await self._notify_subscribers(task)
    
    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)
    
    def list_tasks(
        self,
        filter: Optional[TaskFilter] = None,
    ) -> List[AgentTask]:
        """List tasks with optional filtering.
        
        Args:
            filter: Optional filter
            
        Returns:
            List of matching tasks
        """
        tasks = list(self._tasks.values())
        
        if filter:
            if filter.status:
                tasks = [t for t in tasks if t.status in filter.status]
            if filter.source:
                tasks = [t for t in tasks if t.source == filter.source]
            if filter.priority:
                tasks = [t for t in tasks if t.priority == filter.priority]
            if filter.created_by:
                tasks = [t for t in tasks if t.created_by == filter.created_by]
            if filter.workspace_id:
                tasks = [t for t in tasks if t.workspace_id == filter.workspace_id]
            if filter.since:
                tasks = [t for t in tasks if t.created_at >= filter.since]
            
            tasks = tasks[:filter.limit]
        
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    async def approve_task(
        self,
        task_id: str,
        user_id: str,
        comment: Optional[str] = None,
    ) -> AgentTask:
        """Approve a task.
        
        Args:
            task_id: Task to approve
            user_id: Approving user
            comment: Optional comment
            
        Returns:
            Updated task
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        if task.status != TaskStatus.AWAITING_REVIEW:
            raise ValueError(f"Task not awaiting review: {task.status}")
        
        task.approved_by.append(user_id)
        
        if comment:
            task.review_comments.append({
                "user_id": user_id,
                "type": "approval",
                "text": comment,
                "timestamp": datetime.utcnow().isoformat(),
            })
        
        # Check if all reviewers approved
        if set(task.approved_by) >= set(task.reviewers):
            task.status = TaskStatus.APPROVED
            task.completed_at = datetime.utcnow()
            
            # Would merge PR here
        
        await self._notify_subscribers(task)
        return task
    
    async def reject_task(
        self,
        task_id: str,
        user_id: str,
        reason: str,
    ) -> AgentTask:
        """Reject a task.
        
        Args:
            task_id: Task to reject
            user_id: Rejecting user
            reason: Rejection reason
            
        Returns:
            Updated task
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        task.rejected_by.append(user_id)
        task.status = TaskStatus.REJECTED
        task.completed_at = datetime.utcnow()
        
        task.review_comments.append({
            "user_id": user_id,
            "type": "rejection",
            "text": reason,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        await self._notify_subscribers(task)
        return task
    
    async def cancel_task(self, task_id: str) -> AgentTask:
        """Cancel a running task."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        
        await self._notify_subscribers(task)
        return task
    
    def subscribe(
        self,
        task_id: str,
        callback: Callable[[AgentTask], Awaitable[None]],
    ) -> None:
        """Subscribe to task updates.
        
        Args:
            task_id: Task to subscribe to
            callback: Async callback for updates
        """
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(callback)
    
    def unsubscribe(
        self,
        task_id: str,
        callback: Callable,
    ) -> None:
        """Unsubscribe from task updates."""
        if task_id in self._subscribers:
            self._subscribers[task_id] = [
                c for c in self._subscribers[task_id] if c != callback
            ]
    
    async def _notify_subscribers(self, task: AgentTask) -> None:
        """Notify subscribers of task update."""
        callbacks = self._subscribers.get(task.id, [])
        for callback in callbacks:
            try:
                await callback(task)
            except:
                pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get task statistics."""
        tasks = list(self._tasks.values())
        
        return {
            "total": len(tasks),
            "by_status": {
                status.value: len([t for t in tasks if t.status == status])
                for status in TaskStatus
            },
            "by_source": {
                source.value: len([t for t in tasks if t.source == source])
                for source in TaskSource
            },
            "completed_today": len([
                t for t in tasks
                if t.completed_at and t.completed_at.date() == datetime.utcnow().date()
            ]),
        }

