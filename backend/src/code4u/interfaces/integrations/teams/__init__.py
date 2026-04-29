"""Microsoft Teams integration for communication and meetings."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import CommunicationIntegration, MeetingIntegration, IntegrationConfig
from ..registry import register_integration


@register_integration("teams")
class TeamsIntegration(CommunicationIntegration, MeetingIntegration):
    """
    Microsoft Teams Integration for code4u.ai.
    
    Features:
    - Send messages to channels
    - Join meetings as bot
    - Receive commands via @mentions
    - Create Adaptive Cards for rich interactions
    - Approval workflows
    """
    
    name = "teams"
    GRAPH_URL = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.tenant_id = os.getenv("TEAMS_TENANT_ID", "")
        self.client_id = os.getenv("TEAMS_CLIENT_ID", "")
        self.client_secret = os.getenv("TEAMS_CLIENT_SECRET", "")
        self._token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        # Get access token
        await self._get_token()
        self._client = httpx.AsyncClient(
            base_url=self.GRAPH_URL,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        return True
    
    async def _get_token(self) -> None:
        """Get OAuth2 access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                },
            )
            response.raise_for_status()
            self._token = response.json().get("access_token")
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/me")
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def send_message(
        self,
        channel_id: str,
        message: str,
        team_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a message to a Teams channel."""
        data = {"body": {"content": message}}
        response = await self._client.post(
            f"/teams/{team_id}/channels/{channel_id}/messages",
            json=data,
        )
        response.raise_for_status()
        return response.json()
    
    async def send_rich_message(
        self,
        channel_id: str,
        blocks: List[Dict[str, Any]],
        team_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send an Adaptive Card to Teams."""
        card = {
            "body": {
                "contentType": "html",
                "content": "<attachment id='adaptive-card'></attachment>",
            },
            "attachments": [{
                "id": "adaptive-card",
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": blocks,
                },
            }],
        }
        response = await self._client.post(
            f"/teams/{team_id}/channels/{channel_id}/messages",
            json=card,
        )
        response.raise_for_status()
        return response.json()
    
    async def create_meeting(
        self,
        subject: str,
        start_time: str,
        end_time: str,
        attendees: List[str],
    ) -> Dict[str, Any]:
        """Create a Teams meeting."""
        data = {
            "subject": subject,
            "start": {"dateTime": start_time, "timeZone": "UTC"},
            "end": {"dateTime": end_time, "timeZone": "UTC"},
            "attendees": [{"emailAddress": {"address": email}} for email in attendees],
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
        }
        response = await self._client.post("/me/events", json=data)
        response.raise_for_status()
        return response.json()
    
    async def join_meeting(self, meeting_url: str) -> Dict[str, Any]:
        """Join a Teams meeting."""
        # Teams bot joining requires Azure Bot Service
        # This is a placeholder for the actual implementation
        return {"status": "joining", "url": meeting_url}
    
    async def leave_meeting(self, session_id: str) -> None:
        """Leave a Teams meeting."""
        pass
    
    async def get_transcript(self, meeting_id: str) -> str:
        """Get meeting transcript."""
        # Teams transcripts available via Graph API
        response = await self._client.get(
            f"/me/onlineMeetings/{meeting_id}/transcripts"
        )
        if response.status_code == 200:
            transcripts = response.json().get("value", [])
            if transcripts:
                # Get content of first transcript
                content_response = await self._client.get(
                    f"/me/onlineMeetings/{meeting_id}/transcripts/{transcripts[0]['id']}/content"
                )
                return content_response.text
        return ""
    
    async def get_recording(self, meeting_id: str) -> Optional[str]:
        """Get meeting recording URL."""
        response = await self._client.get(
            f"/me/onlineMeetings/{meeting_id}/recordings"
        )
        if response.status_code == 200:
            recordings = response.json().get("value", [])
            if recordings:
                return recordings[0].get("recordingContentUrl")
        return None
    
    async def get_teams(self) -> List[Dict[str, Any]]:
        """Get all teams."""
        response = await self._client.get("/me/joinedTeams")
        response.raise_for_status()
        return response.json().get("value", [])
    
    async def get_channels(self, team_id: str) -> List[Dict[str, Any]]:
        """Get channels in a team."""
        response = await self._client.get(f"/teams/{team_id}/channels")
        response.raise_for_status()
        return response.json().get("value", [])

