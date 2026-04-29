"""API routes for Meeting AI and Approval Workflow."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from code4u.interfaces.integrations.meeting_ai import MeetingAssistant, RequirementPresenter
from code4u.interfaces.integrations.approval_workflow import ApprovalWorkflow, ApprovalStatus


router = APIRouter(prefix="/meeting", tags=["meeting-ai"])

# Shared instances
_assistants: Dict[str, MeetingAssistant] = {}
_workflows: Dict[str, ApprovalWorkflow] = {}


def get_assistant(tenant_id: str) -> MeetingAssistant:
    if tenant_id not in _assistants:
        _assistants[tenant_id] = MeetingAssistant(tenant_id)
    return _assistants[tenant_id]


def get_workflow(tenant_id: str) -> ApprovalWorkflow:
    if tenant_id not in _workflows:
        _workflows[tenant_id] = ApprovalWorkflow(tenant_id)
    return _workflows[tenant_id]


# ============= Request/Response Models =============

class JoinMeetingRequest(BaseModel):
    """Request to join a meeting."""
    meeting_url: str
    bot_name: str = "code4u.ai Assistant"


class MeetingSession(BaseModel):
    """Meeting session info."""
    id: str
    platform: str
    status: str
    participants: List[str]


class TranscriptEntry(BaseModel):
    """Transcript entry."""
    speaker: str
    text: str


class ProcessMeetingResponse(BaseModel):
    """Response from processing a meeting."""
    meeting_id: str
    summary: str
    key_points: List[str]
    decisions: List[str]
    action_items: List[Dict[str, Any]]
    requirements: List[Dict[str, Any]]


class PresentForApprovalRequest(BaseModel):
    """Request to present requirements for approval."""
    session_id: str
    channel: str
    platform: str = "slack"
    approvers: List[str]


class ApprovalActionRequest(BaseModel):
    """Approval action request."""
    user_id: str
    action: str  # approve, reject, modify
    comment: Optional[str] = None
    modifications: Optional[List[Dict[str, Any]]] = None


# ============= Meeting Endpoints =============

@router.post("/join", response_model=MeetingSession)
async def join_meeting(
    request: JoinMeetingRequest,
    x_tenant_id: str = Header(default="default"),
) -> MeetingSession:
    """Join a meeting."""
    assistant = get_assistant(x_tenant_id)
    
    try:
        session = await assistant.join_meeting(
            meeting_url=request.meeting_url,
            bot_name=request.bot_name,
        )
        
        return MeetingSession(
            id=session.id,
            platform=session.platform.value,
            status=session.status.value,
            participants=session.participants,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/start-transcription")
async def start_transcription(
    session_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, str]:
    """Start transcription for a meeting."""
    assistant = get_assistant(x_tenant_id)
    await assistant.start_transcription(session_id)
    return {"status": "transcription_started", "session_id": session_id}


@router.post("/{session_id}/transcript")
async def add_transcript(
    session_id: str,
    entry: TranscriptEntry,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, str]:
    """Add a transcript entry (for real-time transcription)."""
    assistant = get_assistant(x_tenant_id)
    await assistant.add_transcript_entry(session_id, entry.speaker, entry.text)
    return {"status": "added"}


@router.post("/{session_id}/process", response_model=ProcessMeetingResponse)
async def process_meeting(
    session_id: str,
    x_tenant_id: str = Header(default="default"),
) -> ProcessMeetingResponse:
    """Process a meeting to extract requirements."""
    assistant = get_assistant(x_tenant_id)
    
    try:
        minutes = await assistant.process_meeting(session_id)
        
        return ProcessMeetingResponse(
            meeting_id=session_id,
            summary=minutes.summary,
            key_points=minutes.key_points,
            decisions=minutes.decisions,
            action_items=minutes.action_items,
            requirements=[
                {
                    "id": req.id,
                    "title": req.title,
                    "description": req.description,
                    "type": req.type,
                    "priority": req.priority,
                }
                for req in minutes.requirements
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/leave")
async def leave_meeting(
    session_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, str]:
    """Leave a meeting."""
    assistant = get_assistant(x_tenant_id)
    await assistant.leave_meeting(session_id)
    return {"status": "left", "session_id": session_id}


@router.get("/sessions")
async def list_sessions(
    x_tenant_id: str = Header(default="default"),
) -> List[MeetingSession]:
    """List all meeting sessions."""
    assistant = get_assistant(x_tenant_id)
    
    return [
        MeetingSession(
            id=s.id,
            platform=s.platform.value,
            status=s.status.value,
            participants=s.participants,
        )
        for s in assistant.list_sessions()
    ]


# ============= Approval Workflow Endpoints =============

@router.post("/present-for-approval")
async def present_for_approval(
    request: PresentForApprovalRequest,
    background_tasks: BackgroundTasks,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Present extracted requirements for team approval."""
    assistant = get_assistant(x_tenant_id)
    workflow = get_workflow(x_tenant_id)
    
    session = assistant.get_session(request.session_id)
    if not session or not session.minutes:
        raise HTTPException(status_code=404, detail="Session or minutes not found")
    
    # Create approval request
    approval_request = workflow.create_request(
        source_type="meeting",
        source_id=request.session_id,
        title=session.minutes.meeting_title,
        requirements=[
            {
                "id": req.id,
                "title": req.title,
                "description": req.description,
                "type": req.type,
                "priority": req.priority,
            }
            for req in session.requirements
        ],
        approvers=request.approvers,
        description=session.minutes.summary,
        notification_channel=request.channel,
        notification_platform=request.platform,
    )
    
    return {
        "approval_id": approval_request.id,
        "status": approval_request.status.value,
        "requirements_count": len(approval_request.requirements),
        "approvers": approval_request.approvers,
    }


