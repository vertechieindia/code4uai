"""GitHub Webhook Handler — listens for PR events and triggers AI review.

Endpoint: ``POST /webhooks/github``

Verifies the webhook signature (``X-Hub-Signature-256``), parses
``pull_request`` events (``opened``, ``synchronize``), and dispatches
the PR to the ``GitHubReviewer`` agent for automated recipe-based
review with inline suggestion comments.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request
import structlog

logger = structlog.get_logger("webhooks.github")

router = APIRouter()

_WEBHOOK_SECRET = os.environ.get("CODE4U_GITHUB_WEBHOOK_SECRET", "")
_GITHUB_TOKEN = os.environ.get("CODE4U_GITHUB_TOKEN", "")

# Track in-flight reviews to avoid duplicate processing
_active_reviews: Dict[str, bool] = {}


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify the ``X-Hub-Signature-256`` header from GitHub.

    Returns True if the signature is valid, or if no secret is
    configured (development mode).
    """
    if not secret:
        return True

    if not signature or not signature.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Event parsing
# ---------------------------------------------------------------------------

def parse_pr_event(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract relevant fields from a ``pull_request`` webhook payload.

    Returns None if the event is not actionable (e.g. closed, labeled).
    """
    action = payload.get("action", "")
    if action not in ("opened", "synchronize", "reopened"):
        return None

    pr = payload.get("pull_request", {})
    if not pr:
        return None

    repo = payload.get("repository", {})

    return {
        "action": action,
        "pr_number": pr.get("number"),
        "pr_title": pr.get("title", ""),
        "pr_url": pr.get("html_url", ""),
        "head_sha": pr.get("head", {}).get("sha", ""),
        "base_ref": pr.get("base", {}).get("ref", ""),
        "head_ref": pr.get("head", {}).get("ref", ""),
        "repo_full_name": repo.get("full_name", ""),
        "repo_clone_url": repo.get("clone_url", ""),
        "sender": payload.get("sender", {}).get("login", ""),
        "diff_url": pr.get("diff_url", ""),
        "changed_files": pr.get("changed_files", 0),
    }


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
):
    """Receive and process GitHub webhook events.

    Currently handles ``pull_request`` events with actions
    ``opened``, ``synchronize``, and ``reopened``.
    """
    body = await request.body()

    if not verify_github_signature(body, x_hub_signature_256 or "", _WEBHOOK_SECRET):
        logger.warning("webhook_signature_invalid", delivery=x_github_delivery)
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if x_github_event == "ping":
        logger.info("webhook_ping", delivery=x_github_delivery)
        return {"status": "pong"}

    if x_github_event != "pull_request":
        logger.debug("webhook_ignored", event=x_github_event)
        return {"status": "ignored", "event": x_github_event}

    payload = await request.json()
    pr_info = parse_pr_event(payload)

    if pr_info is None:
        action = payload.get("action", "unknown")
        logger.debug("pr_action_ignored", action=action)
        return {"status": "ignored", "action": action}

    review_key = f"{pr_info['repo_full_name']}#{pr_info['pr_number']}/{pr_info['head_sha'][:8]}"

    if review_key in _active_reviews:
        logger.info("review_already_active", key=review_key)
        return {"status": "already_processing", "key": review_key}

    _active_reviews[review_key] = True

    logger.info(
        "pr_review_triggered",
        repo=pr_info["repo_full_name"],
        pr=pr_info["pr_number"],
        action=pr_info["action"],
        sha=pr_info["head_sha"][:8],
    )

    asyncio.create_task(_dispatch_review(pr_info, review_key))

    return {
        "status": "review_started",
        "repo": pr_info["repo_full_name"],
        "pr": pr_info["pr_number"],
        "sha": pr_info["head_sha"][:8],
    }


# ---------------------------------------------------------------------------
# Generic git-event webhook (push → reindex)
# ---------------------------------------------------------------------------

# Track projects by repo URL for webhook lookups
def _find_projects_by_repo(repo_url: str) -> list:
    """Find projects that were cloned from a given repo URL."""
    from code4u.interfaces.api.routes.projects import _projects

    matches = []
    normalized = repo_url.rstrip("/").rstrip(".git")
    for p in _projects.values():
        proj_url = (p.get("repoUrl") or "").rstrip("/").rstrip(".git")
        if proj_url and (proj_url == normalized or proj_url.endswith(normalized.split("/")[-1])):
            matches.append(p)
    return matches


@router.post("/webhooks/git-event")
async def git_event_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None),
):
    """Handle push events and trigger incremental reindexing.

    Supports both GitHub-formatted and generic payloads.
    A push event triggers a re-pull and re-index of the affected project.
    """
    payload = await request.json()

    event_type = x_github_event or payload.get("event", "push")

    if event_type == "ping":
        return {"status": "pong"}

    if event_type != "push":
        return {"status": "ignored", "event": event_type}

    repo_info = payload.get("repository", {})
    repo_url = repo_info.get("clone_url") or repo_info.get("html_url") or payload.get("repo_url", "")
    repo_name = repo_info.get("full_name") or payload.get("repo_name", "")

    if not repo_url and not repo_name:
        return {"status": "ignored", "reason": "no_repo_info"}

    ref = payload.get("ref", "")
    commits = payload.get("commits", [])
    changed_files = set()
    for c in commits:
        changed_files.update(c.get("added", []))
        changed_files.update(c.get("modified", []))
        changed_files.update(c.get("removed", []))

    projects = _find_projects_by_repo(repo_url or repo_name)
    if not projects:
        logger.info("git_event_no_project", repo=repo_url or repo_name)
        return {"status": "no_matching_project", "repo": repo_url or repo_name}

    reindexed = []
    for proj in projects:
        path = proj["path"]

        from code4u.core.filesystem.git_manager import GitManager
        mgr = GitManager()
        pull_result = mgr.pull(path)

        if pull_result.success:
            from code4u.interfaces.api.routes.projects import _index_workspace
            index_result = _index_workspace(path)
            proj["totalFiles"] = index_result.get("totalFiles", 0)
            proj["totalSymbols"] = index_result.get("totalSymbols", 0)
            proj["languages"] = index_result.get("languages", [])
            import time as _time
            proj["lastIndexedAt"] = _time.time()
            proj["status"] = "indexed"

            reindexed.append({
                "projectId": proj["id"],
                "name": proj["name"],
                "updated": pull_result.updated,
                "changedFiles": len(pull_result.changed_files or changed_files),
            })

            logger.info(
                "git_event_reindexed",
                project=proj["name"],
                updated=pull_result.updated,
                files=len(pull_result.changed_files or changed_files),
            )

    return {
        "status": "reindexed",
        "ref": ref,
        "repo": repo_name,
        "projects": reindexed,
    }


async def _dispatch_review(pr_info: Dict[str, Any], review_key: str) -> None:
    """Background task that runs the recipe-based PR review."""
    try:
        from code4u.agents.github_reviewer import GitHubReviewer

        reviewer = GitHubReviewer(
            github_token=_GITHUB_TOKEN,
            repo_full_name=pr_info["repo_full_name"],
        )

        await reviewer.review_pr(
            pr_number=pr_info["pr_number"],
            head_sha=pr_info["head_sha"],
        )

        logger.info("pr_review_complete", key=review_key)
    except Exception as exc:
        logger.error("pr_review_failed", key=review_key, error=str(exc)[:300])
    finally:
        _active_reviews.pop(review_key, None)
