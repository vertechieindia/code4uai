"""NVD Vulnerability Watch API routes.

Endpoints:
  - POST /nvd/watch/configure     — set packages to watch
  - POST /nvd/watch/poll          — trigger manual NVD poll
  - GET  /nvd/watch/status        — get watch status
  - GET  /nvd/watch/alerts        — get recorded alerts
  - POST /nvd/watch/check          — check specific packages against NVD
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from code4u.security_compliance.security.vulnerability_scanner import NVDFeed

router = APIRouter(prefix="/nvd/watch", tags=["NVD Watch"])

_nvd_feed: Optional[NVDFeed] = None


def _get_nvd_feed() -> NVDFeed:
    global _nvd_feed
    if _nvd_feed is None:
        _nvd_feed = NVDFeed()
    return _nvd_feed


class ConfigureWatchRequest(BaseModel):
    """Request to configure packages to watch."""
    packages: Dict[str, str] = Field(
        default_factory=dict,
        description="Package name -> version mapping to monitor",
    )


class PollRequest(BaseModel):
    """Request to trigger manual NVD poll."""
    keyword: str = Field("", description="Keyword or package name to search")


class CheckPackagesRequest(BaseModel):
    """Request to check specific packages against NVD."""
    packages: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of {name, version} or {package, version}",
    )


@router.post("/configure")
async def configure_watch(request: ConfigureWatchRequest) -> Dict[str, Any]:
    """Set packages to watch for CVE alerts."""
    feed = _get_nvd_feed()
    feed.set_watch_list(request.packages)
    return {"status": "configured", "watching": len(request.packages)}


@router.post("/poll")
async def trigger_poll(request: PollRequest) -> Dict[str, Any]:
    """Trigger manual NVD poll for a keyword."""
    feed = _get_nvd_feed()
    if not request.keyword:
        raise HTTPException(status_code=400, detail="keyword required")
    results = await feed.poll_nvd(keyword=request.keyword)
    return {"keyword": request.keyword, "findings": results, "count": len(results)}


@router.get("/status")
async def get_watch_status() -> Dict[str, Any]:
    """Get current watch status."""
    feed = _get_nvd_feed()
    return feed.get_watch_status()


@router.get("/alerts")
async def get_alerts() -> Dict[str, Any]:
    """Get recorded alerts."""
    feed = _get_nvd_feed()
    alerts = feed.get_alerts()
    return {"alerts": alerts, "total": len(alerts)}


@router.post("/check")
async def check_packages(request: CheckPackagesRequest) -> Dict[str, Any]:
    """Check specific packages against NVD for known CVEs."""
    feed = _get_nvd_feed()
    if not request.packages:
        packages = feed.get_watch_list_packages()
        if not packages:
            return {"findings": [], "checked": 0}
    else:
        packages = request.packages

    findings = await feed.check_dependencies(packages)
    return {"findings": findings, "checked": len(packages)}
