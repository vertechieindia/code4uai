"""API routes for Agent Manager."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from code4u.platform_core.agent_manager import AgentManager, NotificationService
from code4u.platform_core.agent_manager.manager import TaskSource, TaskPriority, TaskStatus, TaskFilter
from code4u.platform_core.agent_manager.session import SessionManager, DeviceType


router = APIRouter(prefix="/agent", tags=["agent-manager"])

# Instances
_managers: Dict[str, AgentManager] = {}
_notifications: Dict[str, NotificationService] = {}
_sessions = SessionManager()


def get_manager(tenant_id: str) -> AgentManager:
    if tenant_id not in _managers:
        _managers[tenant_id] = AgentManager(tenant_id)
    return _managers[tenant_id]


def get_notifications(tenant_id: str) -> NotificationService:
    if tenant_id not in _notifications:
        _notifications[tenant_id] = NotificationService(tenant_id)
    return _notifications[tenant_id]


# ============= Request/Response Models =============

class CreateTaskRequest(BaseModel):
    """Request to create a task."""
    intent: str
    description: str = ""
    source: str = "api"
    source_id: Optional[str] = None
    workspace_id: Optional[str] = None
    repository: Optional[str] = None
    priority: str = "normal"
    reviewers: List[str] = []
    notify_on_complete: List[str] = []
    notify_channel: Optional[str] = None


class TaskInfo(BaseModel):
    """Task info."""
    id: str
    intent: str
    status: str
    progress: float
    source: str
    created_at: str
    pull_request_url: Optional[str] = None


class TaskDetail(BaseModel):
    """Detailed task info."""
    id: str
    intent: str
    description: str
    status: str
    progress: float
    source: str
    steps: List[Dict[str, Any]]
    changes: List[Dict[str, Any]]
    analysis: Optional[str] = None
    pull_request_url: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class ReviewRequest(BaseModel):
    """Request to approve/reject."""
    user_id: str
    comment: Optional[str] = None
    reason: Optional[str] = None


class SessionRequest(BaseModel):
    """Request to create session."""
    user_id: str
    device_type: str = "web"
    device_name: Optional[str] = None


class SessionInfo(BaseModel):
    """Session info."""
    id: str
    device_type: str
    status: str
    active_task_id: Optional[str] = None


# ============= Task Endpoints =============

@router.post("/tasks", response_model=TaskInfo)
async def create_task(
    request: CreateTaskRequest,
    x_tenant_id: str = Header(default="default"),
    x_user_id: str = Header(default=None),
) -> TaskInfo:
    """Create a new agent task."""
    manager = get_manager(x_tenant_id)
    
    task = await manager.create_task(
        intent=request.intent,
        description=request.description,
        source=TaskSource(request.source),
        source_id=request.source_id,
        workspace_id=request.workspace_id,
        repository=request.repository,
        priority=TaskPriority(request.priority),
        reviewers=request.reviewers,
        created_by=x_user_id,
        notify_on_complete=request.notify_on_complete,
        notify_channel=request.notify_channel,
    )
    
    return TaskInfo(
        id=task.id,
        intent=task.intent,
        status=task.status.value,
        progress=task.progress,
        source=task.source.value,
        created_at=task.created_at.isoformat(),
        pull_request_url=task.pull_request_url,
    )


@router.get("/tasks", response_model=List[TaskInfo])
async def list_tasks(
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
    x_tenant_id: str = Header(default="default"),
) -> List[TaskInfo]:
    """List tasks."""
    manager = get_manager(x_tenant_id)
    
    filter = TaskFilter(
        status=[TaskStatus(status)] if status else None,
        source=TaskSource(source) if source else None,
        limit=limit,
    )
    
    tasks = manager.list_tasks(filter)
    
    return [
        TaskInfo(
            id=t.id,
            intent=t.intent,
            status=t.status.value,
            progress=t.progress,
            source=t.source.value,
            created_at=t.created_at.isoformat(),
            pull_request_url=t.pull_request_url,
        )
        for t in tasks
    ]


@router.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: str,
    x_tenant_id: str = Header(default="default"),
) -> TaskDetail:
    """Get task details."""
    manager = get_manager(x_tenant_id)
    task = manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskDetail(
        id=task.id,
        intent=task.intent,
        description=task.description,
        status=task.status.value,
        progress=task.progress,
        source=task.source.value,
        steps=[
            {"name": s.name, "status": s.status, "progress": s.progress}
            for s in task.steps
        ],
        changes=task.changes,
        analysis=task.analysis,
        pull_request_url=task.pull_request_url,
        created_at=task.created_at.isoformat(),
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        error_message=task.error_message,
    )


@router.post("/tasks/{task_id}/approve")
async def approve_task(
    task_id: str,
    request: ReviewRequest,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Approve a task."""
    manager = get_manager(x_tenant_id)
    
    try:
        task = await manager.approve_task(task_id, request.user_id, request.comment)
        return {"status": task.status.value, "approved_by": task.approved_by}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/reject")
