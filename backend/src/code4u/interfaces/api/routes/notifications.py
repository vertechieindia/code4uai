"""Notification Bridge — Slack/Teams webhook integration for swarm results.

Endpoints:
  - ``POST /notifications/slack-webhook``  — configure Slack webhook URL.
  - ``POST /notifications/teams-webhook``  — configure Teams webhook URL.
  - ``POST /notifications/send``           — send a notification to configured channels.
  - ``POST /notifications/swarm-summary``  — format and send a swarm completion summary.
  - ``GET  /notifications/config``         — get current webhook configuration.
  - ``GET  /notifications``                — list recent notifications.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory store for webhook config and history
# ---------------------------------------------------------------------------

_webhook_config: Dict[str, str] = {}
_notification_log: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class SlackWebhookConfig(BaseModel):
    webhookUrl: str = Field(..., description="Slack Incoming Webhook URL.")
    channel: str = Field("#engineering", description="Target channel.")
    enabled: bool = Field(True, description="Whether Slack notifications are enabled.")


class TeamsWebhookConfig(BaseModel):
    webhookUrl: str = Field(..., description="Teams Incoming Webhook URL.")
    enabled: bool = Field(True, description="Whether Teams notifications are enabled.")


class NotificationSendRequest(BaseModel):
    channel: str = Field("slack", description="Channel: slack | teams | all.")
    title: str = Field(..., description="Notification title.")
    body: str = Field(..., description="Notification body.")
    severity: str = Field("info", description="info | warning | error | success.")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SwarmSummaryRequest(BaseModel):
    graphId: str = Field("", description="Swarm graph ID.")
    goal: str = Field("", description="Original swarm goal.")
    filesRefactored: int = Field(0, description="Number of files refactored.")
    healingLoops: int = Field(0, description="Number of healing loops used.")
    securityViolations: int = Field(0, description="Number of security violations.")
    duration_ms: float = Field(0, description="Total duration in ms.")
    success: bool = Field(True, description="Whether the swarm succeeded.")
    approvalStatus: str = Field("none", description="Approval gate status.")


# ---------------------------------------------------------------------------
# Slack/Teams message formatting
# ---------------------------------------------------------------------------

def _format_slack_message(
    title: str,
    body: str,
    severity: str = "info",
    fields: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    emoji_map = {
        "success": ":white_check_mark:",
        "error": ":x:",
        "warning": ":warning:",
        "info": ":information_source:",
    }
    color_map = {
        "success": "#36a64f",
        "error": "#e01e5a",
        "warning": "#ecb22e",
        "info": "#36c5f0",
    }
    emoji = emoji_map.get(severity, ":robot_face:")
    color = color_map.get(severity, "#36c5f0")

    attachment: Dict[str, Any] = {
        "color": color,
        "title": f"{emoji} {title}",
        "text": body,
        "footer": "code4u.ai Swarm Engine",
        "ts": int(time.time()),
    }
    if fields:
        attachment["fields"] = [
            {"title": f["title"], "value": f["value"], "short": f.get("short", True)}
            for f in fields
        ]

    return {"attachments": [attachment]}


def _format_teams_message(
    title: str,
    body: str,
    severity: str = "info",
    fields: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    color_map = {
        "success": "00ff00",
        "error": "ff0000",
        "warning": "ffcc00",
        "info": "0078d7",
    }
    color = color_map.get(severity, "0078d7")

    facts = []
    if fields:
        facts = [{"name": f["title"], "value": f["value"]} for f in fields]

    return {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": title,
        "sections": [
            {
                "activityTitle": title,
                "activitySubtitle": "code4u.ai Swarm Engine",
                "facts": facts,
                "text": body,
            }
        ],
    }


def _format_swarm_summary(req: SwarmSummaryRequest) -> tuple[str, str, str, list]:
    status = "success" if req.success else "error"
    icon = "+" if req.success else "x"

    title = f"Swarm {'Completed' if req.success else 'Failed'}: {req.goal[:60]}"
    body = (
        f"{icon} {req.filesRefactored} files refactored, "
        f"{req.healingLoops} healing loops used, "
        f"{req.securityViolations} security violations."
    )

    if req.approvalStatus not in ("none", ""):
        body += f"\nApproval: {req.approvalStatus}"

    fields = [
        {"title": "Files Changed", "value": str(req.filesRefactored), "short": True},
        {"title": "Healing Loops", "value": str(req.healingLoops), "short": True},
        {"title": "Security Issues", "value": str(req.securityViolations), "short": True},
        {"title": "Duration", "value": f"{req.duration_ms / 1000:.1f}s", "short": True},
    ]

    return title, body, status, fields


async def _send_to_slack(payload: Dict[str, Any]) -> bool:
    url = _webhook_config.get("slack_url", "")
    if not url:
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False


async def _send_to_teams(payload: Dict[str, Any]) -> bool:
    url = _webhook_config.get("teams_url", "")
    if not url:
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/notifications/slack-webhook")
async def configure_slack(config: SlackWebhookConfig):
    """Configure Slack webhook URL for notifications."""
    _webhook_config["slack_url"] = config.webhookUrl
    _webhook_config["slack_channel"] = config.channel
    _webhook_config["slack_enabled"] = str(config.enabled)
    return {"status": "configured", "channel": config.channel, "enabled": config.enabled}


@router.post("/notifications/teams-webhook")
async def configure_teams(config: TeamsWebhookConfig):
    """Configure Teams webhook URL for notifications."""
    _webhook_config["teams_url"] = config.webhookUrl
    _webhook_config["teams_enabled"] = str(config.enabled)
    return {"status": "configured", "enabled": config.enabled}


@router.get("/notifications/config")
async def get_config():
    """Get current notification webhook configuration."""
    return {
        "slack": {
            "configured": bool(_webhook_config.get("slack_url")),
            "channel": _webhook_config.get("slack_channel", "#engineering"),
            "enabled": _webhook_config.get("slack_enabled", "true") == "true",
        },
        "teams": {
            "configured": bool(_webhook_config.get("teams_url")),
            "enabled": _webhook_config.get("teams_enabled", "true") == "true",
        },
    }


@router.post("/notifications/send")
async def send_notification(request: NotificationSendRequest):
    """Send a notification to configured channels."""
    results: Dict[str, Any] = {"sent": [], "failed": []}

    entry = {
        "title": request.title,
        "body": request.body,
        "severity": request.severity,
        "channel": request.channel,
        "timestamp": time.time(),
        "metadata": request.metadata,
    }

    if request.channel in ("slack", "all"):
        payload = _format_slack_message(
            request.title, request.body, request.severity
        )
        ok = await _send_to_slack(payload)
        entry["slack_sent"] = ok
        (results["sent"] if ok else results["failed"]).append("slack")

    if request.channel in ("teams", "all"):
        payload = _format_teams_message(
            request.title, request.body, request.severity
        )
        ok = await _send_to_teams(payload)
        entry["teams_sent"] = ok
        (results["sent"] if ok else results["failed"]).append("teams")

    if request.channel not in ("slack", "teams", "all"):
        entry["in_app"] = True
        results["sent"].append("in_app")

    _notification_log.append(entry)
    return results


@router.post("/notifications/swarm-summary")
async def send_swarm_summary(request: SwarmSummaryRequest):
    """Format and send a swarm completion summary to all configured channels."""
    title, body, severity, fields = _format_swarm_summary(request)

    results: Dict[str, Any] = {"sent": [], "failed": [], "simulated": False}

    slack_url = _webhook_config.get("slack_url", "")
    teams_url = _webhook_config.get("teams_url", "")

    if slack_url:
        payload = _format_slack_message(title, body, severity, fields)
        ok = await _send_to_slack(payload)
        (results["sent"] if ok else results["failed"]).append("slack")
    else:
        results["sent"].append("slack_simulated")
        results["simulated"] = True

    if teams_url:
        payload = _format_teams_message(title, body, severity, fields)
        ok = await _send_to_teams(payload)
        (results["sent"] if ok else results["failed"]).append("teams")

    entry = {
        "title": title,
        "body": body,
        "severity": severity,
        "channel": "swarm_summary",
        "timestamp": time.time(),
        "graphId": request.graphId,
        "fields": fields,
    }
    _notification_log.append(entry)

    return {
        **results,
        "title": title,
        "body": body,
        "severity": severity,
    }


@router.get("/notifications")
async def list_notifications(limit: int = 20):
    """List recent notifications."""
    items = sorted(_notification_log, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]
    return {"notifications": items, "total": len(_notification_log)}
