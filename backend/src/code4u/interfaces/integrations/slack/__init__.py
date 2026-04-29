"""Slack integration for communication."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import CommunicationIntegration, IntegrationConfig
from ..registry import register_integration


@register_integration("slack")
class SlackIntegration(CommunicationIntegration):
    """
    Slack Integration for code4u.ai.
    
    Features:
    - Send messages to channels
    - Slash commands
    - Rich Block Kit messages
    - Approval workflows with buttons
    - File uploads
    - Thread replies
    """
    
    name = "slack"
    BASE_URL = "https://slack.com/api"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.bot_token = os.getenv("SLACK_BOT_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self.bot_token}"},
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/auth.test")
            data = response.json()
            if data.get("ok"):
                return {"status": "healthy", "team": data.get("team"), "bot": data.get("user")}
            return {"status": "error", "error": data.get("error")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def send_message(
        self,
        channel_id: str,
        message: str,
        thread_ts: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a message to a Slack channel."""
        data = {
            "channel": channel_id,
            "text": message,
        }
        if thread_ts:
            data["thread_ts"] = thread_ts
        
        response = await self._client.post("/chat.postMessage", json=data)
        result = response.json()
        
        if not result.get("ok"):
            raise Exception(result.get("error"))
        
        return result
    
    async def send_rich_message(
        self,
        channel_id: str,
        blocks: List[Dict[str, Any]],
        text: str = "",
        thread_ts: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a Block Kit message to Slack."""
        data = {
            "channel": channel_id,
            "blocks": blocks,
            "text": text or "Message from code4u.ai",
        }
        if thread_ts:
            data["thread_ts"] = thread_ts
        
        response = await self._client.post("/chat.postMessage", json=data)
        result = response.json()
        
        if not result.get("ok"):
            raise Exception(result.get("error"))
        
        return result
    
    async def send_approval_request(
        self,
        channel_id: str,
        title: str,
        description: str,
        requirements: List[Dict[str, Any]],
        approval_id: str,
        approvers: List[str],
    ) -> Dict[str, Any]:
        """Send an approval request with action buttons."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📋 {title}"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": description}
            },
            {"type": "divider"},
        ]
        
        # Add requirements
        for i, req in enumerate(requirements[:5], 1):
            priority_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(req.get("priority", "medium"), "⚪")
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{priority_emoji} *{i}. {req.get('title', '')}*\n{req.get('description', '')[:150]}..."
                }
            })
        
        if len(requirements) > 5:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"_...and {len(requirements) - 5} more requirements_"}]
            })
        
        # Add approvers mention
        approver_mentions = " ".join([f"<@{uid}>" for uid in approvers])
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Awaiting approval from: {approver_mentions}"}]
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
                    "value": approval_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ Edit Requirements"},
                    "action_id": f"edit_{approval_id}",
                    "value": approval_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject"},
                    "style": "danger",
                    "action_id": f"reject_{approval_id}",
                    "value": approval_id,
                },
            ]
        })
        
        return await self.send_rich_message(channel_id, blocks, title)
    
    async def update_message(
        self,
        channel_id: str,
        message_ts: str,
        blocks: List[Dict[str, Any]],
        text: str = "",
    ) -> Dict[str, Any]:
        """Update a message."""
        data = {
            "channel": channel_id,
            "ts": message_ts,
            "blocks": blocks,
            "text": text or "Message from code4u.ai",
        }
        
        response = await self._client.post("/chat.update", json=data)
        return response.json()
    
    async def add_reaction(
        self,
        channel_id: str,
        message_ts: str,
        emoji: str,
    ) -> Dict[str, Any]:
        """Add a reaction to a message."""
        data = {
            "channel": channel_id,
            "timestamp": message_ts,
            "name": emoji,
        }
        response = await self._client.post("/reactions.add", json=data)
        return response.json()
    
    async def get_channels(self) -> List[Dict[str, Any]]:
        """Get all channels."""
        response = await self._client.get("/conversations.list")
        result = response.json()
        return result.get("channels", [])
    
    async def get_users(self) -> List[Dict[str, Any]]:
        """Get all users."""
        response = await self._client.get("/users.list")
        result = response.json()
        return result.get("members", [])
    
    async def upload_file(
        self,
        channel_id: str,
        file_content: bytes,
        filename: str,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a file to a channel."""
        # Use files.upload endpoint
        response = await self._client.post(
            "/files.upload",
            data={
                "channels": channel_id,
                "filename": filename,
                "title": title or filename,
            },
            files={"file": (filename, file_content)},
        )
        return response.json()
