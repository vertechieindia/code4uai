"""Nexus API — multi-repo organizational intelligence.

Endpoints:
  - ``POST /nexus/scan``       — scan a parent directory for repos.
  - ``POST /nexus/index``      — index all discovered repos.
  - ``POST /nexus/link``       — discover cross-repo dependencies.
  - ``GET  /nexus/summary``    — full nexus summary.
  - ``GET  /nexus/impact/{symbol}`` — cross-repo blast radius.
  - ``GET  /nexus/high-risk``  — symbols affecting multiple repos.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from code4u.core.nexus import NexusContext
from code4u.agents.nexus.impact_analyzer import ImpactAnalyzer

router = APIRouter()


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_nexus: Optional[NexusContext] = None


def _get_nexus() -> NexusContext:
    if _nexus is None:
        raise HTTPException(status_code=409, detail="Nexus not initialized. POST /nexus/scan first.")
    return _nexus


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class NexusScanRequest(BaseModel):
    rootPath: str = Field(..., description="Parent directory containing repos.")
    maxDepth: int = Field(2, description="Max directory depth to scan.")


class NexusIndexRequest(BaseModel):
    repoName: str = Field("", description="Optional: index a specific repo.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/nexus/scan")
async def scan_nexus(request: NexusScanRequest):
    """Scan a directory for repositories."""
    global _nexus
    _nexus = NexusContext(request.rootPath, max_depth=request.maxDepth)
    repos = _nexus.scan()
    return {
        "repoCount": len(repos),
        "repos": [r.to_dict() for r in repos],
    }


@router.post("/nexus/index")
async def index_nexus(request: NexusIndexRequest = NexusIndexRequest()):
    """Index all (or one) discovered repos."""
    nexus = _get_nexus()

    if request.repoName:
        info = nexus.index_repo(request.repoName)
        if not info:
            raise HTTPException(404, f"Repo '{request.repoName}' not found.")
        return {"repo": info.to_dict()}

    result = nexus.index_all()
    return {
        "indexed": len(result),
        "repos": {k: v.to_dict() for k, v in result.items()},
    }


@router.post("/nexus/link")
async def link_nexus():
    """Discover cross-repo dependencies."""
    nexus = _get_nexus()
    edges = nexus.link_repos()
    return {
        "crossEdges": len(edges),
        "edges": [e.to_dict() for e in edges[:50]],
    }


@router.get("/nexus/summary")
async def nexus_summary():
    """Full nexus summary."""
    nexus = _get_nexus()
    return nexus.summary()


@router.get("/nexus/impact/{symbol_name}")
async def nexus_impact(symbol_name: str):
    """Calculate cross-repo blast radius for a symbol."""
    nexus = _get_nexus()
    analyzer = ImpactAnalyzer(nexus.registry)
    blast = analyzer.analyze(symbol_name)
    return blast.to_dict()


@router.get("/nexus/high-risk")
async def nexus_high_risk(min_repos: int = 2):
    """Find high-risk symbols that affect multiple repos."""
    nexus = _get_nexus()
    analyzer = ImpactAnalyzer(nexus.registry)
    results = analyzer.high_risk_symbols(min_repos=min_repos)
    return {
        "highRiskSymbols": [b.to_dict() for b in results],
        "count": len(results),
    }
