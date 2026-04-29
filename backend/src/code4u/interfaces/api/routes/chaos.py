"""Chaos Engineering & Adversarial Testing API routes.

Endpoints:
  - POST /chaos/toggle          — enable/disable chaos mode
  - POST /chaos/inject          — manually inject a fault
  - POST /chaos/round           — run a chaos round
  - GET  /chaos/report          — get chaos report
  - GET  /chaos/events          — get chaos events
  - POST /chaos/clear           — clear chaos history
  - POST /adversarial/run       — run adversarial hygiene suite
  - POST /adversarial/check     — check a single input
  - POST /adversarial/scan-code — scan code for adversarial comments
  - POST /red-team/scan         — run full red team scan
  - GET  /red-team/report       — get latest red team report
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from code4u.agents.chaos_agent import get_chaos_agent
from code4u.security_compliance.security.adversarial_agent import AdversarialAgent
from code4u.agents.red_team_agent import RedTeamAgent

router = APIRouter()

_adversarial_agent = AdversarialAgent()
_red_team_agent = RedTeamAgent()
_last_red_team_result: Dict[str, Any] = {}
_last_adversarial_report: Dict[str, Any] = {}


class ChaosToggleRequest(BaseModel):
    enabled: bool = Field(..., description="Enable or disable chaos mode")
    intensity: float = Field(0.3, description="Chaos intensity (0.0-1.0)")


class ChaosInjectRequest(BaseModel):
    fault_type: str = Field(..., description="process_kill, latency_injection, memory_pressure, stage_corruption, network_partition")
    target: str = Field("worker", description="Target of the fault")
    pid: Optional[int] = Field(None, description="PID to kill (process_kill only)")


class AdversarialCheckRequest(BaseModel):
    input_text: str = Field(..., description="Text to check for adversarial patterns")


class CodeScanRequest(BaseModel):
    code: str = Field(..., description="Code to scan for adversarial comments")


class RedTeamRequest(BaseModel):
    code_map: Dict[str, str] = Field(..., description="filepath -> content to red-team scan")


# ── Chaos Endpoints ──

@router.post("/chaos/toggle")
async def toggle_chaos(request: ChaosToggleRequest) -> Dict[str, Any]:
    chaos = get_chaos_agent()
    chaos.set_enabled(request.enabled)
    chaos.set_intensity(request.intensity)
    return {"enabled": chaos.enabled, "intensity": chaos.intensity}


@router.post("/chaos/inject")
async def inject_fault(request: ChaosInjectRequest) -> Dict[str, Any]:
    chaos = get_chaos_agent()
    was_enabled = chaos.enabled
    chaos.enabled = True

    try:
        ft = request.fault_type
        if ft == "latency_injection":
            event = chaos.inject_latency(request.target)
        elif ft == "process_kill":
            event = chaos.inject_process_kill(request.pid, request.target)
        elif ft == "memory_pressure":
            event = chaos.inject_memory_pressure(request.target)
        elif ft == "stage_corruption":
            event = chaos.inject_stage_corruption(request.target)
        elif ft == "network_partition":
            event = chaos.inject_network_partition(request.target)
        else:
            return {"error": f"Unknown fault type: {ft}"}
    finally:
        chaos.enabled = was_enabled

    return event.to_dict()


@router.post("/chaos/round")
async def run_chaos_round() -> Dict[str, Any]:
    chaos = get_chaos_agent()
    if not chaos.enabled:
        return {"message": "Chaos mode is disabled. Enable it first via POST /chaos/toggle."}
    events = chaos.run_chaos_round()
    return {"injected": len(events), "events": [e.to_dict() for e in events]}


@router.get("/chaos/report")
async def get_chaos_report() -> Dict[str, Any]:
    chaos = get_chaos_agent()
    return chaos.get_report().to_dict()


@router.get("/chaos/events")
async def get_chaos_events(limit: int = 50) -> Dict[str, Any]:
    chaos = get_chaos_agent()
    events = chaos.get_events()[-limit:]
    return {"events": [e.to_dict() for e in events], "total": len(chaos.get_events())}


@router.post("/chaos/clear")
async def clear_chaos() -> Dict[str, str]:
    chaos = get_chaos_agent()
    chaos.clear()
    return {"status": "cleared"}


# ── Adversarial Endpoints ──

@router.post("/adversarial/run")
async def run_adversarial_suite() -> Dict[str, Any]:
    global _last_adversarial_report
    agent = AdversarialAgent()
    report = agent.run_full_suite()
    _last_adversarial_report = report.to_dict()
    return _last_adversarial_report


@router.post("/adversarial/check")
async def check_adversarial_input(request: AdversarialCheckRequest) -> Dict[str, Any]:
    agent = AdversarialAgent()
    is_safe = agent.run_hygiene_check(request.input_text)
    return {"safe": is_safe, "input_length": len(request.input_text)}


@router.post("/adversarial/scan-code")
async def scan_code_for_adversarial(request: CodeScanRequest) -> Dict[str, Any]:
    agent = AdversarialAgent()
    findings = agent.test_code_comment_injection(request.code)
    return {"findings": [f.to_dict() for f in findings], "total": len(findings)}


# ── Red Team Endpoints ──

@router.post("/red-team/scan")
async def run_red_team_scan(request: RedTeamRequest) -> Dict[str, Any]:
    global _last_red_team_result
    agent = RedTeamAgent()
    result = agent.run_full_red_team(request.code_map)
    _last_red_team_result = result
    _last_red_team_result["report"] = agent.generate_report()
    return result


@router.get("/red-team/report", response_class=PlainTextResponse)
async def get_red_team_report() -> str:
    return _last_red_team_result.get("report", "# No red team scan has been run yet.\n\nRun POST /red-team/scan first.")
