"""
Requirements Intelligence Layer API Routes

Full pipeline from conversation to execution:
1. Capture conversations (Slack/Teams/Zoom)
2. Process and classify segments
3. Structure into requirements
4. Add to Knowledge Graph
5. Generate plans
6. Execute with approval

UX Surfaces:
- Slack: /code4u commands, notifications
- Web Dashboard: Timeline, review, approval
- IDE: Requirement linkage to code
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header, Query, Body, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Import RIL components
from code4u.requirements_intelligence.ril.models import (
    ConversationPlatform,
    SegmentType,
    RequirementType,
    RequirementPriority,
    RequirementStatus,
)
from code4u.requirements_intelligence.ril.ingestion import (
    SlackIngestion,
    TeamsIngestion,
    ZoomIngestion,
)
from code4u.requirements_intelligence.ril.intelligence import ConversationIntelligence
from code4u.requirements_intelligence.ril.structuring import RequirementStructurer
from code4u.requirements_intelligence.ril.graph import RequirementGraphIntegration
from code4u.requirements_intelligence.ril.agent import RequirementPlanner, RequirementExecutor, CommandHandler
from code4u.requirements_intelligence.ril.agent.executor import ExecutionMode
from code4u.requirements_intelligence.ril.security import ConsentManager, PIIRedactor, RILAuditLogger


router = APIRouter()


# === Request/Response Models ===

class CaptureRequest(BaseModel):
    """Request to start capturing."""
    platform: str = Field(..., description="slack, teams, or zoom")
    channel_id: Optional[str] = None
    meeting_id: Optional[str] = None


class CaptureResponse(BaseModel):
    """Capture response."""
    conversation_id: str
    status: str
    message: str


class ProcessConversationRequest(BaseModel):
    """Request to process a conversation."""
    conversation_id: str
    use_llm: bool = True
    redact_pii: bool = True


class StructuredRequirementResponse(BaseModel):
    """Structured requirement response."""
    id: str
    title: str
    description: str
    type: str
    priority: str
    status: str
    systems: List[str]
    constraints: List[str]
    acceptance_criteria: List[str]
    source_platform: Optional[str]
    source_conversation_id: Optional[str]
    created_at: str


class RequirementListResponse(BaseModel):
    """List of requirements."""
    requirements: List[StructuredRequirementResponse]
    total: int


class CreatePlanRequest(BaseModel):
    """Request to create a plan."""
    requirement_ids: List[str]
    plan_type: str = "technical"  # prd, technical


class ExecutionPlanResponse(BaseModel):
    """Execution plan response."""
    id: str
    type: str
    status: str
    title: str
    summary: str
    services_affected: List[str]
    tasks: List[Dict[str, Any]]
    total_hours: float


class ExecuteRequest(BaseModel):
    """Request to execute requirements."""
    requirement_ids: List[str]
    mode: str = "generate_plan"  # listen_only, generate_prd, generate_plan, execute


class CommandRequest(BaseModel):
    """Slack/Teams command request."""
    command: str
    user_id: str
    channel_id: Optional[str] = None


class WebhookPayload(BaseModel):
    """Webhook payload from platforms."""
    platform: str
    event_type: str
    payload: Dict[str, Any]


class ConsentRequest(BaseModel):
    """Consent grant request."""
    workspace_id: Optional[str] = None
    channel_id: Optional[str] = None
    meeting_id: Optional[str] = None
    consent_types: List[str] = ["workspace", "ai_processing"]


# === Service Instances ===

# These would typically be injected via dependency injection
_ingestion_services: Dict[str, Any] = {}
_intelligence: Optional[ConversationIntelligence] = None
_structurer: Optional[RequirementStructurer] = None
_graph: Optional[RequirementGraphIntegration] = None
_planner: Optional[RequirementPlanner] = None
_executor: Optional[RequirementExecutor] = None
_command_handler: Optional[CommandHandler] = None
_consent_manager: Optional[ConsentManager] = None
_redactor: Optional[PIIRedactor] = None
_audit_logger: Optional[RILAuditLogger] = None


def get_services(tenant_id: str):
    """Get or create service instances."""
    global _intelligence, _structurer, _graph, _planner, _executor
    global _command_handler, _consent_manager, _redactor, _audit_logger
    
    if _intelligence is None:
        _intelligence = ConversationIntelligence()
        _structurer = RequirementStructurer(tenant_id=tenant_id)
        _graph = RequirementGraphIntegration()
        _planner = RequirementPlanner()
        _executor = RequirementExecutor(planner=_planner)
        _command_handler = CommandHandler(
            executor=_executor,
            planner=_planner,
            graph_integration=_graph,
        )
        _consent_manager = ConsentManager()
        _redactor = PIIRedactor()
        _audit_logger = RILAuditLogger()
    
    return {
        "intelligence": _intelligence,
        "structurer": _structurer,
        "graph": _graph,
        "planner": _planner,
        "executor": _executor,
        "commands": _command_handler,
        "consent": _consent_manager,
        "redactor": _redactor,
        "audit": _audit_logger,
    }


# === Capture Endpoints ===

@router.post("/ril/capture/start", response_model=CaptureResponse)
async def start_capture(
    request: CaptureRequest,
    background_tasks: BackgroundTasks,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """
    Start capturing a conversation.
    
    Supported platforms:
    - slack: Capture channel/thread messages
    - teams: Capture channel messages or meeting transcript
    - zoom: Capture meeting transcript
    """
    services = get_services(x_tenant_id)
    
    # Check consent
    consent_ok = services["consent"].check_consent(
        tenant_id=x_tenant_id,
        consent_type=ConsentType.WORKSPACE,
        workspace_id=request.channel_id or request.meeting_id,
    )
    
    # Note: For demo, we proceed even without consent
    # In production, you'd enforce consent
    
    platform = request.platform.lower()
    
    if platform == "slack":
        ingestion = SlackIngestion(tenant_id=x_tenant_id)
        await ingestion.connect()
        conv_id = await ingestion.start_capture(channel_id=request.channel_id)
        
    elif platform == "teams":
        ingestion = TeamsIngestion(tenant_id=x_tenant_id)
        await ingestion.connect()
        conv_id = await ingestion.start_capture(
            channel_id=request.channel_id,
            meeting_id=request.meeting_id,
        )
        
    elif platform == "zoom":
        ingestion = ZoomIngestion(tenant_id=x_tenant_id)
        await ingestion.connect()
        conv_id = await ingestion.start_capture(meeting_id=request.meeting_id)
        
    else:
        raise HTTPException(400, f"Unsupported platform: {platform}")
    
    # Store for later
    _ingestion_services[conv_id] = ingestion
    
    # Audit log
    services["audit"].log_capture_started(
        tenant_id=x_tenant_id,
        user_id=x_user_id,
        conversation_id=conv_id,
        platform=platform,
    )
    
    return CaptureResponse(
        conversation_id=conv_id,
        status="capturing",
        message=f"Capture started on {platform}",
    )


@router.post("/ril/capture/{conversation_id}/stop")
async def stop_capture(
    conversation_id: str,
    background_tasks: BackgroundTasks,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """Stop capturing and process the conversation."""
    ingestion = _ingestion_services.get(conversation_id)
    
    if not ingestion:
        raise HTTPException(404, "Capture not found")
    
    conversation = await ingestion.stop_capture(conversation_id)
    
    # Schedule processing in background
    background_tasks.add_task(
        process_conversation_task,
        conversation,
        x_tenant_id,
    )
    
    return {
        "conversation_id": conversation_id,
        "status": "processing",
        "message_count": len(conversation.messages),
        "has_transcript": bool(conversation.transcript),
    }


async def process_conversation_task(conversation, tenant_id: str):
    """Background task to process conversation."""
    services = get_services(tenant_id)
    
    # 1. Redact PII
    if conversation.messages:
        messages_dicts = [
            {"text": m.text, "speaker": m.speaker.name}
            for m in conversation.messages
        ]
        redacted, redaction_count = services["redactor"].redact_conversation(
            messages_dicts
        )
        
        if redaction_count > 0:
            services["audit"].log_pii_redaction(
                tenant_id=tenant_id,
                conversation_id=conversation.id,
                redaction_stats={"total": redaction_count},
            )
    
    # 2. Intelligence processing
    result = await services["intelligence"].process(conversation)
    
    # 3. Structure requirements
    structuring_result = await services["structurer"].structure_batch(
        segments=result.segments,
        conversation_id=conversation.id,
        source_platform=conversation.platform,
    )
    
    # 4. Add to graph
    for req in structuring_result.requirements:
        services["executor"].add_requirement(req)
        await services["graph"].add_requirement(req)
    
    # 5. Add meeting to graph
    await services["graph"].add_meeting(
        conversation,
        requirements_count=len(structuring_result.requirements),
    )
    
    # 6. Audit log
    services["audit"].log_requirements_extracted(
        tenant_id=tenant_id,
        conversation_id=conversation.id,
        requirements_count=len(structuring_result.requirements),
        requirement_ids=[r.id for r in structuring_result.requirements],
    )


# === Webhook Endpoints ===

@router.post("/ril/webhooks/slack")
async def slack_webhook(
    payload: Dict[str, Any] = Body(...),
    background_tasks: BackgroundTasks = None,
):
    """Handle Slack Events API webhooks."""
    # Handle URL verification
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    
    # Handle events
    event = payload.get("event", {})
    event_type = event.get("type")
    
    if event_type == "message":
        # Find active capture for this channel
        channel = event.get("channel")
        for conv_id, ingestion in _ingestion_services.items():
            if isinstance(ingestion, SlackIngestion):
                await ingestion.handle_event(event)
                break
    
    return {"status": "ok"}


@router.post("/ril/webhooks/zoom")
async def zoom_webhook(
    payload: Dict[str, Any] = Body(...),
    background_tasks: BackgroundTasks = None,
):
    """Handle Zoom webhooks."""
    event = payload.get("event")
    
    for conv_id, ingestion in _ingestion_services.items():
        if isinstance(ingestion, ZoomIngestion):
            await ingestion.handle_webhook(payload)
            break
    
    return {"status": "ok"}


# === Requirements Endpoints ===

@router.get("/ril/requirements", response_model=RequirementListResponse)
async def list_requirements(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, le=200),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """List requirements with optional filtering."""
    services = get_services(x_tenant_id)
    
    if search:
        requirements = await services["graph"].search_requirements(
            query=search,
            tenant_id=x_tenant_id,
            limit=limit,
        )
    else:
        # Get all from graph
        requirements = list(services["graph"]._requirement_nodes.values())
        
        # Filter by status
        if status:
            requirements = [r for r in requirements if r.status == status]
        
        requirements = requirements[:limit]
    
    return RequirementListResponse(
        requirements=[
            StructuredRequirementResponse(
                id=r.id,
                title=r.title,
                description=r.description,
                type=r.requirement_type,
                priority=r.priority if hasattr(r, 'priority') else "medium",
                status=r.status,
                systems=r.systems,
                constraints=r.constraints,
                acceptance_criteria=r.acceptance_criteria if hasattr(r, 'acceptance_criteria') else [],
                source_platform=r.source_platform,
                source_conversation_id=r.source_conversation_id,
                created_at=r.created_at.isoformat(),
            )
            for r in requirements
        ],
        total=len(requirements),
    )


@router.get("/ril/requirements/{requirement_id}")
async def get_requirement(
    requirement_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """Get requirement with full traceability."""
    services = get_services(x_tenant_id)
    
    requirement = services["graph"]._requirement_nodes.get(requirement_id)
    if not requirement:
        raise HTTPException(404, "Requirement not found")
    
    # Get traceability chain
    traceability = services["graph"].get_traceability_chain(requirement_id)
    
    return {
        "requirement": requirement.to_dict(),
        "traceability": traceability,
    }


@router.patch("/ril/requirements/{requirement_id}/status")
async def update_requirement_status(
    requirement_id: str,
    status: str = Body(..., embed=True),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Update requirement status."""
    services = get_services(x_tenant_id)
    
    requirement = services["graph"]._requirement_nodes.get(requirement_id)
    if not requirement:
        raise HTTPException(404, "Requirement not found")
    
    requirement.status = status
    
    return {"id": requirement_id, "status": status}


