"""System Doctor — comprehensive health diagnostics.

``GET /health/doctor`` pings every dependency and returns a readiness
score so operators can verify that the platform is fully operational
before onboarding users.
"""

from __future__ import annotations

import os
import shutil
import socket
import time
from typing import Any, Dict, List

from fastapi import APIRouter

import structlog

logger = structlog.get_logger("doctor")

router = APIRouter()


# ---------------------------------------------------------------------------
# Individual probes
# ---------------------------------------------------------------------------

async def _check_redis() -> Dict[str, Any]:
    """Probe Redis connectivity."""
    t0 = time.perf_counter()
    try:
        from code4u.core import get_settings
        url = get_settings().redis_url
        host = url.split("@")[-1].split("/")[0] if "@" in url else url.replace("redis://", "").split("/")[0]
        hostname, _, port_str = host.partition(":")
        port = int(port_str) if port_str else 6379
        sock = socket.create_connection((hostname, port), timeout=3)
        sock.sendall(b"PING\r\n")
        resp = sock.recv(64)
        sock.close()
        latency = (time.perf_counter() - t0) * 1000
        ok = b"PONG" in resp
        return {"name": "Redis", "status": "healthy" if ok else "degraded", "latencyMs": round(latency, 1), "url": url}
    except Exception as exc:
        return {"name": "Redis", "status": "unhealthy", "error": str(exc)[:200], "latencyMs": round((time.perf_counter() - t0) * 1000, 1)}


async def _check_database() -> Dict[str, Any]:
    """Probe PostgreSQL connectivity."""
    t0 = time.perf_counter()
    try:
        from code4u.core import get_settings
        url = get_settings().database_url
        raw = url.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
        creds_host = raw.split("/")[0]
        host_part = creds_host.split("@")[-1] if "@" in creds_host else creds_host
        hostname, _, port_str = host_part.partition(":")
        port = int(port_str) if port_str else 5432
        sock = socket.create_connection((hostname, port), timeout=3)
        sock.close()
        latency = (time.perf_counter() - t0) * 1000
        return {"name": "PostgreSQL", "status": "healthy", "latencyMs": round(latency, 1), "host": f"{hostname}:{port}"}
    except Exception as exc:
        return {"name": "PostgreSQL", "status": "unhealthy", "error": str(exc)[:200], "latencyMs": round((time.perf_counter() - t0) * 1000, 1)}


async def _check_llm_provider() -> Dict[str, Any]:
    """Probe the configured LLM provider."""
    t0 = time.perf_counter()
    try:
        from code4u.core import get_settings
        s = get_settings()
        provider = s.default_llm_provider

        if provider == "local":
            url = s.ollama_base_url
            hostname = url.replace("http://", "").replace("https://", "").split(":")[0]
            port_str = url.replace("http://", "").replace("https://", "").split(":")[-1].rstrip("/")
            port = int(port_str) if port_str.isdigit() else 11434
            sock = socket.create_connection((hostname, port), timeout=3)
            sock.close()
            latency = (time.perf_counter() - t0) * 1000
            return {"name": "LLM Provider", "status": "healthy", "provider": "ollama", "latencyMs": round(latency, 1), "url": url}

        has_key = False
        if provider == "openai" and s.openai_api_key:
            has_key = True
        elif provider == "anthropic" and s.anthropic_api_key:
            has_key = True

        latency = (time.perf_counter() - t0) * 1000
        if has_key:
            return {"name": "LLM Provider", "status": "healthy", "provider": provider, "latencyMs": round(latency, 1), "note": "API key configured"}
        return {"name": "LLM Provider", "status": "degraded", "provider": provider, "latencyMs": round(latency, 1), "note": "No API key set"}
    except Exception as exc:
        return {"name": "LLM Provider", "status": "unhealthy", "error": str(exc)[:200], "latencyMs": round((time.perf_counter() - t0) * 1000, 1)}