async def reject_task(
    task_id: str,
    request: ReviewRequest,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Reject a task."""
    manager = get_manager(x_tenant_id)
    
    try:
        task = await manager.reject_task(task_id, request.user_id, request.reason or "No reason provided")
        return {"status": task.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, str]:
    """Cancel a task."""
    manager = get_manager(x_tenant_id)
    
    try:
        task = await manager.cancel_task(task_id)
        return {"status": task.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats")
async def get_stats(
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Get task statistics."""
    manager = get_manager(x_tenant_id)
    return manager.get_stats()


# ============= Session Endpoints =============

@router.post("/sessions", response_model=SessionInfo)
async def create_session(
    request: SessionRequest,
    x_tenant_id: str = Header(default="default"),
) -> SessionInfo:
    """Create a new session."""
    session = _sessions.create_session(
        user_id=request.user_id,
        tenant_id=x_tenant_id,
        device_type=DeviceType(request.device_type),
        device_name=request.device_name,
    )
    
    return SessionInfo(
        id=session.id,
        device_type=session.device_type.value,
        status=session.status.value,
        active_task_id=session.active_task_id,
    )


@router.get("/sessions/{user_id}")
async def get_user_sessions(
    user_id: str,
) -> List[SessionInfo]:
    """Get sessions for a user."""
    sessions = _sessions.get_active_sessions(user_id)
    
    return [
        SessionInfo(
            id=s.id,
            device_type=s.device_type.value,
            status=s.status.value,
            active_task_id=s.active_task_id,
        )
        for s in sessions
    ]


@router.get("/sessions/{user_id}/sync")
async def sync_state(user_id: str) -> Dict[str, Any]:
    """Sync state across user sessions."""
    return _sessions.sync_state(user_id)


# ============= Notification Endpoints =============

@router.get("/notifications")
async def get_notifications(
    user_id: str,
    unread_only: bool = False,
    limit: int = 50,
    x_tenant_id: str = Header(default="default"),
) -> List[Dict[str, Any]]:
    """Get notifications for a user."""
    service = get_notifications(x_tenant_id)
    notifications = service.get_notifications(user_id, unread_only, limit)
    
    return [
        {
            "id": n.id,
            "type": n.type.value,
            "title": n.title,
            "body": n.body,
            "read": n.read,
            "created_at": n.created_at.isoformat(),
            "action_url": n.action_url,
        }
        for n in notifications
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, bool]:
    """Mark notification as read."""
    service = get_notifications(x_tenant_id)
    result = service.mark_read(notification_id, user_id)
    return {"marked": result}


@router.post("/notifications/read-all")
async def mark_all_read(
    user_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, int]:
    """Mark all notifications as read."""
    service = get_notifications(x_tenant_id)
    count = service.mark_all_read(user_id)
    return {"marked": count}


@router.get("/notifications/count")
async def get_unread_count(
    user_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, int]:
    """Get unread notification count."""
    service = get_notifications(x_tenant_id)
    return {"count": service.get_unread_count(user_id)}