@router.post("/approval/{approval_id}/action")
async def handle_approval_action(
    approval_id: str,
    request: ApprovalActionRequest,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Handle an approval action (approve/reject/modify)."""
    workflow = get_workflow(x_tenant_id)
    
    if request.action == "approve":
        return await workflow.approve(approval_id, request.user_id, request.comment)
    elif request.action == "reject":
        return await workflow.reject(approval_id, request.user_id, request.comment or "No reason provided")
    elif request.action == "modify":
        if not request.modifications:
            raise HTTPException(status_code=400, detail="Modifications required")
        return await workflow.modify_requirements(approval_id, request.user_id, request.modifications)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")


@router.get("/approval/{approval_id}")
async def get_approval(
    approval_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Get approval request details."""
    workflow = get_workflow(x_tenant_id)
    request = workflow.get_request(approval_id)
    
    if not request:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    return {
        "id": request.id,
        "title": request.title,
        "source_type": request.source_type,
        "status": request.status.value,
        "requirements": request.requirements,
        "approvers": request.approvers,
        "approved_by": request.approved_by,
        "rejected_by": request.rejected_by,
        "comments": request.comments,
        "execution_status": request.execution_status.value if request.execution_status else None,
    }


@router.get("/approvals")
async def list_approvals(
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    x_tenant_id: str = Header(default="default"),
) -> List[Dict[str, Any]]:
    """List approval requests."""
    workflow = get_workflow(x_tenant_id)
    
    status_enum = ApprovalStatus(status) if status else None
    requests = workflow.list_requests(status=status_enum, source_type=source_type)
    
    return [
        {
            "id": r.id,
            "title": r.title,
            "source_type": r.source_type,
            "status": r.status.value,
            "requirements_count": len(r.requirements),
            "approved_count": len(r.approved_by),
            "required_approvals": r.required_approvals,
            "created_at": r.created_at.isoformat(),
        }
        for r in requests
    ]


@router.get("/approvals/pending")
async def get_pending_approvals(
    user_id: str,
    x_tenant_id: str = Header(default="default"),
) -> List[Dict[str, Any]]:
    """Get pending approvals for a user."""
    workflow = get_workflow(x_tenant_id)
    requests = workflow.get_pending_for_user(user_id)
    
    return [
        {
            "id": r.id,
            "title": r.title,
            "source_type": r.source_type,
            "requirements_count": len(r.requirements),
        }
        for r in requests
    ]


@router.get("/workflow/stats")
async def get_workflow_stats(
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Get workflow statistics."""
    workflow = get_workflow(x_tenant_id)
    return workflow.get_stats()

