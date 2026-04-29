from __future__ import annotations
"""Refactoring API routes for code4u.ai.

Provides two modes of operation:

  **Synchronous** — ``POST /refactor`` and ``POST /refactor/rename``
      block until the full pipeline completes and return the result.

  **Asynchronous (polling)** — ``POST /refactor/jobs`` or
      ``POST /refactor/rename/jobs`` start the pipeline in the background
      and return a ``jobId``.  The frontend polls
      ``GET /refactor/jobs/{job_id}`` to observe state-machine transitions
      in real time.

All endpoints use the real ``PlanExecutor`` — no mocks, no setTimeout.
"""

import asyncio
import base64
import traceback
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from code4u.code_intelligence.context.compiler import ContextCompiler
from code4u.code_intelligence.context.planner import plan_from_blast_context
from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    DependencyMap,
    SymbolIndexer,
)
from code4u.platform_core.agents.orchestrator import PlanExecutor
from code4u.platform_core.agents.session_manager import (
    SessionManager,
    Session,
    RefactorJobRecord,
    DependencySnapshot,
)
from code4u.platform_core.agents.sentinel import (
    WorkspaceSentinel,
    WorkspaceBusyError,
)
from code4u.interfaces.api.routes.events import make_status_callback, push_event

router = APIRouter()


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_dep_maps: Dict[str, DependencyMap] = {}
_indexer = SymbolIndexer()
_session_mgr = SessionManager()
_sentinel = WorkspaceSentinel()

_MULTI_ROOT_KEY = "__multi_root__"
_DEFAULT_USER = "local_user"


def _get_or_build_dep_map(workspace_path: str) -> DependencyMap:
    """Return a cached ``DependencyMap`` for *workspace_path*, indexing on first call."""
    resolved = str(Path(workspace_path).resolve())
    if resolved not in _dep_maps:
        _dep_maps[resolved] = _indexer.index_workspace(resolved)
    return _dep_maps[resolved]


def _get_or_build_multi_dep_map(workspace_paths: List[str]) -> DependencyMap:
    """Return a cached ``DependencyMap`` spanning multiple workspace roots."""
    resolved = [str(Path(wp).resolve()) for wp in workspace_paths]
    cache_key = _MULTI_ROOT_KEY + "|".join(sorted(resolved))
    if cache_key not in _dep_maps:
        _dep_maps[cache_key] = _indexer.index_multi_workspace(resolved)
    return _dep_maps[cache_key]


def _get_compiler(workspace_path: str) -> ContextCompiler:
    """Return a ``ContextCompiler`` wired to the ``DependencyMap`` for *workspace_path*."""
    dep_map = _get_or_build_dep_map(workspace_path)
    return ContextCompiler(dependency_map=dep_map)


def _get_multi_compiler(workspace_paths: List[str]) -> ContextCompiler:
    """Return a ``ContextCompiler`` wired to a multi-root ``DependencyMap``."""
    dep_map = _get_or_build_multi_dep_map(workspace_paths)
    return ContextCompiler(dependency_map=dep_map)


def _get_plan_executor(
    workspace_path: str = ".",
    dry_run: bool = False,
    status_callback: Any = None,
) -> PlanExecutor:
    """Return a **new** ``PlanExecutor`` per job for state isolation."""
    dep_map = _get_or_build_dep_map(workspace_path)
    return PlanExecutor(
        dependency_map=dep_map,
        dry_run=dry_run,
        status_callback=status_callback,
    )


def _get_multi_plan_executor(
    workspace_paths: List[str],
    dry_run: bool = False,
) -> PlanExecutor:
    """Return a ``PlanExecutor`` backed by a multi-root ``DependencyMap``."""
    dep_map = _get_or_build_multi_dep_map(workspace_paths)
    return PlanExecutor(dependency_map=dep_map, dry_run=dry_run)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RefactorRequest(BaseModel):
    """Payload for ``POST /refactor``."""
    intent: str = Field(..., min_length=1, description="Natural-language refactor intent.")
    filePath: str = Field(..., min_length=1, description="Primary file path (absolute or workspace-relative).")
    workspacePath: Optional[str] = Field(None, description="Repository root. Defaults to '.'.")
    selection: Optional[Dict[str, Any]] = Field(None, description="Reserved for future line-range selection.")
    context: Dict[str, Any] = Field(default_factory=dict, description="Reserved for future extra context.")


class RenameRequest(BaseModel):
    """Payload for ``POST /refactor/rename``."""
    oldName: str = Field(..., min_length=1, description="Current symbol name.")
    newName: str = Field(..., min_length=1, description="Desired new symbol name.")
    filePath: str = Field(..., min_length=1, description="Primary file path.")
    workspacePath: Optional[str] = Field(None, description="Repository root. Defaults to '.'.")


class RefactorResponse(BaseModel):
    """Response for synchronous refactor endpoints."""
    success: bool
    state: str = Field(description="Terminal PlanExecutionState (e.g. APPLIED).")
    executionId: str = Field(description="Unique execution identifier.")
    affectedFiles: List[str] = Field(default_factory=list)
    diffs: Dict[str, str] = Field(default_factory=dict, description="file_path → unified diff.")
    breakingChange: bool = False
    stateHistory: List[Dict[str, Any]] = Field(default_factory=list)
    proposedPlan: Optional[Dict[str, Any]] = Field(None, description="Structured plan of operations.")
    error: Optional[str] = None


