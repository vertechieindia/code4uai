"""Analytics API — ROI dashboard, review metrics, and recipe heatmap.

Endpoints:
  - ``GET /analytics/summary``     — full savings report.
  - ``GET /analytics/recent``      — last N review audits.
  - ``GET /analytics/heatmap``     — noisiest recipes ranked.
  - ``POST /analytics/audit``      — record a review audit.
  - ``POST /analytics/accept``     — mark suggestions as accepted.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from code4u.models.analytics import AuditStore, ReviewAudit

router = APIRouter()

_store = AuditStore()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AuditRecordRequest(BaseModel):
    repoName: str = Field(..., description="Full repo name (e.g. org/repo).")
    prId: int = Field(..., description="Pull request number.")
    prUrl: str = Field("", description="PR HTML URL.")
    author: str = Field("", description="PR author login.")
    headSha: str = Field("", description="Head commit SHA.")
    suggestionsCount: int = Field(0, description="Number of suggestions posted.")
    acceptedCount: int = Field(0, description="Number of suggestions accepted.")
    triggeredRecipes: List[str] = Field(default_factory=list, description="Recipe IDs triggered.")
    filesReviewed: int = Field(0, description="Files reviewed.")
    reviewDurationMs: float = Field(0.0, description="Review duration in ms.")


class AcceptRequest(BaseModel):
    repoName: str
    prId: int
    acceptedCount: int = Field(..., description="Number of newly accepted suggestions.")


# ---------------------------------------------------------------------------
# GET /analytics/summary
# ---------------------------------------------------------------------------

@router.get("/analytics/summary")
async def analytics_summary(
    since_days: Optional[int] = Query(None, description="Limit to last N days."),
):
    """Return the full savings report.

    Example response::

        {
          "totalReviews": 48,
          "totalSuggestions": 156,
          "totalAccepted": 92,
          "adoptionRate": 0.59,
          "totalMinutesSaved": 460,
          "totalDaysSaved": 0.96,
          "repos": { "org/api": { ... }, "org/web": { ... } },
          "topRecipes": [ { "recipeId": "use-pathlib", "triggerCount": 31 } ],
          "humanSummary": "Code4u saved 7.7 hours across 4 repositories."
        }
    """
    since_ts = 0.0
    if since_days:
        since_ts = time.time() - (since_days * 86400)

    data = _store.summary(since_ts=since_ts)

    repo_count = len(data["repos"])
    hours = round(data["totalMinutesSaved"] / 60, 1)
    data["humanSummary"] = (
        f"Code4u saved {hours} hours of manual review time "
        f"across {repo_count} repositor{'y' if repo_count == 1 else 'ies'}."
    )

    return data


# ---------------------------------------------------------------------------
# GET /analytics/recent
# ---------------------------------------------------------------------------

@router.get("/analytics/recent")
async def analytics_recent(
    limit: int = Query(20, ge=1, le=200, description="Number of records to return."),
):
    """Return the most recent review audit records."""
    records = _store.load_recent(limit=limit)
    return {
        "count": len(records),
        "records": [r.to_dict() for r in records],
    }


# ---------------------------------------------------------------------------
# GET /analytics/heatmap
# ---------------------------------------------------------------------------

@router.get("/analytics/heatmap")
async def recipe_heatmap(
    since_days: Optional[int] = Query(None, description="Limit to last N days."),
):
    """Return recipes ranked by trigger frequency (noisiest first).

    Identifies team training needs — if a recipe triggers 100 times
    in a week, it signals a systemic issue worth a team-wide fix.
    """
    since_ts = 0.0
    if since_days:
        since_ts = time.time() - (since_days * 86400)

    heatmap = _store.recipe_heatmap(since_ts=since_ts)
    return {
        "recipes": heatmap,
        "count": len(heatmap),
    }


# ---------------------------------------------------------------------------
# POST /analytics/audit
# ---------------------------------------------------------------------------

@router.post("/analytics/audit")
async def record_audit(request: AuditRecordRequest):
    """Record a review audit entry.

    Called automatically by the GitHubReviewer after each PR review.
    Can also be called manually for external review tools.
    """
    audit = ReviewAudit(
        repo_name=request.repoName,
        pr_id=request.prId,
        pr_url=request.prUrl,
        author=request.author,
        head_sha=request.headSha,
        suggestions_count=request.suggestionsCount,
        accepted_count=request.acceptedCount,
        triggered_recipes=request.triggeredRecipes,
        files_reviewed=request.filesReviewed,
        review_duration_ms=request.reviewDurationMs,
    )
    _store.record(audit)
    return {"status": "recorded", "minutesSaved": audit.minutes_saved}


# ---------------------------------------------------------------------------
# POST /analytics/accept
# ---------------------------------------------------------------------------

@router.post("/analytics/accept")
async def record_acceptance(request: AcceptRequest):
    """Record that suggestions were accepted (merged) by a developer.

    This updates the adoption metrics.  Typically called by a webhook
    when the developer clicks "Accept Suggestion" on GitHub.
    """
    audit = ReviewAudit(
        repo_name=request.repoName,
        pr_id=request.prId,
        accepted_count=request.acceptedCount,
        status="accepted",
    )
    _store.record(audit)
    minutes = request.acceptedCount * 5
    return {
        "status": "recorded",
        "acceptedCount": request.acceptedCount,
        "minutesSaved": minutes,
    }
