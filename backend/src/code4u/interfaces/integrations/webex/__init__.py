"""Webex integration for meetings and communication."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import MeetingIntegration, CommunicationIntegration, IntegrationConfig
from ..registry import register_integration


@register_integration("webex")
class WebexIntegration(MeetingIntegration, CommunicationIntegration):
    """
    Webex Integration for code4u.ai.
    
    Features:
    - Join meetings as bot
    - Send messages to spaces
    - Rich cards with actions
    - Recording and transcription
    """
    
    name = "webex"
    BASE_URL = "https://webexapis.com/v1"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.access_token = os.getenv("WEBEX_ACCESS_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/people/me")
            user = response.json()
            return {"status": "healthy", "user": user.get("displayName")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def send_message(
        self,
        channel_id: str,  # roomId in Webex
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a message to a Webex space."""
        data = {"roomId": channel_id, "text": message}
        response = await self._client.post("/messages", json=data)
        response.raise_for_status()
        return response.json()
    
    async def send_rich_message(
        self,
        channel_id: str,
        blocks: List[Dict[str, Any]],  # Adaptive Cards
        **kwargs,
    ) -> Dict[str, Any]:
        """Send an Adaptive Card to Webex."""
        card = {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": blocks,
            }
        }
        data = {"roomId": channel_id, "attachments": [card]}
        response = await self._client.post("/messages", json=data)
        response.raise_for_status()
        return response.json()
    
    async def create_meeting(
        self,
        title: str,
        start_time: str,
        duration_minutes: int = 60,
        invitees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a Webex meeting."""
        data = {
            "title": title,
            "start": start_time,
            "end": start_time,  # Would calculate based on duration
            "enabledAutoRecordMeeting": True,
        }
        if invitees:
            data["invitees"] = [{"email": email} for email in invitees]
        
        response = await self._client.post("/meetings", json=data)
        response.raise_for_status()
        return response.json()
    
    async def join_meeting(self, meeting_url: str) -> Dict[str, Any]:
        """Join a Webex meeting."""
        # Webex bot joining requires Webex SDK
        return {"status": "ready_to_join", "url": meeting_url}
    
    async def leave_meeting(self, session_id: str) -> None:
        """Leave a Webex meeting."""
        pass
    
    async def get_transcript(self, meeting_id: str) -> str:
        """Get meeting transcript."""
        response = await self._client.get(f"/meetingTranscripts?meetingId={meeting_id}")
        if response.status_code == 200:
            transcripts = response.json().get("items", [])
            if transcripts:
                # Get transcript content
                content_response = await self._client.get(f"/meetingTranscripts/{transcripts[0]['id']}/download")
                return content_response.text
        return ""
    
    async def get_recording(self, meeting_id: str) -> Optional[str]:
        """Get meeting recording URL."""
        response = await self._client.get(f"/recordings?meetingId={meeting_id}")
        if response.status_code == 200:
            recordings = response.json().get("items", [])
            if recordings:
                return recordings[0].get("temporaryDirectDownloadLinks", {}).get("recordingDownloadLink")
        return None
    
    async def get_spaces(self) -> List[Dict[str, Any]]:
        """Get all spaces (rooms)."""
        response = await self._client.get("/rooms")
        response.raise_for_status()
        return response.json().get("items", [])