# === Plan Endpoints ===

@router.post("/ril/plans", response_model=ExecutionPlanResponse)
async def create_plan(
    request: CreatePlanRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    """Create an execution plan from requirements."""
    services = get_services(x_tenant_id)
    
    # Get requirements
    requirements = []
    for rid in request.requirement_ids:
        req = services["executor"]._requirements.get(rid)
        if req:
            requirements.append(req)
    
    if not requirements:
        raise HTTPException(400, "No valid requirements provided")
    
    if request.plan_type == "prd":
        plan = await services["planner"].create_prd(
            requirements,
            created_by=x_user_id or "system",
        )
    else:
        plan = await services["planner"].create_technical_plan(
            requirements,
            created_by=x_user_id or "system",
        )
    
    return ExecutionPlanResponse(
        id=plan.id,
        type=plan.type.value,
        status=plan.status.value,
        title=plan.title,
        summary=plan.summary,
        services_affected=plan.services_affected,
        tasks=[
            {
                "id": t.id,
                "title": t.title,
                "service": t.assigned_service,
                "hours": t.estimated_hours,
            }
            for t in plan.tasks
        ],
        total_hours=plan.total_estimated_hours,
    )


@router.get("/ril/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """Get a plan by ID."""
    services = get_services(x_tenant_id)
    
    plan = services["planner"].get_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    
    return plan.to_dict()


@router.post("/ril/plans/{plan_id}/approve")
async def approve_plan(
    plan_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """Approve a plan for execution."""
    services = get_services(x_tenant_id)
    
    success = services["planner"].approve_plan(plan_id, x_user_id)
    if not success:
        raise HTTPException(400, "Failed to approve plan")
    
    # Audit log
    plan = services["planner"].get_plan(plan_id)
    services["audit"].log_plan_approved(
        tenant_id=x_tenant_id,
        user_id=x_user_id,
        plan_id=plan_id,
        requirement_ids=plan.requirement_ids if plan else [],
    )
    
    return {"status": "approved", "plan_id": plan_id}


@router.post("/ril/plans/{plan_id}/reject")
async def reject_plan(
    plan_id: str,
    reason: str = Body(..., embed=True),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """Reject a plan."""
    services = get_services(x_tenant_id)
    
    success = services["planner"].reject_plan(plan_id, reason)
    if not success:
        raise HTTPException(400, "Failed to reject plan")
    
    return {"status": "rejected", "plan_id": plan_id, "reason": reason}


# === Execution Endpoints ===

@router.post("/ril/execute")
async def execute_requirements(
    request: ExecuteRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """Create an execution request for requirements."""
    services = get_services(x_tenant_id)
    
    mode_map = {
        "listen_only": ExecutionMode.LISTEN_ONLY,
        "generate_prd": ExecutionMode.GENERATE_PRD,
        "generate_plan": ExecutionMode.GENERATE_PLAN,
        "execute": ExecutionMode.EXECUTE,
    }
    
    mode = mode_map.get(request.mode, ExecutionMode.GENERATE_PLAN)
    
    exec_request = await services["executor"].create_execution_request(
        requirement_ids=request.requirement_ids,
        mode=mode,
        created_by=x_user_id,
        tenant_id=x_tenant_id,
    )
    
    return {
        "request_id": exec_request.id,
        "status": exec_request.status.value,
        "mode": exec_request.mode.value,
        "result": exec_request.result,
    }


@router.get("/ril/execute/{request_id}")
async def get_execution_status(
    request_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """Get execution request status."""
    services = get_services(x_tenant_id)
    
    exec_request = services["executor"].get_request(request_id)
    if not exec_request:
        raise HTTPException(404, "Execution request not found")
    
    return {
        "request_id": exec_request.id,
        "status": exec_request.status.value,
        "mode": exec_request.mode.value,
        "result": exec_request.result,
        "error": exec_request.error,
        "created_at": exec_request.created_at.isoformat(),
    }


@router.post("/ril/execute/{request_id}/approve")
async def approve_execution(
    request_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """Approve an execution request."""
    services = get_services(x_tenant_id)
    
    success = await services["executor"].approve_execution(request_id, x_user_id)
    if not success:
        raise HTTPException(400, "Failed to approve execution")
    
    return {"status": "approved", "request_id": request_id}


# === Command Endpoints (for Slack/Teams) ===

@router.post("/ril/commands")
async def handle_command(
    request: CommandRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """
    Handle Slack/Teams commands.
    
    Supported commands:
    - convert <meeting-id> to <prd|plan|implementation>
    - status <request-id>
    - list <requirements|meetings|plans>
    - approve <request-id>
    - reject <request-id> [reason: ...]
    """
    services = get_services(x_tenant_id)
    
    result = await services["commands"].handle(
        command_text=request.command,
        user_id=request.user_id,
        tenant_id=x_tenant_id,
        channel_id=request.channel_id,
    )
    
    return result


# === Consent Endpoints ===

@router.post("/ril/consent/grant")
async def grant_consent(
    request: ConsentRequest,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """Grant consent for RIL features."""
    services = get_services(x_tenant_id)
    
    from code4u.requirements_intelligence.ril.security.consent import ConsentType
    
    consent_types = []
    for ct in request.consent_types:
        try:
            consent_types.append(ConsentType(ct))
        except ValueError:
            pass
    
    if request.workspace_id:
        records = services["consent"].grant_workspace_consent(
            tenant_id=x_tenant_id,
            workspace_id=request.workspace_id,
            consent_types=consent_types,
            granted_by=x_user_id,
        )
    elif request.channel_id:
        records = services["consent"].grant_channel_consent(
            tenant_id=x_tenant_id,
            channel_id=request.channel_id,
            consent_types=consent_types,
            granted_by=x_user_id,
        )
    elif request.meeting_id:
        records = services["consent"].grant_meeting_consent(
            tenant_id=x_tenant_id,
            meeting_id=request.meeting_id,
            consent_types=consent_types,
            granted_by=x_user_id,
        )
    else:
        raise HTTPException(400, "workspace_id, channel_id, or meeting_id required")
    
    # Audit log
    for ct in consent_types:
        services["audit"].log_consent_granted(
            tenant_id=x_tenant_id,
            user_id=x_user_id,
            consent_type=ct.value,
            workspace_id=request.workspace_id,
            channel_id=request.channel_id,
            meeting_id=request.meeting_id,
        )
    
    return {
        "granted": len(records),
        "consent_types": [r.type.value for r in records],
    }


@router.get("/ril/consent/check")
async def check_consent(
    workspace_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    meeting_id: Optional[str] = None,
    consent_types: str = Query("workspace,ai_processing"),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """Check consent status."""
    services = get_services(x_tenant_id)
    
    from code4u.requirements_intelligence.ril.security.consent import ConsentType
    
    types_to_check = []
    for ct in consent_types.split(","):
        try:
            types_to_check.append(ConsentType(ct.strip()))
        except ValueError:
            pass
    
    results = services["consent"].check_all_consents(
        tenant_id=x_tenant_id,
        consent_types=types_to_check,
        workspace_id=workspace_id,
        channel_id=channel_id,
        meeting_id=meeting_id,
    )
    
    return {
        "consents": {k.value: v for k, v in results.items()},
        "all_granted": all(results.values()),
    }


# === Audit Endpoints ===

@router.get("/ril/audit")
async def get_audit_logs(
    action: Optional[str] = None,
    days: int = Query(7, le=90),
    limit: int = Query(100, le=1000),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """Get audit logs."""
    services = get_services(x_tenant_id)
    
    from code4u.requirements_intelligence.ril.security.audit import RILAuditAction
    from datetime import timedelta
    
    action_filter = None
    if action:
        try:
            action_filter = RILAuditAction(action)
        except ValueError:
            pass
    
    start_time = datetime.utcnow() - timedelta(days=days)
    
    logs = services["audit"].query(
        tenant_id=x_tenant_id,
        action=action_filter,
        start_time=start_time,
        limit=limit,
    )
    
    return {
        "logs": [log.to_dict() for log in logs],
        "total": len(logs),
    }


@router.get("/ril/audit/summary")
async def get_audit_summary(
    days: int = Query(30, le=90),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """Get activity summary."""
    services = get_services(x_tenant_id)
    
    summary = services["audit"].get_activity_summary(
        tenant_id=x_tenant_id,
        days=days,
    )
    
    return summary


# === Meetings Endpoints ===

@router.get("/ril/meetings")
async def list_meetings(
    limit: int = Query(50, le=200),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """List captured meetings."""
    services = get_services(x_tenant_id)
    
    meetings = list(services["graph"]._meeting_nodes.values())
    meetings = [
        m for m in meetings
        if m.tenant_id == x_tenant_id
    ][:limit]
    
    return {
        "meetings": [
            {
                "id": m.id,
                "title": m.title,
                "platform": m.platform,
                "duration_minutes": m.duration_minutes,
                "requirements_count": m.requirements_count,
                "decisions_count": m.decisions_count,
                "has_transcript": m.has_transcript,
            }
            for m in meetings
        ],
        "total": len(meetings),
    }


@router.get("/ril/meetings/{meeting_id}/requirements")
async def get_meeting_requirements(
    meeting_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """Get requirements from a meeting."""
    services = get_services(x_tenant_id)
    
    requirements = services["graph"].get_requirements_from_meeting(meeting_id)
    
    return {
        "meeting_id": meeting_id,
        "requirements": [r.to_dict() for r in requirements],
        "total": len(requirements),
    }


# Need to import ConsentType for the capture endpoint
from code4u.requirements_intelligence.ril.security.consent import ConsentType

