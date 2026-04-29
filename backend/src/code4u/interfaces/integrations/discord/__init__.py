"""Discord integration for communication."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import CommunicationIntegration, IntegrationConfig
from ..registry import register_integration


@register_integration("discord")
class DiscordIntegration(CommunicationIntegration):
    """
    Discord Integration for code4u.ai.
    
    Features:
    - Send messages to channels
    - Slash commands
    - Rich embeds
    - Approval workflows with reactions
    """
    
    name = "discord"
    BASE_URL = "https://discord.com/api/v10"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bot {self.bot_token}"},
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/users/@me")
            return {"status": "healthy", "bot": response.json().get("username")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def send_message(
        self,
        channel_id: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a message to a Discord channel."""
        data = {"content": message}
        response = await self._client.post(f"/channels/{channel_id}/messages", json=data)
        response.raise_for_status()
        return response.json()
    
    async def send_rich_message(
        self,
        channel_id: str,
        blocks: List[Dict[str, Any]],  # Discord embeds
        **kwargs,
    ) -> Dict[str, Any]:
        """Send an embed to Discord."""
        data = {"embeds": blocks}
        if kwargs.get("content"):
            data["content"] = kwargs["content"]
        response = await self._client.post(f"/channels/{channel_id}/messages", json=data)
        response.raise_for_status()
        return response.json()
    
    async def send_approval_request(
        self,
        channel_id: str,
        title: str,
        description: str,
        requirements: List[Dict[str, Any]],
        approval_id: str,
    ) -> Dict[str, Any]:
        """Send an approval request with action buttons."""
        embed = {
            "title": f"📋 {title}",
            "description": description,
            "color": 0x00D4AA,
            "fields": [
                {"name": f"{i+1}. {req['title']}", "value": req.get('description', '')[:100], "inline": False}
                for i, req in enumerate(requirements[:5])
            ],
            "footer": {"text": f"Approval ID: {approval_id}"},
        }
        
        # Discord uses components for buttons
        data = {
            "embeds": [embed],
            "components": [
                {
                    "type": 1,  # Action Row
                    "components": [
                        {"type": 2, "style": 3, "label": "✅ Approve", "custom_id": f"approve_{approval_id}"},
                        {"type": 2, "style": 1, "label": "✏️ Edit", "custom_id": f"edit_{approval_id}"},
                        {"type": 2, "style": 4, "label": "❌ Reject", "custom_id": f"reject_{approval_id}"},
                    ],
                }
            ],
        }
        
        response = await self._client.post(f"/channels/{channel_id}/messages", json=data)
        response.raise_for_status()
        return response.json()
    
    async def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        """Add a reaction to a message."""
        await self._client.put(
            f"/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me"
        )
    
    async def get_guilds(self) -> List[Dict[str, Any]]:
        """Get all guilds the bot is in."""
        response = await self._client.get("/users/@me/guilds")
        response.raise_for_status()
        return response.json()
    
    async def get_channels(self, guild_id: str) -> List[Dict[str, Any]]:
        """Get channels in a guild."""
        response = await self._client.get(f"/guilds/{guild_id}/channels")
        response.raise_for_status()
        return response.json()