class SessionRefactorRequest(BaseModel):
    """Payload for ``POST /refactor/session`` — session-aware refactor.

    When ``sessionId`` is provided, the system loads the session context
    (previous intents, diffs, plan summaries) and injects them into the
    LLM prompt so follow-up intents are contextually aware.
    """
    intent: str = Field(..., min_length=1, description="Refactor intent (can be a follow-up).")
    filePath: str = Field(..., min_length=1, description="Primary file path.")
    workspacePath: Optional[str] = Field(None, description="Repository root. Defaults to '.'.")
    sessionId: Optional[str] = Field(None, description="Existing session ID for follow-ups. Omit to create a new session.")
    userId: Optional[str] = Field(None, description="User identifier for multi-tenant isolation. Defaults to 'local_user'.")
    dryRun: bool = Field(default=False, description="Preview without writing (default: false).")


class SessionResponse(BaseModel):
    """Response that includes session metadata alongside the refactor result."""
    success: bool
    sessionId: str = Field(description="Session ID (use for follow-up requests).")
    state: str = Field(description="Terminal PlanExecutionState.")
    executionId: str = Field(description="Unique execution identifier.")
    affectedFiles: List[str] = Field(default_factory=list)
    diffs: Dict[str, str] = Field(default_factory=dict)
    breakingChange: bool = False
    stateHistory: List[Dict[str, Any]] = Field(default_factory=list)
    proposedPlan: Optional[Dict[str, Any]] = Field(None)
    sessionSummary: Optional[Dict[str, Any]] = Field(None, description="Session history and context.")
    error: Optional[str] = None


class MultiRootRefactorRequest(BaseModel):
    """Payload for ``POST /refactor/multi-root``.

    Spans multiple workspace roots in a single atomic refactor.
    """
    intent: str = Field(..., min_length=1, description="Natural-language refactor intent.")
    filePath: str = Field(..., min_length=1, description="Primary file path (absolute or relative to first root).")
    workspacePaths: List[str] = Field(..., min_items=1, description="List of workspace root directories.")


class VisualRefactorRequest(BaseModel):
    """Payload for ``POST /refactor/visual`` (JSON mode).

    Accepts a base64-encoded image alongside the refactor intent.
    For ``multipart/form-data`` uploads, use the separate endpoint
    signature that accepts ``UploadFile``.
    """
    intent: str = Field(default="", description="Optional refactor intent. If empty, the AI infers from the image.")
    filePath: Optional[str] = Field(None, description="Primary file path (optional — visual grounding may auto-detect).")
    workspacePath: Optional[str] = Field(None, description="Repository root. Defaults to '.'.")
    imageBase64: str = Field(..., min_length=1, description="Base64-encoded image (PNG/JPEG/WebP).")
    mediaType: str = Field(default="image/png", description="MIME type of the image.")
    dryRun: bool = Field(default=True, description="Preview without writing (default: true).")


class DryRunRequest(BaseModel):
    """Payload for ``POST /refactor/dry-run``."""
    intent: str = Field(..., min_length=1, description="Natural-language refactor intent.")
    filePath: str = Field(..., min_length=1, description="Primary file path.")
    workspacePath: Optional[str] = Field(None, description="Repository root. Defaults to '.'.")


class JobCreatedResponse(BaseModel):
    """Response for async job-creation endpoints."""
    jobId: str


