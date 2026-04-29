"""Legal, License & Ethical Governance API routes.

Endpoints:
  Legal:
    POST /governance/license/detect         — detect project license
    POST /governance/license/check          — check license compatibility
    POST /governance/license/gate           — gate a wisdom transfer
    GET  /governance/license/violations     — list violations
    GET  /governance/license/matrix         — compatibility matrix
    GET  /governance/license/report         — legal compliance report

  Provenance:
    POST /governance/provenance/record      — record attribution
    GET  /governance/provenance/records     — list records
    POST /governance/provenance/export      — export attribution.json
    GET  /governance/provenance/stats       — provenance stats

  Toxic Scanner:
    POST /governance/toxic/scan             — scan code for forbidden patterns
    POST /governance/toxic/add-pattern      — add custom pattern
    GET  /governance/toxic/matches          — list matches
    GET  /governance/toxic/stats            — scanner stats
    GET  /governance/toxic/report           — scanner report
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from code4u.agents.legal_agent import get_legal_agent
from code4u.knowledge.provenance_tracker import get_provenance_tracker
from code4u.security_compliance.toxic_scanner import get_toxic_scanner

router = APIRouter(prefix="/governance", tags=["Legal & Ethics"])


# ── Request Models ──────────────────────────────────────────────

class DetectLicenseRequest(BaseModel):
    workspace_path: str = Field("", description="Path to project workspace")
    content: Optional[str] = Field(None, description="Raw license file content")
    filename: str = Field("", description="Filename if providing content")


class CheckCompatibilityRequest(BaseModel):
    source_license: str = Field(..., description="Source project license")
    target_license: str = Field(..., description="Target project license")


class GateTransferRequest(BaseModel):
    source_license: str = Field(..., description="Source project license")
    target_license: str = Field(..., description="Target project license")
    nugget_id: str = Field("", description="Wisdom nugget ID")
    file_path: str = Field("", description="Target file path")


class RecordProvenanceRequest(BaseModel):
    file_path: str
    description: str
    change_type: str = "ai_suggestion"
    source_type: str = "wisdom_nugget"
    source_nugget_id: Optional[str] = None
    source_project_hash: Optional[str] = None
    source_author_hash: Optional[str] = None
    confidence: float = 0.0
    license_verified: bool = False
    license_id: Optional[str] = None


class ExportAttributionRequest(BaseModel):
    project_path: str = Field("", description="Project root path")
    save_file: bool = Field(False, description="Save to disk")


class ScanCodeRequest(BaseModel):
    code_map: Dict[str, str] = Field(..., description="filepath -> content")


class AddPatternRequest(BaseModel):
    name: str
    pattern: str
    category: str = "custom"
    severity: str = "medium"
    description: str = ""
    remediation: str = ""
    blocked: bool = False


# ── License Endpoints ──────────────────────────────────────────

@router.post("/license/detect")
async def detect_license(request: DetectLicenseRequest) -> Dict[str, Any]:
    agent = get_legal_agent()
    if request.content:
        info = agent.detect_license_from_content(request.content, request.filename)
    else:
        info = agent.detect_license(request.workspace_path)
    return info.to_dict()


@router.post("/license/check")
async def check_compatibility(request: CheckCompatibilityRequest) -> Dict[str, Any]:
    agent = get_legal_agent()
    result = agent.check_compatibility(request.source_license, request.target_license)
    return result.to_dict()


@router.post("/license/gate")
async def gate_transfer(request: GateTransferRequest) -> Dict[str, Any]:
    agent = get_legal_agent()
    allowed, violation = agent.gate_wisdom_transfer(
        source_project_license=request.source_license,
        target_project_license=request.target_license,
        nugget_id=request.nugget_id,
        file_path=request.file_path,
    )
    result: Dict[str, Any] = {"allowed": allowed}
    if violation:
        result["violation"] = violation.to_dict()
    return result


@router.get("/license/violations")
async def get_violations() -> Dict[str, Any]:
    agent = get_legal_agent()
    violations = agent.get_violations()
    return {"violations": [v.to_dict() for v in violations], "total": len(violations)}


@router.get("/license/matrix")
async def get_compatibility_matrix() -> Dict[str, Any]:
    agent = get_legal_agent()
    return agent.get_compatibility_matrix()


@router.get("/license/report", response_class=PlainTextResponse)
async def get_legal_report() -> str:
    agent = get_legal_agent()
    return agent.generate_report()


# ── Provenance Endpoints ──────────────────────────────────────

@router.post("/provenance/record")
async def record_provenance(request: RecordProvenanceRequest) -> Dict[str, Any]:
    tracker = get_provenance_tracker()
    record = tracker.record_attribution(
        file_path=request.file_path,
        description=request.description,
        change_type=request.change_type,
        source_type=request.source_type,
        source_nugget_id=request.source_nugget_id,
        source_project_hash=request.source_project_hash,
        source_author_hash=request.source_author_hash,
        confidence=request.confidence,
        license_verified=request.license_verified,
        license_id=request.license_id,
    )
    return record.to_dict()


@router.get("/provenance/records")
async def get_records(applied_only: bool = False) -> Dict[str, Any]:
    tracker = get_provenance_tracker()
    records = tracker.get_records(applied_only=applied_only)
    return {"records": [r.to_dict() for r in records], "total": len(records)}


@router.post("/provenance/export")
async def export_attribution(request: ExportAttributionRequest) -> Dict[str, Any]:
    tracker = get_provenance_tracker()
    content = tracker.export_attribution_json(request.project_path)
    result: Dict[str, Any] = {"attribution": json.loads(content)}
    if request.save_file and request.project_path:
        filepath = tracker.save_attribution_file(request.project_path)
        result["savedTo"] = filepath
    return result


@router.get("/provenance/stats")
async def get_provenance_stats() -> Dict[str, Any]:
    tracker = get_provenance_tracker()
    return tracker.get_stats()


# ── Toxic Scanner Endpoints ───────────────────────────────────

@router.post("/toxic/scan")
async def scan_for_toxic(request: ScanCodeRequest) -> Dict[str, Any]:
    scanner = get_toxic_scanner()
    matches = scanner.scan_code(request.code_map)
    return {
        "matches": [m.to_dict() for m in matches],
        "total": len(matches),
        "blocked": scanner.has_blocking_matches(matches),
    }


@router.post("/toxic/add-pattern")
async def add_pattern(request: AddPatternRequest) -> Dict[str, Any]:
    scanner = get_toxic_scanner()
    scanner.add_custom_pattern(
        name=request.name,
        pattern=request.pattern,
        category=request.category,
        severity=request.severity,
        description=request.description,
        remediation=request.remediation,
        blocked=request.blocked,
    )
    return {"status": "added", "name": request.name}


@router.get("/toxic/matches")
async def get_matches() -> Dict[str, Any]:
    scanner = get_toxic_scanner()
    matches = scanner.get_all_matches()
    return {"matches": [m.to_dict() for m in matches], "total": len(matches)}


@router.get("/toxic/stats")
async def get_toxic_stats() -> Dict[str, Any]:
    scanner = get_toxic_scanner()
    return scanner.get_stats()


@router.get("/toxic/report", response_class=PlainTextResponse)
async def get_toxic_report() -> str:
    scanner = get_toxic_scanner()
    return scanner.generate_report()
