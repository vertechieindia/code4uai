"""Requirement presenter for team approval workflow."""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..base import Requirement, MeetingMinutes


class RequirementPresenter:
    """
    Presents extracted requirements to team for approval.
    
    Features:
    - Format requirements for Slack/Teams/Discord
    - Create interactive approval buttons
    - Track approval status
    - Allow editing before approval
    - Trigger task creation after approval
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize presenter.
        
        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}
    
    async def present(
        self,
        minutes: MeetingMinutes,
        channel: str,
        approvers: List[str],
        platform: str = "slack",
    ) -> Dict[str, Any]:
        """Present meeting minutes and requirements for approval.
        
        Args:
            minutes: Meeting minutes with requirements
            channel: Channel to post to
            approvers: List of approver IDs
            platform: Target platform (slack, teams, discord)
            
        Returns:
            Presentation result
        """
        approval_id = str(uuid.uuid4())
        
        # Store approval request
        self._pending_approvals[approval_id] = {
            "minutes": minutes,
            "channel": channel,
            "approvers": approvers,
            "approved_by": [],
            "rejected_by": [],
            "status": "pending",
            "created_at": datetime.utcnow(),
        }
        
        # Format message based on platform
        if platform == "slack":
            blocks = self._format_slack_message(minutes, approval_id)
            # Would use Slack API to post
            return {
                "approval_id": approval_id,
                "platform": platform,
                "channel": channel,
                "blocks": blocks,
            }
        
        elif platform == "teams":
            card = self._format_teams_card(minutes, approval_id)
            return {
                "approval_id": approval_id,
                "platform": platform,
                "channel": channel,
                "card": card,
            }
        
        elif platform == "discord":
            embed = self._format_discord_embed(minutes, approval_id)
            return {
                "approval_id": approval_id,
                "platform": platform,
                "channel": channel,
                "embed": embed,
            }
        
        return {"approval_id": approval_id}
    
    def _format_slack_message(
        self,
        minutes: MeetingMinutes,
        approval_id: str,
    ) -> List[Dict[str, Any]]:
        """Format message for Slack."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📋 Meeting Minutes: {minutes.meeting_title}",
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary:*\n{minutes.summary}",
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Key Points:*\n" + "\n".join(f"• {p}" for p in minutes.key_points),
                }
            },
        ]
        
        # Add requirements
        if minutes.requirements:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📝 Extracted Requirements ({len(minutes.requirements)}):*",
                }
            })
            
            for i, req in enumerate(minutes.requirements, 1):
                priority_emoji = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢",
                }.get(req.priority, "⚪")
                
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{priority_emoji} *{i}. {req.title}*\n{req.description[:200]}...",
                    }
                })
        
        # Add action buttons
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve All"},
                    "style": "primary",
                    "action_id": f"approve_all_{approval_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ Edit Requirements"},
                    "action_id": f"edit_{approval_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject"},
                    "style": "danger",
                    "action_id": f"reject_{approval_id}",
                },
            ]
        })
        
        return blocks
    
    def _format_teams_card(
        self,
        minutes: MeetingMinutes,
        approval_id: str,
    ) -> Dict[str, Any]:
        """Format Adaptive Card for Microsoft Teams."""
        return {
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"📋 Meeting Minutes: {minutes.meeting_title}",
                    "size": "Large",
                    "weight": "Bolder",
                },
                {
                    "type": "TextBlock",
                    "text": minutes.summary,
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": f"Requirements: {len(minutes.requirements)}",
                    "weight": "Bolder",
                },
                *[
                    {
                        "type": "Container",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": f"**{i}. {req.title}** ({req.priority})",
                            },
                            {
                                "type": "TextBlock",
                                "text": req.description[:150],
                                "wrap": True,
                            },
                        ]
                    }
                    for i, req in enumerate(minutes.requirements, 1)
                ],
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "✅ Approve All",
                    "data": {"action": "approve", "approval_id": approval_id},
                },
                {
                    "type": "Action.Submit",
                    "title": "✏️ Edit",
                    "data": {"action": "edit", "approval_id": approval_id},
                },
                {
                    "type": "Action.Submit",
                    "title": "❌ Reject",
                    "data": {"action": "reject", "approval_id": approval_id},
                },
            ],
        }
    
    def _format_discord_embed(
        self,
        minutes: MeetingMinutes,
        approval_id: str,
    ) -> Dict[str, Any]:
        """Format embed for Discord."""
        fields = [
            {"name": "Summary", "value": minutes.summary, "inline": False},
        ]
        
        for i, req in enumerate(minutes.requirements[:5], 1):
            fields.append({
                "name": f"{i}. {req.title}",
                "value": f"**{req.priority}** - {req.description[:100]}...",
                "inline": False,
            })
        
        return {
            "title": f"📋 Meeting Minutes: {minutes.meeting_title}",
            "color": 0x00D4AA,
            "fields": fields,
            "footer": {"text": f"Approval ID: {approval_id}"},
        }
    
    async def handle_approval(
        self,
        approval_id: str,
        user_id: str,
        action: str,
        modifications: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Handle an approval action.
        
        Args:
            approval_id: Approval request ID
            user_id: User taking action
            action: approve, reject, or edit
            modifications: Optional modifications to requirements
            
        Returns:
            Result of action
        """
        approval = self._pending_approvals.get(approval_id)
        if not approval:
            return {"error": "Approval not found"}
        
        if action == "approve":
            approval["approved_by"].append(user_id)
            
            # Check if all approvers have approved
            if set(approval["approved_by"]) >= set(approval["approvers"]):
                approval["status"] = "approved"
                
                # Trigger task creation
                result = await self._create_tasks(approval)
                return {
                    "status": "approved",
                    "tasks_created": result.get("count", 0),
                }
            
            return {
                "status": "pending",
                "approved_by": len(approval["approved_by"]),
                "required": len(approval["approvers"]),
            }
        
        elif action == "reject":
            approval["rejected_by"].append(user_id)
            approval["status"] = "rejected"
            return {"status": "rejected"}
        
        elif action == "edit":
            if modifications:
                # Update requirements based on modifications
                minutes = approval["minutes"]
                for mod in modifications.get("requirements", []):
                    for req in minutes.requirements:
                        if req.id == mod.get("id"):
                            req.title = mod.get("title", req.title)
                            req.description = mod.get("description", req.description)
                            req.priority = mod.get("priority", req.priority)
                            req.type = mod.get("type", req.type)
            
            return {"status": "edited"}
        
        return {"error": "Invalid action"}
    
    async def _create_tasks(self, approval: Dict[str, Any]) -> Dict[str, Any]:
        """Create tasks from approved requirements.
        
        Args:
            approval: Approval data
            
        Returns:
            Task creation result
        """
        minutes = approval["minutes"]
        created = []
        
        for req in minutes.requirements:
            req.status = "approved"
            req.approved_at = datetime.utcnow()
            req.approved_by = approval["approved_by"]
            
            # Here we would trigger the agent to work on the requirement
            # from code4u.platform_core.agents import Orchestrator
            # orchestrator = Orchestrator()
            # await orchestrator.execute_from_requirement(req)
            
            created.append(req.id)
        
        return {"count": len(created), "requirement_ids": created}
    
    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get all pending approvals."""
        return [
            {
                "id": aid,
                "meeting_title": data["minutes"].meeting_title,
                "requirements_count": len(data["minutes"].requirements),
                "status": data["status"],
                "approved_by": len(data["approved_by"]),
                "required": len(data["approvers"]),
            }
            for aid, data in self._pending_approvals.items()
            if data["status"] == "pending"
        ]