class JobStatus(str, Enum):
    """High-level status of an async refactor job."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobStatusResponse(BaseModel):
    """Response for ``GET /refactor/jobs/{job_id}``."""
    jobId: str
    status: str
    state: str = Field(description="Current PlanExecutionState.")
    stateHistory: List[Dict[str, Any]] = Field(default_factory=list)
    affectedFiles: List[str] = Field(default_factory=list)
    diffs: Dict[str, str] = Field(default_factory=dict)
    breakingChange: bool = False
    executionId: str = ""
    error: Optional[str] = None
    createdAt: str = ""


# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

class _RefactorJob:
    """Tracks one async refactor execution."""

    __slots__ = (
        "job_id", "status", "executor", "affected_files",
        "breaking_change", "error", "created_at", "intent",
    )

    def __init__(self, job_id: str, intent: str) -> None:
        self.job_id: str = job_id
        self.intent: str = intent
        self.status: JobStatus = JobStatus.PENDING
        self.executor: Optional[PlanExecutor] = None
        self.affected_files: List[str] = []
        self.breaking_change: bool = False
        self.error: Optional[str] = None
        self.created_at: str = datetime.now(timezone.utc).isoformat()


_jobs: Dict[str, _RefactorJob] = {}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_refactor_request(intent: str, file_path: str) -> None:
    """Raise 400 if required fields are missing or blank."""
    if not file_path or not str(file_path).strip():
        raise HTTPException(status_code=400, detail="filePath is required")
    if not intent or not str(intent).strip():
        raise HTTPException(status_code=400, detail="intent is required")


def _validate_rename_request(request: RenameRequest) -> None:
    """Raise 400 if rename fields are missing or blank."""
    if not request.filePath or not str(request.filePath).strip():
        raise HTTPException(status_code=400, detail="filePath is required")
    if not request.oldName or not str(request.oldName).strip():
        raise HTTPException(status_code=400, detail="oldName is required")
    if not request.newName or not str(request.newName).strip():
        raise HTTPException(status_code=400, detail="newName is required")


# ---------------------------------------------------------------------------
# Core pipeline runner (shared by sync and async paths)
# ---------------------------------------------------------------------------

async def _run_pipeline(
    intent: str,
    file_path: str,
    workspace_path: str,
    executor: PlanExecutor,
) -> tuple[List[str], bool, Dict[str, str], Optional[Dict[str, Any]]]:
    """Compile context, build plan, execute pipeline.

    Returns:
        Tuple of (affected_files, breaking_change, diffs, proposed_plan_summary).
    """
    compiler = _get_compiler(workspace_path)
    blast_context = await compiler.compile_refactor_blast_context(
        intent=intent,
        primary_file_path=file_path,
        workspace_path=workspace_path,
    )
    plan = plan_from_blast_context(blast_context)
    await executor.run(plan, blast_context, intent=intent)

    affected = list(plan.affected_files)
    # Include newly created files in the affected list
    if executor.proposed_plan:
        for new_file in executor.proposed_plan.files_to_create:
            if new_file not in affected:
                affected.append(new_file)

    breaking = plan.metadata.get("has_cross_owner", False)
    diffs = executor.diffs
    plan_summary = executor.proposed_plan.summary if executor.proposed_plan else None
    return affected, breaking, diffs, plan_summary


# ---------------------------------------------------------------------------
# Synchronous endpoints
# ---------------------------------------------------------------------------

@router.post("/refactor", response_model=RefactorResponse)
async def refactor(request: RefactorRequest) -> RefactorResponse:
    """Run the full Golden Path synchronously and return the result.

    Flow: ``compile_refactor_blast_context`` → ``plan_from_blast_context``
    → ``PlanExecutor.run`` (GENERATE → VALIDATE → PREVIEW → APPLY).

    Acquires a workspace lock via the Sentinel — concurrent writes to
    the same workspace are rejected with HTTP 409.
    """
    _validate_refactor_request(request.intent, request.filePath)
    workspace = request.workspacePath or "."
    executor = _get_plan_executor(workspace)

    try:
        async with _sentinel.acquire(workspace):
            affected, breaking, diffs, plan_summary = await _run_pipeline(
                request.intent, request.filePath, workspace, executor
            )
        return RefactorResponse(
            success=True,
            state=executor.state.value,
            executionId=executor.execution_id,
            affectedFiles=affected,
            diffs=diffs,
            breakingChange=breaking,
            stateHistory=[e.to_dict() for e in executor.state_history],
            proposedPlan=plan_summary,
        )
    except WorkspaceBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        return RefactorResponse(
            success=False,
            state=executor.state.value,
            executionId=executor.execution_id,
            stateHistory=[e.to_dict() for e in executor.state_history],
            proposedPlan=executor.proposed_plan.summary if executor.proposed_plan else None,
            error=str(exc),
        )


@router.post("/refactor/rename", response_model=RefactorResponse)
async def rename_symbol(request: RenameRequest) -> RefactorResponse:
    """Run a rename refactor synchronously.

    Constructs intent ``"Rename {oldName} to {newName}"`` and delegates to
    the same pipeline as ``POST /refactor``.
    """
    _validate_rename_request(request)
    intent = f"Rename {request.oldName} to {request.newName}"
    workspace = request.workspacePath or "."
    executor = _get_plan_executor(workspace)

    try:
        async with _sentinel.acquire(workspace):
            affected, breaking, diffs, plan_summary = await _run_pipeline(
                intent, request.filePath, workspace, executor
            )
        return RefactorResponse(
            success=True,
            state=executor.state.value,
            executionId=executor.execution_id,
            affectedFiles=affected,
            diffs=diffs,
            breakingChange=breaking,
            stateHistory=[e.to_dict() for e in executor.state_history],
            proposedPlan=plan_summary,
        )
    except WorkspaceBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        return RefactorResponse(
            success=False,
            state=executor.state.value,
            executionId=executor.execution_id,
            stateHistory=[e.to_dict() for e in executor.state_history],
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Dry-run endpoint
# ---------------------------------------------------------------------------

@router.post("/refactor/dry-run", response_model=RefactorResponse)
async def dry_run_refactor(request: DryRunRequest) -> RefactorResponse:
    """Simulate a refactor without writing to disk.

    Runs the full pipeline through GENERATE → VALIDATE → PREVIEW_DIFF
    but skips the APPLY phase.  Returns the proposed plan, diffs, and
    validation results so the caller can inspect before committing.

    If the proposed code has syntax errors, the response will include
    ``success: false`` and the validation error.
    """
    _validate_refactor_request(request.intent, request.filePath)
    workspace = request.workspacePath or "."
    executor = _get_plan_executor(workspace, dry_run=True)

    try:
        affected, breaking, diffs, plan_summary = await _run_pipeline(
            request.intent, request.filePath, workspace, executor
        )
        return RefactorResponse(
            success=True,
            state=executor.state.value,
            executionId=executor.execution_id,
            affectedFiles=affected,
            diffs=diffs,
            breakingChange=breaking,
            stateHistory=[e.to_dict() for e in executor.state_history],
            proposedPlan=plan_summary,
        )
    except Exception as exc:
        return RefactorResponse(
            success=False,
            state=executor.state.value,
            executionId=executor.execution_id,
            stateHistory=[e.to_dict() for e in executor.state_history],
            proposedPlan=executor.proposed_plan.summary if executor.proposed_plan else None,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Visual refactor endpoints
# ---------------------------------------------------------------------------

async def _run_visual_pipeline(
    intent: str,
    image_base64: str,
    workspace_path: str,
    media_type: str = "image/png",
    file_path: Optional[str] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Run the visual grounding + refactor pipeline.

    1. Index the workspace.
    2. Run ``VisualGrounder`` to identify files/symbols from the image.
    3. If a primary file is identified, run the full refactor pipeline.
    4. Return the grounding result + any ProposedPlan.
    """
    from code4u.ai_engine.llm.visual_grounder import VisualGrounder

    dep_map = _get_or_build_dep_map(workspace_path)
    grounder = VisualGrounder(dep_map=dep_map)
    grounding = await grounder.ground(
        image_base64=image_base64,
        intent=intent,
        media_type=media_type,
    )

    result: Dict[str, Any] = {
        "grounding": grounding.metadata,
        "visualSummary": grounding.visual_summary,
    }

    primary_file = file_path
    if not primary_file and grounding.matched_files:
        primary_file = grounding.matched_files[0]

    if primary_file and intent:
        effective_intent = intent
        if grounding.is_ui_layout and "layout" not in intent.lower():
            effective_intent = f"[UI Layout] {intent}"

        try:
            executor = _get_plan_executor(workspace_path, dry_run=dry_run)
            affected, breaking, diffs, plan_summary = await _run_pipeline(
                effective_intent, primary_file, workspace_path, executor
            )

            if plan_summary:
                plan_summary["visualReasoningMetadata"] = grounding.metadata

            result.update({
                "success": True,
                "state": executor.state.value,
                "executionId": executor.execution_id,
                "affectedFiles": affected,
                "diffs": diffs,
                "breakingChange": breaking,
                "stateHistory": [e.to_dict() for e in executor.state_history],
                "proposedPlan": plan_summary,
            })
        except Exception as exc:
            result.update({
                "success": False,
                "error": str(exc),
            })
    else:
        result["success"] = True
        result["message"] = "Grounding complete. Provide a file path and intent to trigger the refactor pipeline."

    return result


