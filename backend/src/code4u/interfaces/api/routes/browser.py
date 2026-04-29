"""API routes for browser agent."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import asyncio
import uuid

from code4u.platform_core.browser_agent import (
    BrowserAgent,
    BrowserTask,
    BrowserResult,
    BrowserConfig,
)


router = APIRouter(prefix="/browser", tags=["browser"])

# Active browser sessions
_sessions: Dict[str, BrowserAgent] = {}


class BrowserSessionRequest(BaseModel):
    """Request to create a browser session."""
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    allowed_domains: List[str] = []


class BrowserSessionResponse(BaseModel):
    """Response with session info."""
    session_id: str
    status: str


class NavigateRequest(BaseModel):
    """Request to navigate."""
    session_id: str
    url: str


class ClickRequest(BaseModel):
    """Request to click."""
    session_id: str
    selector: str


class TypeRequest(BaseModel):
    """Request to type."""
    session_id: str
    selector: str
    text: str
    submit: bool = False


class ScreenshotResponse(BaseModel):
    """Screenshot response."""
    screenshot_base64: str


class SnapshotResponse(BaseModel):
    """Page snapshot response."""
    url: str
    title: str
    text_preview: str
    elements_count: int


class TaskRequest(BaseModel):
    """Request for autonomous task."""
    description: str
    url: Optional[str] = None
    success_criteria: List[str] = []
    max_actions: int = 50
    timeout: float = 300.0


class TaskResponse(BaseModel):
    """Response for task execution."""
    task_id: str
    success: bool
    actions_taken: int
    error: Optional[str] = None
    extracted_data: Dict[str, Any] = {}


@router.post("/sessions", response_model=BrowserSessionResponse)
async def create_session(request: BrowserSessionRequest) -> BrowserSessionResponse:
    """Create a new browser session.
    
    Args:
        request: Session configuration
        
    Returns:
        Session info
    """
    session_id = str(uuid.uuid4())
    
    config = BrowserConfig(
        headless=request.headless,
        viewport_width=request.viewport_width,
        viewport_height=request.viewport_height,
        allowed_domains=request.allowed_domains,
    )
    
    agent = BrowserAgent(config=config)
    
    try:
        await agent.start()
        _sessions[session_id] = agent
        
        return BrowserSessionResponse(
            session_id=session_id,
            status="active",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def close_session(session_id: str) -> Dict[str, str]:
    """Close a browser session.
    
    Args:
        session_id: Session to close
        
    Returns:
        Status message
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    agent = _sessions.pop(session_id)
    await agent.stop()
    
    return {"status": "closed", "session_id": session_id}


@router.post("/sessions/{session_id}/navigate")
async def navigate(session_id: str, request: NavigateRequest) -> Dict[str, Any]:
    """Navigate to a URL.
    
    Args:
        session_id: Browser session
        request: Navigation request
        
    Returns:
        Action result
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    agent = _sessions[session_id]
    result = await agent.navigate(request.url)
    
    return {
        "success": result.success,
        "error": result.error,
        "duration_ms": result.duration_ms,
    }


@router.post("/sessions/{session_id}/click")
async def click(session_id: str, request: ClickRequest) -> Dict[str, Any]:
    """Click an element.
    
    Args:
        session_id: Browser session
        request: Click request
        
    Returns:
        Action result
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    agent = _sessions[session_id]
    result = await agent.click(request.selector)
    
    return {
        "success": result.success,
        "error": result.error,
        "duration_ms": result.duration_ms,
    }


@router.post("/sessions/{session_id}/type")
async def type_text(session_id: str, request: TypeRequest) -> Dict[str, Any]:
    """Type text into an element.
    
    Args:
        session_id: Browser session
        request: Type request
        
    Returns:
        Action result
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    agent = _sessions[session_id]
    result = await agent.type_text(request.selector, request.text)
    
    return {
        "success": result.success,
        "error": result.error,
        "duration_ms": result.duration_ms,
    }


@router.get("/sessions/{session_id}/screenshot", response_model=ScreenshotResponse)
async def screenshot(session_id: str) -> ScreenshotResponse:
    """Take a screenshot.
    
    Args:
        session_id: Browser session
        
    Returns:
        Base64 encoded screenshot
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    agent = _sessions[session_id]
    screenshot_b64 = await agent.screenshot()
    
    return ScreenshotResponse(screenshot_base64=screenshot_b64)


@router.get("/sessions/{session_id}/snapshot", response_model=SnapshotResponse)
async def get_snapshot(session_id: str) -> SnapshotResponse:
    """Get page snapshot.
    
    Args:
        session_id: Browser session
        
    Returns:
        Page snapshot info
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    agent = _sessions[session_id]
    snapshot = await agent.get_snapshot()
    
    return SnapshotResponse(
        url=snapshot.url,
        title=snapshot.title,
        text_preview=snapshot.text[:500] if snapshot.text else "",
        elements_count=len(snapshot.elements),
    )


@router.post("/task", response_model=TaskResponse)
async def execute_task(request: TaskRequest) -> TaskResponse:
    """Execute an autonomous browser task.
    
    Creates a temporary session, executes the task, and closes.
    
    Args:
        request: Task to execute
        
    Returns:
        Task execution result
    """
    task_id = str(uuid.uuid4())
    
    agent = BrowserAgent(config=BrowserConfig(headless=True))
    
    try:
        await agent.start()
        
        task = BrowserTask(
            id=task_id,
            description=request.description,
            url=request.url,
            success_criteria=request.success_criteria,
            max_actions=request.max_actions,
            timeout=request.timeout,
        )
        
        result = await agent.execute_task(task)
        
        return TaskResponse(
            task_id=task_id,
            success=result.success,
            actions_taken=result.total_actions,
            error=result.error,
            extracted_data=result.extracted_data,
        )
    finally:
        await agent.stop()


@router.post("/task/stream")
async def execute_task_stream(request: TaskRequest):
    """Execute task with streaming updates.
    
    Args:
        request: Task to execute
        
    Returns:
        Server-sent events stream
    """
    async def event_generator():
        task_id = str(uuid.uuid4())
        agent = BrowserAgent(config=BrowserConfig(headless=True))
        
        try:
            await agent.start()
            
            yield f"data: {json.dumps({'type': 'started', 'task_id': task_id})}\n\n"
            
            task = BrowserTask(
                id=task_id,
                description=request.description,
                url=request.url,
                success_criteria=request.success_criteria,
                max_actions=request.max_actions,
                timeout=request.timeout,
            )
            
            # Execute with action callbacks
            def on_action(action):
                pass  # Would send via SSE
            
            result = await agent.execute_task(task)
            
            yield f"data: {json.dumps({'type': 'complete', 'success': result.success, 'error': result.error})}\n\n"
            
        finally:
            await agent.stop()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.get("/health")
async def browser_health() -> Dict[str, Any]:
    """Health check for browser service."""
    return {
        "status": "healthy",
        "service": "browser",
        "active_sessions": len(_sessions),
    }

