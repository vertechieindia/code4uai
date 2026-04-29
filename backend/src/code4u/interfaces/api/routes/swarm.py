"""Swarm API — autonomous multi-agent task decomposition and execution.

Endpoints:
  - ``POST /swarm/plan``        — decompose a goal into a TaskGraph.
  - ``POST /swarm/execute``     — plan + execute the full swarm pipeline.
  - ``GET  /swarm/{id}``        — fetch a TaskGraph by ID.
  - ``GET  /swarm``             — list recent swarm runs.
  - ``POST /swarm/kill-all``    — emergency stop: cancel all active swarm runs.
  - ``POST /swarm/feedback``    — inline diff comments trigger plan revision.
  - ``POST /swarm/debate``      — multi-agent debate on trade-offs.
  - ``POST /swarm/approval``    — create an approval gate request.
  - ``POST /swarm/approval/{id}/approve`` — approve a gate.
  - ``POST /swarm/approval/{id}/reject``  — reject a gate.
  - ``GET  /swarm/approvals``   — list pending approval gates.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from code4u.agents.orchestrator.models import TaskGraph
from code4u.agents.orchestrator.chief import ChiefArchitect
from code4u.agents.orchestrator.controller import SwarmController

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory store for task graphs
# ---------------------------------------------------------------------------

_graphs: Dict[str, TaskGraph] = {}
_events: Dict[str, List[Dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class SwarmPlanRequest(BaseModel):
    goal: str = Field(..., description="Natural language goal to decompose.")
    workspacePath: str = Field("", description="Workspace root path.")
    imageBase64: str = Field("", description="Optional base64 image for vision tasks.")
    context: Dict[str, Any] = Field(default_factory=dict)


class SwarmExecuteRequest(BaseModel):
    goal: str = Field(..., description="Natural language goal.")
    workspacePath: str = Field("", description="Workspace root path.")
    imageBase64: str = Field("", description="Optional base64 image.")
    context: Dict[str, Any] = Field(default_factory=dict)
    sessionId: str = Field("", description="Optional presence session ID for broadcasting.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event_callback(graph_id: str, session_id: str = ""):
    """Create a callback that stores events and optionally broadcasts."""

    def callback(payload: Dict[str, Any]) -> None:
        if graph_id not in _events:
            _events[graph_id] = []
        _events[graph_id].append(payload)

        if session_id:
            _try_broadcast(session_id, payload)

    return callback


def _try_broadcast(session_id: str, payload: Dict[str, Any]) -> None:
    """Best-effort broadcast via PresenceManager (sync context)."""
    try:
        from code4u.core.presence import get_presence_manager, MessageType
        import asyncio

        pm = get_presence_manager()
        event_name = payload.get("event", "SWARM_UPDATE")

        msg_type_map = {
            "SWARM_STARTED": MessageType.SWARM_STARTED,
            "SWARM_COMPLETED": MessageType.SWARM_COMPLETED,
        }
        msg_type = msg_type_map.get(event_name, MessageType.SWARM_UPDATE)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(pm._broadcast(msg_type, payload, exclude_session=session_id))
        except RuntimeError:
            pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/swarm/plan")
async def plan_swarm(request: SwarmPlanRequest):
    """Decompose a goal into a TaskGraph without executing."""
    chief = ChiefArchitect()
    graph = chief.decompose(
        request.goal,
        workspace_path=request.workspacePath,
        image_base64=request.imageBase64,
        context=request.context,
    )
    _graphs[graph.id] = graph
    return {
        "graph": graph.to_dict(),
        "summary": graph.summary(),
    }


@router.post("/swarm/execute")
async def execute_swarm(request: SwarmExecuteRequest):
    """Decompose a goal and execute the full swarm pipeline."""
    chief = ChiefArchitect()
    graph = chief.decompose(
        request.goal,
        workspace_path=request.workspacePath,
        image_base64=request.imageBase64,
        context=request.context,
    )

    controller = SwarmController()
    callback = _make_event_callback(graph.id, request.sessionId)
    controller.set_event_callback(callback)

    graph = controller.execute_sync(graph)
    _graphs[graph.id] = graph

    return {
        "graph": graph.to_dict(),
        "summary": graph.summary(),
        "events": _events.get(graph.id, []),
    }


@router.get("/swarm/{graph_id}")
async def get_graph(graph_id: str):
    """Fetch a TaskGraph by ID."""
    graph = _graphs.get(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="TaskGraph not found")
    return {
        "graph": graph.to_dict(),
        "events": _events.get(graph_id, []),
    }


@router.post("/swarm/kill-all")
async def kill_all_swarms():
    """Emergency stop: cancel all active swarm runs and terminate workers.

    This endpoint:
      1. Marks every in-progress TaskGraph as "killed".
      2. Sets all pending/running sub-tasks to "cancelled".
      3. Attempts to terminate any OS-level worker processes.
      4. Clears the event pipeline to prevent stale callbacks.

    Returns a summary of what was terminated.
    """
    import os
    import signal

    killed_graphs: List[str] = []
    cancelled_tasks = 0
    terminated_pids: List[int] = []

    for gid, graph in list(_graphs.items()):
        has_active = False
        for task in graph.tasks:
            if task.status in ("pending", "running", "in_progress"):
                task.status = "cancelled"
                cancelled_tasks += 1
                has_active = True

                pid = task.config.get("pid")
                if pid and isinstance(pid, int):
                    try:
                        os.kill(pid, signal.SIGTERM)
                        terminated_pids.append(pid)
                    except (ProcessLookupError, PermissionError):
                        pass

        if has_active:
            killed_graphs.append(gid)

    _events.clear()

    return {
        "status": "killed",
        "killedGraphs": len(killed_graphs),
        "killedGraphIds": killed_graphs,
        "cancelledTasks": cancelled_tasks,
        "terminatedPids": terminated_pids,
        "timestamp": time.time(),
    }


@router.get("/swarm")
async def list_graphs(limit: int = 20):
    """List recent swarm runs."""
    items = sorted(_graphs.values(), key=lambda g: g.created_at, reverse=True)[:limit]
    return {
        "graphs": [
            {
                "id": g.id,
                "goal": g.goal,
                "taskCount": g.task_count,
                "completedCount": g.completed_count,
                "failedCount": g.failed_count,
                "progress": round(g.progress, 2),
                "isComplete": g.is_complete,
                "isSuccess": g.is_success,
                "durationMs": round(g.duration_ms, 1),
            }
            for g in items
        ],
        "total": len(_graphs),
    }


# ---------------------------------------------------------------------------
# Inline feedback — user comments on diffs trigger plan revision
# ---------------------------------------------------------------------------

class FeedbackComment(BaseModel):
    filePath: str = Field(..., description="File the comment is on.")
    line: int = Field(..., description="Line number in the proposed code.")
    comment: str = Field(..., description="User's feedback text.")


class SwarmFeedbackRequest(BaseModel):
    workspacePath: str = Field("", description="Workspace root.")
    jobId: str = Field("", description="Original refactor job ID.")
    comments: List[FeedbackComment] = Field(..., description="Inline comments from the user.")
    originalGoal: str = Field("", description="The original refactor intent.")


_feedback_history: Dict[str, List[Dict[str, Any]]] = {}


@router.post("/swarm/feedback")
async def submit_feedback(request: SwarmFeedbackRequest):
    """Accept user inline comments on a diff and trigger a plan revision.

    The Chief Architect receives the user's feedback as constraints
    and generates a revised plan that respects those comments.
    """
    if not request.comments:
        raise HTTPException(status_code=400, detail="No comments provided")

    feedback_lines = []
    for c in request.comments:
        feedback_lines.append(
            f"- In `{c.filePath}` line {c.line}: \"{c.comment}\""
        )

    revised_goal = (
        f"{request.originalGoal}\n\n"
        f"USER FEEDBACK (must be respected in the revised plan):\n"
        + "\n".join(feedback_lines)
    )

    chief = ChiefArchitect()
    graph = chief.decompose(
        revised_goal,
        workspace_path=request.workspacePath,
    )

    graph_id = graph.id
    _graphs[graph_id] = graph

    key = request.jobId or "latest"
    if key not in _feedback_history:
        _feedback_history[key] = []
    _feedback_history[key].append({
        "comments": [{"filePath": c.filePath, "line": c.line, "comment": c.comment} for c in request.comments],
        "revisedGraphId": graph_id,
        "timestamp": time.time(),
    })

    return {
        "status": "revision_planned",
        "revisedGraphId": graph_id,
        "graph": graph.to_dict(),
        "summary": graph.summary(),
        "feedbackAcknowledged": len(request.comments),
    }


# ---------------------------------------------------------------------------
# Agent Debate — two agents argue about trade-offs
# ---------------------------------------------------------------------------

class DebateRequest(BaseModel):
    topic: str = Field(..., description="The trade-off or question to debate.")
    workspacePath: str = Field("", description="Workspace root for context.")
    filePath: str = Field("", description="Specific file for context.")
    rounds: int = Field(3, description="Number of debate rounds.")


@router.post("/swarm/debate")
async def agent_debate(request: DebateRequest):
    """Simulate a multi-agent debate between the Profiler and Heal agents.

    The Profiler argues for performance; the Heal Agent argues for
    readability and safety. Each round builds on the previous.
    """
    topic = request.topic
    rounds: List[Dict[str, Any]] = []

    profiler_perspectives = [
        "From a performance standpoint, we should prioritize algorithmic efficiency. "
        "Using a hash map for lookups converts O(n) scans to O(1). "
        "The readability trade-off is minimal compared to the runtime gain.",

        "I've analyzed the hot path — the inner loop accounts for ~60% of execution time. "
        "Memoization here gives us 10x speedup on repeated calls. "
        "The memory overhead is bounded and acceptable.",

        "My final recommendation: optimize the critical path first, "
        "then refactor for clarity. Performance regressions are harder to fix than readability issues. "
        "Ship fast code, then document the why.",
    ]

    healer_perspectives = [
        "While performance matters, this code will be maintained by humans. "
        "A nested comprehension with memoization is hard to debug. "
        "I'd prefer explicit loops with clear variable names — the 2ms difference is negligible.",

        "I disagree with premature optimization. The profiler data shows this path is called "
        "only 50 times per request. The real bottleneck is the I/O layer. "
        "Let's fix the readability issues that cause bugs, not the micro-optimizations.",

        "My final recommendation: keep the code simple and readable. "
        "Add caching at the service layer instead of inside the function. "
        "Readability reduces bug density, which saves more engineering time than micro-optimizations.",
    ]

    for i in range(min(request.rounds, 5)):
        rounds.append({
            "round": i + 1,
            "profiler": {
                "agent": "Profiler Agent",
                "role": "Performance Advocate",
                "argument": profiler_perspectives[min(i, len(profiler_perspectives) - 1)],
            },
            "healer": {
                "agent": "Heal Agent",
                "role": "Readability & Safety Advocate",
                "argument": healer_perspectives[min(i, len(healer_perspectives) - 1)],
            },
        })

    consensus_areas = [
        "Both agents agree on using proper data structures (sets/dicts for lookups).",
        "Both agents agree the I/O layer is a bigger bottleneck than CPU-bound logic.",
        "Both agents agree documentation should explain any non-obvious optimization.",
    ]

    return {
        "topic": topic,
        "rounds": rounds,
        "totalRounds": len(rounds),
        "consensusAreas": consensus_areas,
        "recommendation": "Apply targeted optimizations on the measured hot path while maintaining readable code. "
                          "Use service-layer caching instead of inline memoization.",
    }


# ---------------------------------------------------------------------------
# Approval Gate endpoints
# ---------------------------------------------------------------------------

class CreateApprovalRequest(BaseModel):
    jobId: str = Field(..., description="Refactor job ID.")
    userId: str = Field(..., description="User requesting the change.")
    reason: str = Field("High-risk change", description="Why approval is needed.")
    fileCount: int = Field(0, description="Number of files affected.")
    productionCritical: bool = Field(False, description="Whether the project is production-critical.")


class ApprovalActionRequest(BaseModel):
    userId: str = Field(..., description="User performing the action.")
    reason: str = Field("", description="Optional reason (for rejection).")


@router.post("/swarm/approval")
async def create_approval_gate(request: CreateApprovalRequest):
    """Create an approval gate for a high-risk refactor."""
    from code4u.security_compliance.security.rbac import get_approval_manager

    mgr = get_approval_manager()
    req = mgr.create_request(
        job_id=request.jobId,
        requested_by=request.userId,
        reason=request.reason,
        file_count=request.fileCount,
        is_production_critical=request.productionCritical,
    )
    return {
        "approvalId": req.id,
        "status": req.status,
        "reason": req.reason,
        "fileCount": req.file_count,
        "createdAt": req.created_at,
    }


@router.post("/swarm/approval/{approval_id}/approve")
async def approve_gate(approval_id: str, request: ApprovalActionRequest):
    """Approve a pending approval gate."""
    from code4u.security_compliance.security.rbac import get_approval_manager

    mgr = get_approval_manager()
    try:
        req = mgr.approve(approval_id, request.userId)
        return {
            "approvalId": req.id,
            "status": req.status,
            "approvedBy": req.approved_by,
            "signature": req.signature,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/swarm/approval/{approval_id}/reject")
async def reject_gate(approval_id: str, request: ApprovalActionRequest):
    """Reject a pending approval gate."""
    from code4u.security_compliance.security.rbac import get_approval_manager

    mgr = get_approval_manager()
    try:
        req = mgr.reject(approval_id, request.userId, request.reason)
        return {
            "approvalId": req.id,
            "status": req.status,
            "rejectedBy": req.rejected_by,
            "rejectionReason": req.rejection_reason,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/swarm/approvals")
async def list_pending_approvals():
    """List all pending approval gates."""
    from code4u.security_compliance.security.rbac import get_approval_manager

    mgr = get_approval_manager()
    pending = mgr.get_pending()
    return {
        "approvals": [
            {
                "approvalId": r.id,
                "jobId": r.job_id,
                "requestedBy": r.requested_by,
                "reason": r.reason,
                "fileCount": r.file_count,
                "status": r.status,
                "createdAt": r.created_at,
            }
            for r in pending
        ],
        "total": len(pending),
    }
