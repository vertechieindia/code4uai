"""Sentinel API — architectural drift detection, governance, and security.

Endpoints:
  - ``POST /sentinel/scan``           — full workspace scan.
  - ``POST /sentinel/scan-delta``     — scan specific changed files.
  - ``GET  /sentinel/rules``          — list all registered rules.
  - ``POST /sentinel/rules``          — register a rule dynamically.
  - ``GET  /sentinel/suggest/{id}``   — get fix suggestion.
  - ``POST /sentinel/security-scan``  — secret + SAST scan on source code.
  - ``POST /sentinel/security-workspace`` — scan entire workspace for security issues.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from code4u.agents.nexus.rules import ArchitecturalRule, RuleRegistry, Violation
from code4u.agents.nexus.sentinel import Sentinel, ScanResult

router = APIRouter()


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_rule_registry = RuleRegistry()
_sentinel: Optional[Sentinel] = None
_last_violations: Dict[str, Violation] = {}


def _get_sentinel() -> Sentinel:
    if _sentinel is None:
        raise HTTPException(409, "Sentinel not initialized. POST /sentinel/scan first.")
    return _sentinel


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    workspacePath: str = Field(..., description="Workspace root to scan.")


class DeltaScanRequest(BaseModel):
    files: List[str] = Field(..., description="Changed file paths to scan.")
    workspacePath: str = Field("", description="Workspace root (for dep map).")


class RuleCreateRequest(BaseModel):
    rule: Dict[str, Any] = Field(..., description="Rule definition dict.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/sentinel/scan")
async def sentinel_full_scan(request: ScanRequest):
    """Run a full architectural scan on a workspace."""
    global _sentinel, _last_violations

    from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
        DependencyMap,
        SymbolIndexer,
    )

    dm = DependencyMap()
    indexer = SymbolIndexer()
    try:
        dm = indexer.index_workspace(request.workspacePath, use_cache=False)
    except Exception as exc:
        raise HTTPException(500, f"Indexing failed: {exc}")

    _rule_registry.load(request.workspacePath)
    _sentinel = Sentinel(_rule_registry, dm)
    result = _sentinel.scan_full()

    _last_violations.clear()
    for i, v in enumerate(result.violations):
        _last_violations[str(i)] = v

    return result.to_dict()


@router.post("/sentinel/scan-delta")
async def sentinel_delta_scan(request: DeltaScanRequest):
    """Scan only changed files for drift."""
    global _sentinel, _last_violations

    sentinel = _get_sentinel()
    result = sentinel.scan_delta(request.files)

    for i, v in enumerate(result.violations):
        _last_violations[str(len(_last_violations) + i)] = v

    return result.to_dict()


@router.get("/sentinel/rules")
async def list_rules():
    """List all registered architectural rules."""
    return {
        "rules": [r.to_dict() for r in _rule_registry.all_rules()],
        "count": _rule_registry.count,
    }


@router.post("/sentinel/rules")
async def add_rule(request: RuleCreateRequest):
    """Register a new architectural rule."""
    rule = ArchitecturalRule.from_dict(request.rule)
    _rule_registry.register(rule)
    return {"registered": rule.id, "rule": rule.to_dict()}


@router.get("/sentinel/suggest/{violation_id}")
async def suggest_fix(violation_id: str):
    """Get a remediation suggestion for a specific violation."""
    sentinel = _get_sentinel()
    violation = _last_violations.get(violation_id)
    if not violation:
        raise HTTPException(404, f"Violation '{violation_id}' not found.")
    fix = sentinel.suggest_fix(violation)
    return fix


# ---------------------------------------------------------------------------
# Security scanning endpoints
# ---------------------------------------------------------------------------

class SecurityScanRequest(BaseModel):
    source: str = Field(..., description="Source code to scan.")
    filePath: str = Field("", description="File path for context.")
    checkSecrets: bool = Field(True, description="Check for secrets/credentials.")
    checkSAST: bool = Field(True, description="Check for vulnerability patterns.")


class WorkspaceSecurityRequest(BaseModel):
    workspacePath: str = Field(..., description="Workspace root to scan.")
    maxFiles: int = Field(50, description="Maximum files to scan.")


@router.post("/sentinel/security-scan")
async def security_scan_source(request: SecurityScanRequest):
    """Scan source code for secrets and security vulnerabilities."""
    from code4u.security_compliance.security.sentinel_agent import scan_content

    findings = scan_content(
        request.source, request.filePath,
        check_secrets=request.checkSecrets,
        check_sast=request.checkSAST,
    )

    secrets = [f for f in findings if f.get("type") == "secret"]
    vulns = [f for f in findings if f.get("type") == "vulnerability"]
    high_entropy = [f for f in findings if f.get("type") == "high-entropy"]

    return {
        "findings": findings,
        "totalFindings": len(findings),
        "secrets": len(secrets),
        "vulnerabilities": len(vulns),
        "highEntropy": len(high_entropy),
        "criticalCount": sum(1 for f in findings if f.get("severity") == "critical"),
    }


@router.post("/sentinel/security-workspace")
async def security_scan_workspace(request: WorkspaceSecurityRequest):
    """Scan an entire workspace for secrets and vulnerabilities."""
    from code4u.security_compliance.security.sentinel_agent import (
        SecretScanner, SASTScanner,
    )

    workspace = request.workspacePath
    if not os.path.isdir(workspace):
        raise HTTPException(status_code=404, detail="Workspace not found")

    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next", "target"}
    code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rs", ".rb", ".env", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".conf"}

    secret_scanner = SecretScanner()
    sast_scanner = SASTScanner()

    all_findings: List[Dict[str, Any]] = []
    scanned = 0

    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in code_exts:
                continue
            if scanned >= request.maxFiles:
                break

            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            if len(content) < 10:
                continue

            scanned += 1
            rel = os.path.relpath(fpath, workspace)
            all_findings.extend(secret_scanner.scan(content, rel))
            all_findings.extend(sast_scanner.scan(content, rel))

        if scanned >= request.maxFiles:
            break

    all_findings.sort(
        key=lambda f: {"critical": 0, "warning": 1, "info": 2}.get(f.get("severity", ""), 3)
    )

    secrets = [f for f in all_findings if f.get("type") == "secret"]
    vulns = [f for f in all_findings if f.get("type") == "vulnerability"]

    critical = sum(1 for f in all_findings if f.get("severity") == "critical")
    risk_level = "critical" if critical > 5 else "high" if critical > 0 else "medium" if len(all_findings) > 10 else "low"

    return {
        "findings": all_findings,
        "totalFindings": len(all_findings),
        "scannedFiles": scanned,
        "secretCount": len(secrets),
        "vulnerabilityCount": len(vulns),
        "criticalCount": critical,
        "riskLevel": risk_level,
    }


# ---------------------------------------------------------------------------
# SCA Vulnerability scanning
# ---------------------------------------------------------------------------

class VulnScanRequest(BaseModel):
    workspacePath: str = Field(..., description="Workspace root to scan.")


@router.post("/sentinel/vulnerabilities")
async def scan_vulnerabilities(request: VulnScanRequest):
    """Check project dependencies for known CVEs via OSV.dev + local DB."""
    from code4u.security_compliance.security.vulnerability_scanner import VulnerabilityScanner

    scanner = VulnerabilityScanner(use_osv=True)
    result = await scanner.scan_workspace(request.workspacePath)
    return result


# ---------------------------------------------------------------------------
# Combined security posture (fleet-wide)
# ---------------------------------------------------------------------------

class FleetSecurityRequest(BaseModel):
    workspacePaths: List[str] = Field(..., description="List of workspace root paths.")


@router.post("/sentinel/fleet-security")
async def fleet_security_posture(request: FleetSecurityRequest):
    """Compute fleet-wide security posture across multiple projects."""
    from code4u.security_compliance.security.sentinel_agent import SecretScanner, SASTScanner
    from code4u.security_compliance.security.vulnerability_scanner import VulnerabilityScanner

    secret_scanner = SecretScanner()
    sast_scanner = SASTScanner()
    vuln_scanner = VulnerabilityScanner(use_osv=False)

    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
    code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rs", ".env", ".yml", ".yaml"}

    fleet_secrets = 0
    fleet_vulns = 0
    fleet_cves = 0
    fleet_critical = 0
    projects: List[Dict[str, Any]] = []

    for workspace in request.workspacePaths:
        if not os.path.isdir(workspace):
            continue

        proj_secrets = 0
        proj_sast = 0
        scanned = 0

        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in skip]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in code_exts:
                    continue
                if scanned >= 30:
                    break
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    continue
                if len(content) < 10:
                    continue
                scanned += 1
                rel = os.path.relpath(fpath, workspace)
                proj_secrets += len(secret_scanner.scan(content, rel))
                proj_sast += len(sast_scanner.scan(content, rel))
            if scanned >= 30:
                break

        vuln_result = await vuln_scanner.scan_workspace(workspace)
        proj_cves = vuln_result.get("totalVulnerabilities", 0)
        proj_critical = vuln_result.get("criticalCount", 0)

        fleet_secrets += proj_secrets
        fleet_vulns += proj_sast
        fleet_cves += proj_cves
        fleet_critical += proj_critical

        projects.append({
            "workspace": workspace,
            "name": os.path.basename(workspace),
            "secrets": proj_secrets,
            "vulnerabilities": proj_sast,
            "cves": proj_cves,
            "criticalCVEs": proj_critical,
            "riskLevel": vuln_result.get("riskLevel", "low"),
        })

    return {
        "projects": projects,
        "totalProjects": len(projects),
        "fleetSecrets": fleet_secrets,
        "fleetVulnerabilities": fleet_vulns,
        "fleetCVEs": fleet_cves,
        "fleetCriticalCVEs": fleet_critical,
        "overallRisk": (
            "critical" if fleet_critical > 0
            else "high" if fleet_secrets > 5 or fleet_cves > 10
            else "medium" if fleet_secrets > 0 or fleet_cves > 0
            else "low"
        ),
    }
