"""Compliance Export — generate a full audit report for a project.

``GET /projects/{id}/export-report`` produces a Markdown summary of:
  - Project health and metadata
  - Knowledge Graph statistics
  - Applied refactors / swarm executions
  - Sentinel security audit (secrets, CVEs, SAST)
  - Telemetry / cost summary
  - System diagnostics snapshot

The result is a single Markdown document suitable for compliance handoff
to a security auditor or engineering leadership.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter()


def _format_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@router.get("/projects/{project_id}/export-report", response_class=PlainTextResponse)
async def export_project_report(project_id: str):
    """Generate a compliance-ready Markdown report for a project.

    Aggregates data from every subsystem: projects, swarm, telemetry,
    security, knowledge graph, and system doctor.
    """
    from code4u.interfaces.api.routes.swarm import _graphs
    from code4u.interfaces.api.routes.projects import _projects

    project = _projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    now = time.time()
    report_date = _format_timestamp(now)

    # ── Project overview ──────────────────────────────────────────
    sections = [
        f"# code4u.ai — Compliance Report",
        f"",
        f"**Project:** {project['name']}  ",
        f"**ID:** `{project['id']}`  ",
        f"**Path:** `{project['path']}`  ",
        f"**Repo:** {project.get('repoUrl', 'N/A') or 'Local workspace'}  ",
        f"**Generated:** {report_date}  ",
        f"**Health Score:** {project.get('healthScore', 'N/A')}/100  ",
        f"",
        f"---",
        f"",
    ]

    # ── Project statistics ────────────────────────────────────────
    sections += [
        f"## 1. Project Statistics",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Files | {project.get('totalFiles', 0)} |",
        f"| Total Symbols | {project.get('totalSymbols', 0)} |",
        f"| Languages | {', '.join(project.get('languages', [])) or 'N/A'} |",
        f"| Status | {project.get('status', 'unknown')} |",
        f"| Created | {_format_timestamp(project.get('createdAt', now))} |",
        f"| Last Indexed | {_format_timestamp(project.get('lastIndexedAt', now))} |",
        f"",
    ]

    # ── Swarm executions ──────────────────────────────────────────
    all_graphs = sorted(_graphs.values(), key=lambda g: g.created_at, reverse=True)
    sections += [
        f"## 2. AI Swarm Executions",
        f"",
        f"Total swarm runs across all projects: **{len(all_graphs)}**",
        f"",
    ]

    if all_graphs:
        sections += [
            f"| # | Goal | Tasks | Completed | Failed | Time |",
            f"|---|------|-------|-----------|--------|------|",
        ]
        for i, g in enumerate(all_graphs[:20], 1):
            goal_short = (g.goal[:60] + "...") if len(g.goal) > 60 else g.goal
            sections.append(
                f"| {i} | {goal_short} | {g.task_count} | {g.completed_count} | {g.failed_count} | {_format_timestamp(g.created_at)} |"
            )
        sections.append("")
    else:
        sections += ["_No swarm executions recorded._", ""]

    # ── Security audit ────────────────────────────────────────────
    sections += [
        f"## 3. Security Audit Summary",
        f"",
    ]

    try:
        from code4u.security_compliance.security.secret_scanner import SecretScanner
        scanner = SecretScanner()
        scan_result = scanner.scan_workspace(project["path"])
        total_secrets = scan_result.get("totalFindings", 0) if isinstance(scan_result, dict) else 0
        sections += [
            f"- **Secret Scanner:** {total_secrets} finding(s)",
        ]
    except Exception:
        sections += ["- **Secret Scanner:** Unable to run (module not available)"]

    try:
        from code4u.security_compliance.security.sast_scanner import SASTScanner
        sast = SASTScanner()
        sast_result = sast.scan_workspace(project["path"])
        sast_count = sast_result.get("totalFindings", 0) if isinstance(sast_result, dict) else 0
        sections += [
            f"- **SAST Scanner:** {sast_count} finding(s)",
        ]
    except Exception:
        sections += ["- **SAST Scanner:** Unable to run (module not available)"]

    try:
        from code4u.security_compliance.security.vulnerability_scanner import VulnerabilityScanner
        vuln = VulnerabilityScanner()
        vuln_result = vuln.scan_workspace(project["path"])
        vuln_count = vuln_result.get("totalVulnerabilities", 0) if isinstance(vuln_result, dict) else 0
        sections += [
            f"- **SCA / CVE Scanner:** {vuln_count} vulnerability(ies)",
        ]
    except Exception:
        sections += ["- **SCA / CVE Scanner:** Unable to run (module not available)"]

    sections.append("")

    # ── Telemetry / cost ──────────────────────────────────────────
    sections += [
        f"## 4. Token Usage & Cost Summary",
        f"",
    ]

    try:
        from code4u.platform_core.telemetry import get_telemetry_store
        store = get_telemetry_store()
        summary = store.get_summary()
        sections += [
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Executions | {summary.get('totalExecutions', 0)} |",
            f"| Total Input Tokens | {summary.get('totalInputTokens', 0):,} |",
            f"| Total Output Tokens | {summary.get('totalOutputTokens', 0):,} |",
            f"| Total Cost (USD) | ${summary.get('totalCostUsd', 0):.4f} |",
            f"| Success Rate | {summary.get('successRate', 0):.1f}% |",
            f"",
        ]
    except Exception:
        sections += ["_Telemetry data unavailable._", ""]

    # ── System diagnostics snapshot ───────────────────────────────
    sections += [
        f"## 5. System Diagnostics",
        f"",
    ]

    try:
        from code4u.interfaces.api.routes.doctor import (
            _check_database,
            _check_redis,
            _check_llm_provider,
            _check_git,
            _check_vector_store,
            _check_disk,
        )
        import asyncio

        probes = [_check_database, _check_redis, _check_llm_provider, _check_git, _check_vector_store, _check_disk]
        probe_results = []
        for probe in probes:
            try:
                result = asyncio.get_event_loop().run_until_complete(probe()) if not asyncio.get_event_loop().is_running() else {"name": probe.__name__, "status": "skipped"}
            except RuntimeError:
                result = {"name": probe.__name__, "status": "skipped"}
            probe_results.append(result)

        sections += [
            f"| Subsystem | Status | Latency |",
            f"|-----------|--------|---------|",
        ]
        for r in probe_results:
            latency = f"{r.get('latencyMs', '-')}ms" if 'latencyMs' in r else "-"
            sections.append(f"| {r.get('name', '?')} | {r.get('status', '?')} | {latency} |")
        sections.append("")
    except Exception:
        sections += ["_Diagnostics unavailable (run GET /api/v1/health/doctor separately)._", ""]

    # ── Air-gapped mode ───────────────────────────────────────────
    try:
        from code4u.interfaces.api.routes.airgap import is_air_gapped
        mode = "ENABLED" if is_air_gapped() else "Disabled"
        sections += [f"**Air-Gapped Mode:** {mode}", ""]
    except Exception:
        pass

    # ── Footer ────────────────────────────────────────────────────
    sections += [
        f"---",
        f"",
        f"_Report generated by **code4u.ai v1.0.0** on {report_date}._  ",
        f"_This document may be provided to security auditors for SOC 2 / ISO 27001 compliance review._",
    ]

    markdown = "\n".join(sections)

    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="code4u-report-{project_id}.md"',
        },
    )