@router.post("/refactor/visual")
async def visual_refactor(request: VisualRefactorRequest) -> Dict[str, Any]:
    """Run a visually-grounded refactor from a base64 image.

    The vision LLM analyzes the image against the workspace's
    ``DependencyMap`` to identify which files and symbols are
    represented.  If a primary file is identified (or provided),
    the full refactor pipeline runs.

    Returns the ``GroundingResult`` metadata alongside the standard
    refactor response (diffs, affected files, ProposedPlan).
    """
    workspace = request.workspacePath or "."
    return await _run_visual_pipeline(
        intent=request.intent,
        image_base64=request.imageBase64,
        workspace_path=workspace,
        media_type=request.mediaType,
        file_path=request.filePath,
        dry_run=request.dryRun,
    )


@router.post("/refactor/visual/upload")
async def visual_refactor_upload(
    image: UploadFile = File(..., description="Image file (PNG/JPEG/WebP)."),
    intent: str = Form(default="", description="Refactor intent."),
    filePath: str = Form(default="", description="Primary file path."),
    workspacePath: str = Form(default=".", description="Workspace root."),
    dryRun: bool = Form(default=True, description="Dry-run mode."),
) -> Dict[str, Any]:
    """Run a visually-grounded refactor from an uploaded image file.

    Accepts ``multipart/form-data`` — ideal for drag-and-drop from
    a browser or IDE extension.
    """
    contents = await image.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")

    content_type = image.content_type or "image/png"
    if "/" not in content_type:
        content_type = "image/png"

    return await _run_visual_pipeline(
        intent=intent,
        image_base64=image_b64,
        workspace_path=workspacePath,
        media_type=content_type,
        file_path=filePath or None,
        dry_run=dryRun,
    )


@router.post("/refactor/visual/ground")
async def visual_ground_only(request: VisualRefactorRequest) -> Dict[str, Any]:
    """Run visual grounding only (no refactor pipeline).

    Returns which files and symbols the vision LLM identified in the
    image.  Useful for previewing the grounding before committing to
    a refactor.
    """
    from code4u.ai_engine.llm.visual_grounder import VisualGrounder

    workspace = request.workspacePath or "."
    dep_map = _get_or_build_dep_map(workspace)
    grounder = VisualGrounder(dep_map=dep_map)
    grounding = await grounder.ground(
        image_base64=request.imageBase64,
        intent=request.intent,
        media_type=request.mediaType,
    )

    return {
        "success": True,
        "grounding": grounding.metadata,
        "visualSummary": grounding.visual_summary,
        "suggestedIntent": grounding.suggested_intent,
        "isUiLayout": grounding.is_ui_layout,
        "matchedFileCount": len(grounding.matched_files),
        "matchedSymbolCount": len(grounding.matched_symbols),
    }


# ---------------------------------------------------------------------------
# Multi-root endpoint
# ---------------------------------------------------------------------------

async def _run_multi_root_pipeline(
    intent: str,
    file_path: str,
    workspace_paths: List[str],
    executor: PlanExecutor,
) -> tuple[List[str], bool, Dict[str, str], Optional[Dict[str, Any]]]:
    """Compile context against multi-root index, build plan, execute.

    The first workspace path is used as the primary root for symbol
    resolution; all roots contribute to the DependencyMap for cross-folder
    dependency discovery.
    """
    primary_workspace = workspace_paths[0]
    compiler = _get_multi_compiler(workspace_paths)
    blast_context = await compiler.compile_refactor_blast_context(
        intent=intent,
        primary_file_path=file_path,
        workspace_path=primary_workspace,
    )
    plan = plan_from_blast_context(blast_context)
    await executor.run(plan, blast_context, intent=intent)

    affected = list(plan.affected_files)
    if executor.proposed_plan:
        for new_file in executor.proposed_plan.files_to_create:
            if new_file not in affected:
                affected.append(new_file)

    breaking = plan.metadata.get("has_cross_owner", False)
    diffs = executor.diffs
    plan_summary = executor.proposed_plan.summary if executor.proposed_plan else None

    if plan_summary and executor.proposed_plan:
        dep_map = _get_or_build_multi_dep_map(workspace_paths)
        if dep_map.is_multi_root:
            symbol_name = blast_context.symbol.name
            cross_root = dep_map.get_cross_root_dependents(
                symbol_name, blast_context.defining_file
            )
            plan_summary["crossRootDependents"] = {
                root: files for root, files in cross_root.items()
            }
            plan_summary["rootCount"] = len(dep_map.root_paths)

    return affected, breaking, diffs, plan_summary


