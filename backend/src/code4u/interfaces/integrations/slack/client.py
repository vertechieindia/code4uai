"""Slack API client."""

from __future__ import annotations
import os
from typing import Optional, Dict, Any, List
import httpx


class SlackClient:
    """HTTP client for Slack API."""
    
    BASE_URL = "https://slack.com/api"
    
    def __init__(self, token: Optional[str] = None):
        """Initialize Slack client.
        
        Args:
            token: Bot token
        """
        self.token = token or os.getenv("SLACK_BOT_TOKEN", "")
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
    
    async def post_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Post a message to a channel."""
        payload = {
            "channel": channel,
            "text": text,
        }
        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts
        
        response = await self._client.post("/chat.postMessage", json=payload)
        return response.json()
    
    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Update an existing message."""
        payload = {
            "channel": channel,
            "ts": ts,
            "text": text,
        }
        if blocks:
            payload["blocks"] = blocks
        
        response = await self._client.post("/chat.update", json=payload)
        return response.json()
    
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user information."""
        response = await self._client.get("/users.info", params={"user": user_id})
        return response.json()
    
    async def close(self) -> None:
        """Close the client."""
        await self._client.aclose()

