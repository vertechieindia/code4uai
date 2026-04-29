"""Guardian API routes for the Gauntlet and Security Fortress.

Endpoints:
  - POST /api/v1/guardian/gauntlet/run      — start a gauntlet run
  - GET  /api/v1/guardian/gauntlet/status/{run_id} — get run status
  - GET  /api/v1/guardian/gauntlet/active   — list active runs
  - POST /api/v1/guardian/fortress/scan     — run fortress security scan
  - GET  /api/v1/guardian/fortress/score    — get latest security score
  - POST /api/v1/guardian/audit/export      — export full audit report as markdown
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from code4u.validation import GauntletOrchestrator, get_gauntlet_orchestrator
from code4u.security_compliance.security.fortress_swarm import FortressSwarm
from code4u.security_compliance.sbom_generator import SBOMGenerator

router = APIRouter()

# Module-level fortress for score persistence
_fortress_swarm: Optional[FortressSwarm] = None
_gauntlet_runs: Dict[str, Any] = {}


def _get_fortress() -> FortressSwarm:
    global _fortress_swarm
    if _fortress_swarm is None:
        _fortress_swarm = FortressSwarm()
    return _fortress_swarm


class GauntletRunRequest(BaseModel):
    """Request to start a gauntlet run."""
    proposed_code: Dict[str, str] = Field(..., description="filepath -> content")
    project_id: str = Field("", description="Project identifier")


class FortressScanRequest(BaseModel):
    """Request for fortress security scan."""
    code_map: Dict[str, str] = Field(..., description="filepath -> content")
    routes: List[Dict[str, Any]] = Field(default_factory=list)
    openapi_spec: Optional[Dict[str, Any]] = None


class AuditExportRequest(BaseModel):
    """Request to export audit report."""
    code_map: Dict[str, str] = Field(..., description="filepath -> content")
    routes: List[Dict[str, Any]] = Field(default_factory=list)


class SBOMRequest(BaseModel):
    """Request for SBOM generation."""
    workspace_path: str = Field("", description="Path to workspace for disk-based scan")
    code_map: Dict[str, str] = Field(default_factory=dict, description="filepath -> content for in-memory scan")
    project_name: str = Field("code4u-project", description="Project name for SBOM metadata")


@router.post("/guardian/gauntlet/run")
async def start_gauntlet_run(request: GauntletRunRequest):
    """Start a gauntlet validation run."""
    orchestrator = get_gauntlet_orchestrator()
    run = await orchestrator.run_validation_loop(
        proposed_code=request.proposed_code,
        project_id=request.project_id,
    )
    _gauntlet_runs[run.run_id] = run
    return run.to_dict()


@router.get("/guardian/gauntlet/status/{run_id}")
async def get_gauntlet_status(run_id: str):
    """Get status of a gauntlet run."""
    if run_id in _gauntlet_runs:
        return _gauntlet_runs[run_id].to_dict()
    from code4u.validation.gauntlet_orchestrator import _active_runs
    if run_id in _active_runs:
        return _active_runs[run_id].to_dict()
    raise HTTPException(status_code=404, detail="Run not found")


@router.get("/guardian/gauntlet/active")
async def list_active_gauntlet_runs():
    """List currently active gauntlet runs."""
    runs = GauntletOrchestrator.get_active_runs()
    return {"active": [r.to_dict() for r in runs], "count": len(runs)}


@router.post("/guardian/fortress/scan")
async def run_fortress_scan(request: FortressScanRequest):
    """Run full fortress security scan."""
    fortress = _get_fortress()
    result = await fortress.run_full_scan(
        code_map=request.code_map,
        routes=request.routes,
        openapi_spec=request.openapi_spec,
    )
    return result


@router.get("/guardian/fortress/score")
async def get_fortress_score():
    """Get latest security score from last scan."""
    fortress = _get_fortress()
    return {"securityScore": fortress.get_security_score()}


@router.post("/guardian/audit/export", response_class=PlainTextResponse)
async def export_audit_report(request: AuditExportRequest):
    """Export full audit report as markdown."""
    fortress = _get_fortress()
    result = await fortress.run_full_scan(
        code_map=request.code_map,
        routes=request.routes,
    )
    report = result.get("auditReport", "# No audit report generated")
    return PlainTextResponse(content=report, media_type="text/markdown")


@router.get("/guardian/audit/sbom")
async def generate_sbom(
    workspace_path: str = "",
    project_name: str = "code4u-project",
):
    """Generate a CycloneDX SBOM for the project."""
    generator = SBOMGenerator()
    if workspace_path:
        sbom = generator.generate_from_workspace(workspace_path)
    else:
        sbom = generator.generate_from_code_map({}, project_name=project_name)
    return sbom


@router.post("/guardian/audit/sbom")
async def generate_sbom_from_code(request: SBOMRequest):
    """Generate a CycloneDX SBOM from code map or workspace."""
    generator = SBOMGenerator()
    if request.workspace_path:
        sbom = generator.generate_from_workspace(request.workspace_path)
    elif request.code_map:
        sbom = generator.generate_from_code_map(request.code_map, project_name=request.project_name)
    else:
        sbom = generator.generate_from_code_map({}, project_name=request.project_name)
    return sbom