async def _check_git() -> Dict[str, Any]:
    """Check that the git binary is available."""
    t0 = time.perf_counter()
    git_path = shutil.which("git")
    latency = (time.perf_counter() - t0) * 1000
    if git_path:
        return {"name": "Git", "status": "healthy", "path": git_path, "latencyMs": round(latency, 1)}
    return {"name": "Git", "status": "unhealthy", "error": "git binary not found on PATH", "latencyMs": round(latency, 1)}


async def _check_vector_store() -> Dict[str, Any]:
    """Check the local vector store status."""
    t0 = time.perf_counter()
    try:
        from code4u.ai_engine.vector_store import get_local_vector_store
        store = get_local_vector_store()
        stats = store.stats()
        latency = (time.perf_counter() - t0) * 1000
        return {
            "name": "Vector Store",
            "status": "healthy",
            "backend": stats["backend"],
            "documentCount": stats["documentCount"],
            "hasFaiss": stats["hasFaiss"],
            "latencyMs": round(latency, 1),
        }
    except Exception as exc:
        return {"name": "Vector Store", "status": "unhealthy", "error": str(exc)[:200], "latencyMs": round((time.perf_counter() - t0) * 1000, 1)}


async def _check_disk() -> Dict[str, Any]:
    """Check available disk space."""
    t0 = time.perf_counter()
    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        pct_free = (usage.free / usage.total) * 100
        latency = (time.perf_counter() - t0) * 1000
        status = "healthy" if pct_free > 10 else ("degraded" if pct_free > 5 else "unhealthy")
        return {
            "name": "Disk Space",
            "status": status,
            "freeGb": round(free_gb, 1),
            "totalGb": round(total_gb, 1),
            "freePercent": round(pct_free, 1),
            "latencyMs": round(latency, 1),
        }
    except Exception as exc:
        return {"name": "Disk Space", "status": "unhealthy", "error": str(exc)[:200], "latencyMs": round((time.perf_counter() - t0) * 1000, 1)}


async def _check_airgap() -> Dict[str, Any]:
    """Report air-gapped mode status."""
    t0 = time.perf_counter()
    try:
        from code4u.interfaces.api.routes.airgap import is_air_gapped
        enabled = is_air_gapped()
        latency = (time.perf_counter() - t0) * 1000
        return {
            "name": "Air-Gapped Mode",
            "status": "active" if enabled else "inactive",
            "enabled": enabled,
            "latencyMs": round(latency, 1),
        }
    except Exception as exc:
        return {"name": "Air-Gapped Mode", "status": "unknown", "error": str(exc)[:200], "latencyMs": round((time.perf_counter() - t0) * 1000, 1)}


# ---------------------------------------------------------------------------
# Doctor endpoint
# ---------------------------------------------------------------------------

@router.get("/health/doctor")
async def system_doctor() -> Dict[str, Any]:
    """Run all health probes and return a readiness report.

    Returns a readiness score from 0-100 based on the number of healthy
    subsystems, plus detailed per-probe results.
    """
    probes = [
        _check_database,
        _check_redis,
        _check_llm_provider,
        _check_git,
        _check_vector_store,
        _check_disk,
        _check_airgap,
    ]

    results: List[Dict[str, Any]] = []
    for probe in probes:
        try:
            result = await probe()
            results.append(result)
        except Exception as exc:
            results.append({"name": probe.__name__, "status": "error", "error": str(exc)[:200]})

    scoreable = [r for r in results if r.get("status") not in ("active", "inactive", "unknown")]
    healthy_count = sum(1 for r in scoreable if r["status"] == "healthy")
    total_count = len(scoreable) or 1
    readiness_score = round((healthy_count / total_count) * 100)

    overall = "healthy"
    if readiness_score < 100:
        overall = "degraded"
    if readiness_score < 50:
        overall = "unhealthy"

    logger.info("doctor_check", readiness=readiness_score, overall=overall)

    return {
        "overall": overall,
        "readinessScore": readiness_score,
        "timestamp": time.time(),
        "probes": results,
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
    }