@router.post("/refactor/multi-root", response_model=RefactorResponse)
async def multi_root_refactor(request: MultiRootRefactorRequest) -> RefactorResponse:
    """Run a refactor that spans multiple workspace roots atomically.

    All roots are indexed into a single ``DependencyMap`` so that
    cross-folder dependencies are discovered automatically.  The
    ``ProposedPlan`` aggregates operations across all roots, and
    rollback covers every root.
    """
    _validate_refactor_request(request.intent, request.filePath)
    if not request.workspacePaths:
        raise HTTPException(status_code=400, detail="workspacePaths must be non-empty")

    executor = _get_multi_plan_executor(request.workspacePaths)

    try:
        affected, breaking, diffs, plan_summary = await _run_multi_root_pipeline(
            request.intent, request.filePath, request.workspacePaths, executor
        )
        return RefactorResponse(
            success=True,
            state=executor.state.value,
            executionId=executor.execution_id,
            affectedFiles=affected,
            diffs=diffs,
            breakingChange=breaking,
            stateHistory=[e.to_dict() for e in executor.state_history],
            proposedPlan=plan_summary,
        )
    except Exception as exc:
        return RefactorResponse(
            success=False,
            state=executor.state.value,
            executionId=executor.execution_id,
            stateHistory=[e.to_dict() for e in executor.state_history],
            proposedPlan=executor.proposed_plan.summary if executor.proposed_plan else None,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Async job endpoints (polling)
# ---------------------------------------------------------------------------

async def _execute_job(job: _RefactorJob, intent: str, file_path: str, workspace: str) -> None:
    """Background coroutine that runs the pipeline for an async job.

    Updates ``job.status``, ``job.executor``, and ``job.error`` in-place
    so the polling endpoint can read them at any time.  Also pushes
    real-time progress events to the SSE stream via ``status_callback``.
    """
    callback = make_status_callback(job.job_id)
    executor = _get_plan_executor(workspace, status_callback=callback)
    job.executor = executor
    job.status = JobStatus.RUNNING

    try:
        affected, breaking, _diffs, _plan = await _run_pipeline(
            intent, file_path, workspace, executor
        )
        job.affected_files = affected
        job.breaking_change = breaking
        job.status = JobStatus.COMPLETED
    except Exception as exc:
        job.error = str(exc)
        job.status = JobStatus.FAILED


@router.post("/refactor/jobs", response_model=JobCreatedResponse)
async def create_refactor_job(request: RefactorRequest) -> JobCreatedResponse:
    """Start an async refactor and return a ``jobId`` for polling.

    The pipeline runs in a background ``asyncio.Task``.  Poll
    ``GET /refactor/jobs/{jobId}`` to observe progress.
    """
    _validate_refactor_request(request.intent, request.filePath)
    workspace = request.workspacePath or "."
    job_id = str(uuid.uuid4())
    job = _RefactorJob(job_id=job_id, intent=request.intent)
    _jobs[job_id] = job
    asyncio.create_task(
        _execute_job(job, request.intent, request.filePath, workspace)
    )
    return JobCreatedResponse(jobId=job_id)


@router.post("/refactor/rename/jobs", response_model=JobCreatedResponse)
async def create_rename_job(request: RenameRequest) -> JobCreatedResponse:
    """Start an async rename refactor and return a ``jobId`` for polling."""
    _validate_rename_request(request)
    intent = f"Rename {request.oldName} to {request.newName}"
    workspace = request.workspacePath or "."
    job_id = str(uuid.uuid4())
    job = _RefactorJob(job_id=job_id, intent=intent)
    _jobs[job_id] = job
    asyncio.create_task(
        _execute_job(job, intent, request.filePath, workspace)
    )
    return JobCreatedResponse(jobId=job_id)


@router.get("/refactor/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Poll the status of an async refactor job.

    Returns the current state-machine position, full state history,
    affected files, diffs (when available), and any error.
    """
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    executor = job.executor
    state = "INIT"
    state_history: List[Dict[str, Any]] = []
    diffs: Dict[str, str] = {}
    execution_id = ""

    if executor is not None:
        state = executor.state.value
        state_history = [e.to_dict() for e in executor.state_history]
        diffs = executor.diffs
        execution_id = executor.execution_id

    return JobStatusResponse(
        jobId=job.job_id,
        status=job.status.value,
        state=state,
        stateHistory=state_history,
        affectedFiles=job.affected_files,
        diffs=diffs,
        breakingChange=job.breaking_change,
        executionId=execution_id,
        error=job.error,
        createdAt=job.created_at,
    )


# ---------------------------------------------------------------------------
# Index management endpoints
# ---------------------------------------------------------------------------

class IndexRequest(BaseModel):
    """Payload for ``POST /refactor/index``."""
    workspacePath: str = Field(default="", description="Single workspace root.")
    workspacePaths: Optional[List[str]] = Field(
        None, description="Multiple workspace roots (takes precedence over workspacePath)."
    )


class IndexResponse(BaseModel):
    """Response with index statistics."""
    workspacePath: str = ""
    workspacePaths: Optional[List[str]] = None
    stats: Dict[str, Any] = Field(default_factory=dict)


@router.post("/refactor/index", response_model=IndexResponse)
async def index_workspace(request: IndexRequest) -> IndexResponse:
    """Build (or rebuild) the symbol index for a workspace.

    Supports both single-root and multi-root indexing.  Pass
    ``workspacePaths`` for multi-root; ``workspacePath`` for single.
    Forces a fresh index even if one is already cached.
    """
    if request.workspacePaths and len(request.workspacePaths) > 0:
        resolved = [str(Path(wp).resolve()) for wp in request.workspacePaths]
        dep_map = _indexer.index_multi_workspace(resolved)
        cache_key = _MULTI_ROOT_KEY + "|".join(sorted(resolved))
        _dep_maps[cache_key] = dep_map
        return IndexResponse(
            workspacePaths=resolved,
            stats=dep_map.stats,
        )

    if not request.workspacePath:
        raise HTTPException(status_code=400, detail="workspacePath or workspacePaths required")

    resolved_single = str(Path(request.workspacePath).resolve())
    dep_map = _indexer.index_workspace(resolved_single)
    _dep_maps[resolved_single] = dep_map
    return IndexResponse(workspacePath=resolved_single, stats=dep_map.stats)


@router.get("/refactor/index")
async def get_index_stats() -> Dict[str, Any]:
    """Return statistics for all currently cached workspace indexes."""
    return {
        workspace: dm.stats
        for workspace, dm in _dep_maps.items()
    }


@router.get("/refactor/index/symbols/{symbol_name}")
async def lookup_symbol(symbol_name: str, workspace: str = ".") -> Dict[str, Any]:
    """Look up a symbol in the index and return its definitions and dependents."""
    dep_map = _get_or_build_dep_map(workspace)
    defs = dep_map.get_symbol_defs(symbol_name)
    dependents = dep_map.get_dependents(symbol_name)
    return {
        "symbol": symbol_name,
        "definitions": [
            {
                "file": d.file_path,
                "kind": d.kind,
                "startLine": d.start_line,
                "endLine": d.end_line,
                "exported": d.is_exported,
            }
            for d in defs
        ],
        "dependents": dependents,
        "dependentCount": len(dependents),
    }


class SyncFileRequest(BaseModel):
    """Payload for ``POST /refactor/index/sync``."""
    filePath: str = Field(..., min_length=1, description="File that changed.")
    workspacePath: str = Field(..., min_length=1, description="Workspace root the file belongs to.")


@router.post("/refactor/index/sync")
async def sync_single_file(request: SyncFileRequest) -> Dict[str, Any]:
    """Re-index a single file without a full workspace scan.

    Called by IDE extensions or file watchers when a file is saved.
    Updates the cached ``DependencyMap`` incrementally — typically
    completes in under 1 ms.
    """
    resolved_workspace = str(Path(request.workspacePath).resolve())
    dep_map = _dep_maps.get(resolved_workspace)
    if dep_map is None:
        dep_map = _get_or_build_dep_map(resolved_workspace)
    _indexer.index_single_file(
        request.filePath, dep_map, root_path=resolved_workspace
    )
    return {
        "synced": request.filePath,
        "workspace": resolved_workspace,
        "stats": dep_map.stats,
    }


@router.get("/refactor/index/cycles")
async def detect_cycles(workspace: str = ".") -> Dict[str, Any]:
    """Detect circular import chains in the workspace index.

    Returns all cycles found in the dependency graph.  Useful for
    diagnosing import loops that could affect refactoring safety.
    """
    dep_map = _get_or_build_dep_map(workspace)
    cycles = dep_map.detect_cycles()
    return {
        "workspace": workspace,
        "cycleCount": len(cycles),
        "cycles": [
            [f for f in cycle]
            for cycle in cycles
        ],
    }


# ---------------------------------------------------------------------------
# Session-aware refactoring (stateful iteration)
# ---------------------------------------------------------------------------

@router.post("/refactor/session", response_model=SessionResponse)
async def session_refactor(request: SessionRefactorRequest) -> SessionResponse:
    """Run a refactor within a session context (stateful iteration).

    If ``sessionId`` is provided, loads the previous intents and diffs
    from that session and injects them as context for the LLM.  This
    enables follow-up refinements like "Actually, use camelCase for that."

    If ``sessionId`` is omitted, a new session is created automatically.
    The response always includes the ``sessionId`` for use in follow-ups.
    """
    _validate_refactor_request(request.intent, request.filePath)
    workspace = request.workspacePath or "."
    user_id = request.userId or _DEFAULT_USER

    dep_map = _get_or_build_dep_map(workspace)
    snap = DependencySnapshot(
        indexed_files=dep_map.stats.get("indexed_files", 0),
        total_symbols=dep_map.stats.get("total_symbols", 0),
        total_imports=dep_map.stats.get("total_imports", 0),
    )
    session = _session_mgr.get_or_create_session(
        workspace_path=workspace,
        session_id=request.sessionId,
        dep_snapshot=snap,
        owner_id=user_id,
    )

    if session.owner_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=f"Session {session.session_id} belongs to another user."
        )

    executor = _get_plan_executor(workspace, dry_run=request.dryRun)

    refinement_ctx = _session_mgr.build_refinement_context(session.session_id)

    effective_intent = request.intent
    if refinement_ctx.get("lastDiffs"):
        effective_intent = _build_refinement_intent(
            request.intent, refinement_ctx
        )

    try:
        async with _sentinel.acquire(workspace, session_id=session.session_id):
            affected, breaking, diffs, plan_summary = await _run_pipeline(
                effective_intent, request.filePath, workspace, executor
            )

        job = RefactorJobRecord(
            job_id=str(uuid.uuid4()),
            intent=request.intent,
            intent_type=executor.proposed_plan.intent_type if executor.proposed_plan else "unknown",
            file_path=request.filePath,
            affected_files=affected,
            diffs=diffs,
            plan_summary=plan_summary,
            state=executor.state.value,
            execution_id=executor.execution_id,
            success=True,
        )
        _session_mgr.add_job(session.session_id, job)

        return SessionResponse(
            success=True,
            sessionId=session.session_id,
            state=executor.state.value,
            executionId=executor.execution_id,
            affectedFiles=affected,
            diffs=diffs,
            breakingChange=breaking,
            stateHistory=[e.to_dict() for e in executor.state_history],
            proposedPlan=plan_summary,
            sessionSummary=session.summary,
        )

    except WorkspaceBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        job = RefactorJobRecord(
            job_id=str(uuid.uuid4()),
            intent=request.intent,
            intent_type="unknown",
            file_path=request.filePath,
            state=executor.state.value,
            execution_id=executor.execution_id,
            success=False,
            error=str(exc),
        )
        _session_mgr.add_job(session.session_id, job)

        return SessionResponse(
            success=False,
            sessionId=session.session_id,
            state=executor.state.value,
            executionId=executor.execution_id,
            stateHistory=[e.to_dict() for e in executor.state_history],
            proposedPlan=executor.proposed_plan.summary if executor.proposed_plan else None,
            sessionSummary=session.summary,
            error=str(exc),
        )


def _build_refinement_intent(intent: str, refinement_ctx: Dict[str, Any]) -> str:
    """Augment a follow-up intent with context from the previous job.

    Prepends previous intent and diff summary so the LLM understands
    what was already done and can refine rather than start fresh.
    """
    last_intent = refinement_ctx.get("lastIntent", "")
    last_diffs = refinement_ctx.get("lastDiffs", {})

    diff_summary_parts: List[str] = []
    for file_path, diff_text in last_diffs.items():
        short = "/".join(Path(file_path).parts[-2:])
        line_count = len([l for l in diff_text.splitlines() if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))])
        diff_summary_parts.append(f"{short} ({line_count} changed lines)")

    diff_summary = "; ".join(diff_summary_parts[:10])

    return (
        f"[Follow-up] Previous intent: \"{last_intent}\". "
        f"Previous changes: [{diff_summary}]. "
        f"New instruction: {intent}"
    )


# ---------------------------------------------------------------------------
# Session management endpoints
# ---------------------------------------------------------------------------

@router.post("/refactor/sessions")
async def create_session(
    workspacePath: str = ".",
) -> Dict[str, Any]:
    """Create a new refactoring session for a workspace."""
    dep_map = _get_or_build_dep_map(workspacePath)
    snap = DependencySnapshot(
        indexed_files=dep_map.stats.get("indexed_files", 0),
        total_symbols=dep_map.stats.get("total_symbols", 0),
        total_imports=dep_map.stats.get("total_imports", 0),
    )
    session = _session_mgr.create_session(workspacePath, dep_snapshot=snap)
    return session.summary


@router.get("/refactor/sessions")
async def list_sessions(
    limit: int = 20,
    userId: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List recent refactoring sessions, optionally filtered by user."""
    return [
        s.summary
        for s in _session_mgr.list_sessions(limit, owner_id=userId)
    ]


@router.get("/refactor/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """Get full details of a specific session."""
    session = _session_mgr.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {
        **session.summary,
        "jobs": [j.to_dict() for j in session.jobs],
        "depSnapshot": session.dep_snapshot.to_dict() if session.dep_snapshot else None,
    }


@router.delete("/refactor/sessions/{session_id}")
async def delete_session(session_id: str) -> Dict[str, Any]:
    """Delete a session."""
    deleted = _session_mgr.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {"deleted": True, "sessionId": session_id}


@router.get("/refactor/sessions/{session_id}/context")
async def get_session_context(session_id: str) -> Dict[str, Any]:
    """Get the refinement context for a session (for debugging/preview)."""
    ctx = _session_mgr.build_refinement_context(session_id)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return ctx


# ---------------------------------------------------------------------------
# Sentinel status
# ---------------------------------------------------------------------------

@router.get("/refactor/sentinel/status")
async def sentinel_status(workspace: str = ".") -> Dict[str, Any]:
    """Check whether a workspace is currently locked by the sentinel."""
    is_locked = _sentinel.is_locked(workspace)
    owner = _sentinel.owning_session(workspace)
    return {
        "workspace": workspace,
        "locked": is_locked,
        "owningSession": owner,
    }


# ---------------------------------------------------------------------------
# Predictive Impact Analysis
# ---------------------------------------------------------------------------

@router.get("/refactor/predict/{symbol_name}")
async def predict_impact(
    symbol_name: str,
    workspace: str = ".",
    max_depth: int = 10,
) -> Dict[str, Any]:
    """Predict the blast radius of modifying or deleting a symbol.

    Uses the ``DependencyMap`` to build a recursive tree of every file,
    function, and import that would be affected if *symbol_name* were
    changed or removed.

    Returns:
        A JSON structure with direct dependents, transitive dependents,
        the full impact tree, and statistics.
    """
    dep_map = _get_or_build_dep_map(workspace)

    defs = dep_map.get_symbol_defs(symbol_name)
    if not defs:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol_name}' not found in workspace index."
        )

    defining_file = defs[0].file_path
    direct = dep_map.get_dependents(symbol_name)

    try:
        transitive = dep_map.get_transitive_dependents(
            symbol_name, defining_file, max_depth=max_depth
        )
    except Exception:
        transitive = set(direct)

    impact_tree = _build_impact_tree(
        symbol_name, defining_file, dep_map, max_depth=max_depth
    )

    broken_imports: List[Dict[str, Any]] = []
    for file_path in direct:
        imports = dep_map._imports.get(file_path, [])
        for imp in imports:
            if symbol_name in getattr(imp, "names", []):
                broken_imports.append({
                    "file": file_path,
                    "importLine": f"from {getattr(imp, 'module', '?')} import {', '.join(getattr(imp, 'names', []))}",
                })

    return {
        "symbol": symbol_name,
        "definingFile": defining_file,
        "definitions": [
            {
                "file": d.file_path,
                "kind": d.kind,
                "startLine": d.start_line,
                "endLine": d.end_line,
                "exported": d.is_exported,
            }
            for d in defs
        ],
        "directDependents": direct,
        "directDependentCount": len(direct),
        "transitiveDependents": list(transitive),
        "transitiveDependentCount": len(transitive),
        "brokenImports": broken_imports,
        "impactTree": impact_tree,
        "blastRadius": {
            "files": len(transitive),
            "severity": (
                "low" if len(transitive) <= 2
                else "medium" if len(transitive) <= 5
                else "high" if len(transitive) <= 10
                else "critical"
            ),
        },
    }


def _build_impact_tree(
    symbol_name: str,
    defining_file: str,
    dep_map: DependencyMap,
    max_depth: int = 10,
    _visited: Optional[set] = None,
    _depth: int = 0,
) -> Dict[str, Any]:
    """Recursively build a dependency impact tree.

    Each node contains the file path, the symbols it defines,
    and its own dependents (children).  Cycles are broken via
    the ``_visited`` set.
    """
    if _visited is None:
        _visited = set()

    if _depth > max_depth or defining_file in _visited:
        return {
            "file": defining_file,
            "symbol": symbol_name,
            "truncated": True,
        }

    _visited.add(defining_file)

    file_symbols = dep_map._file_symbols.get(defining_file, [])
    children: List[Dict[str, Any]] = []

    dependents = dep_map.get_dependents(symbol_name)
    for dep_file in dependents:
        if dep_file in _visited:
            children.append({
                "file": dep_file,
                "symbol": symbol_name,
                "relationship": "imports",
                "circular": True,
            })
            continue

        dep_file_symbols = dep_map._file_symbols.get(dep_file, [])
        child_names = [s.name for s in dep_file_symbols[:5]]

        sub_children: List[Dict[str, Any]] = []
        for child_sym in dep_file_symbols[:3]:
            child_deps = dep_map.get_dependents(child_sym.name)
            if child_deps:
                sub_tree = _build_impact_tree(
                    child_sym.name, dep_file, dep_map,
                    max_depth=max_depth,
                    _visited=_visited,
                    _depth=_depth + 1,
                )
                if sub_tree.get("dependents"):
                    sub_children.append(sub_tree)

        children.append({
            "file": dep_file,
            "symbol": symbol_name,
            "relationship": "imports",
            "symbols": child_names,
            "dependents": sub_children if sub_children else None,
        })

    return {
        "file": defining_file,
        "symbol": symbol_name,
        "symbols": [s.name for s in file_symbols[:10]],
        "dependents": children if children else None,
    }


# ---------------------------------------------------------------------------
# Recipe API endpoints (Day 14)
# ---------------------------------------------------------------------------

_recipe_registry = None

def _get_recipe_registry(workspace_path: Optional[str] = None):
    global _recipe_registry
    from code4u.core.recipes import RecipeRegistry
    if _recipe_registry is None or workspace_path:
        _recipe_registry = RecipeRegistry(workspace_path=workspace_path or ".")
        _recipe_registry.load()
    return _recipe_registry


class RecipeRunRequest(BaseModel):
    recipeId: str = Field(..., description="ID of the recipe to run.")
    workspacePath: str = Field(".", description="Workspace root.")
    filePath: Optional[str] = Field(None, description="Primary file (optional, recipe selector used if omitted).")
    extraContext: str = Field("", description="Additional context for the prompt.")
    dryRun: bool = Field(True, description="Preview without writing.")


@router.get("/refactor/recipes")
async def list_recipes(workspacePath: Optional[str] = None):
    """List all available recipes (global + project-local)."""
    registry = _get_recipe_registry(workspacePath)
    return {
        "recipes": [r.summary() for r in registry.list_recipes()],
        "count": registry.count,
    }


@router.get("/refactor/recipes/{recipe_id}")
async def get_recipe(recipe_id: str, workspacePath: Optional[str] = None):
    """Get details for a specific recipe."""
    registry = _get_recipe_registry(workspacePath)
    recipe = registry.get(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail=f"Recipe not found: {recipe_id}")
    return recipe.to_dict()


@router.post("/refactor/recipes/run")
async def run_recipe(request: RecipeRunRequest):
    """Execute a recipe through the standard refactoring pipeline.

    The recipe's selector filters the DependencyMap to find target files,
    and the prompt_template is used as the refactoring intent.  The full
    Atomic Rollback safety net and SSE progress streaming still apply.
    """
    registry = _get_recipe_registry(request.workspacePath)
    recipe = registry.get(request.recipeId)
    if not recipe:
        raise HTTPException(status_code=404, detail=f"Recipe not found: {request.recipeId}")

    workspace = request.workspacePath or "."
    dep_map = _get_or_build_dep_map(workspace)
    all_files = list(dep_map._file_symbols.keys())
    matched_files = recipe.selector.filter_files(all_files)

    if not matched_files:
        return {
            "status": "no_matches",
            "message": f"Recipe '{recipe.id}' selector matched 0 files.",
            "selector": recipe.selector.to_dict(),
        }

    primary_file = request.filePath or matched_files[0]
    intent = recipe.build_intent(request.extraContext)

    job_id = str(uuid.uuid4())
    job = _RefactorJob(job_id=job_id, intent=intent)
    _jobs[job_id] = job

    asyncio.create_task(
        _execute_job(job, intent, primary_file, workspace)
    )

    return {
        "jobId": job_id,
        "recipeId": recipe.id,
        "recipeName": recipe.name,
        "matchedFiles": len(matched_files),
        "selector": recipe.selector.to_dict(),
        "dryRun": request.dryRun,
    }
