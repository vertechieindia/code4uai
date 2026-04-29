from __future__ import annotations
"""Compliance API routes for code4u.ai.

Exposes compliance monitoring and evidence collection.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal
import structlog

from code4u.security_compliance.compliance import ComplianceControls, ComplianceMonitor, EvidenceCollector

logger = structlog.get_logger("api.compliance")
router = APIRouter()

# Service instances
controls = ComplianceControls()
monitor = ComplianceMonitor()
evidence = EvidenceCollector()


class EvidenceRequest(BaseModel):
    framework: Literal["SOC2", "ISO27001"]
    period_start: str
    period_end: str


@router.get("/compliance/check")
async def run_compliance_check():
    """Run a compliance check and return results."""
    result = await monitor.run_check()
    return result


@router.get("/compliance/dashboard")
async def get_compliance_dashboard():
    """Get compliance dashboard data."""
    dashboard = await monitor.get_dashboard()
    return dashboard


@router.get("/compliance/audit-status")
async def get_audit_status():
    """Get audit readiness status."""
    status = await monitor.get_audit_status()
    return status


@router.post("/compliance/evidence")
async def collect_evidence(request: EvidenceRequest):
    """Collect evidence for compliance audit."""
    if request.framework == "SOC2":
        package = await evidence.collect_soc2_evidence(
            period_start=request.period_start,
            period_end=request.period_end,
        )
    elif request.framework == "ISO27001":
        package = await evidence.collect_iso27001_evidence(
            period_start=request.period_start,
            period_end=request.period_end,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown framework: {request.framework}")
    
    return package.to_dict()


@router.get("/compliance/evidence/{package_id}/export")
async def export_evidence(package_id: str, format: str = "json"):
    """Export evidence package."""
    # In production, this would retrieve the package from storage
    raise HTTPException(status_code=501, detail="Evidence export not yet implemented")


@router.post("/compliance/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Mark a compliance alert as resolved."""
    monitor.resolve_alert(alert_id)
    return {"status": "resolved", "alert_id": alert_id}


@router.get("/compliance/controls")
async def list_controls():
    """List all compliance controls and their current status."""
    results = await controls.check_all()
    return {
        "controls": [r.__dict__ for r in results],
        "summary": controls.get_summary(),
    }

