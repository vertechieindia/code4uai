"""Zoom integration for meetings."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import MeetingIntegration, IntegrationConfig
from ..registry import register_integration


@register_integration("zoom")
class ZoomIntegration(MeetingIntegration):
    """
    Zoom Integration for code4u.ai.
    
    Features:
    - Join meetings as bot
    - Real-time transcription
    - Get recordings
    - Meeting insights
    """
    
    name = "zoom"
    BASE_URL = "https://api.zoom.us/v2"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.account_id = os.getenv("ZOOM_ACCOUNT_ID", "")
        self.client_id = os.getenv("ZOOM_CLIENT_ID", "")
        self.client_secret = os.getenv("ZOOM_CLIENT_SECRET", "")
        self._token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        await self._get_token()
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        return True
    
    async def _get_token(self) -> None:
        """Get OAuth2 access token using Server-to-Server OAuth."""
        import base64
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={self.account_id}",
                headers={"Authorization": f"Basic {auth}"},
            )
            response.raise_for_status()
            self._token = response.json().get("access_token")
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/users/me")
            return {"status": "healthy", "user": response.json().get("email")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def create_meeting(
        self,
        topic: str,
        start_time: str,
        duration: int = 60,
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a Zoom meeting."""
        data = {
            "topic": topic,
            "type": 2,  # Scheduled meeting
            "start_time": start_time,
            "duration": duration,
            "settings": {
                "join_before_host": True,
                "auto_recording": "cloud",
            },
        }
        response = await self._client.post("/users/me/meetings", json=data)
        response.raise_for_status()
        return response.json()
    
    async def join_meeting(self, meeting_url: str) -> Dict[str, Any]:
        """Join a Zoom meeting.
        
        Note: Actually joining requires Zoom Meeting SDK.
        This is the API-side setup.
        """
        # Extract meeting ID from URL
        meeting_id = meeting_url.split("/")[-1].split("?")[0]
        
        # Get meeting details
        response = await self._client.get(f"/meetings/{meeting_id}")
        if response.status_code == 200:
            meeting = response.json()
            return {
                "status": "ready_to_join",
                "meeting_id": meeting_id,
                "join_url": meeting.get("join_url"),
                "host_key": meeting.get("host_key"),
            }
        
        return {"status": "error", "message": "Meeting not found"}
    
    async def leave_meeting(self, session_id: str) -> None:
        """Leave a Zoom meeting."""
        # SDK would handle this
        pass
    
    async def get_transcript(self, meeting_id: str) -> str:
        """Get meeting transcript."""
        # Get recording transcript
        response = await self._client.get(f"/meetings/{meeting_id}/recordings")
        if response.status_code == 200:
            recordings = response.json().get("recording_files", [])
            for rec in recordings:
                if rec.get("file_type") == "TRANSCRIPT":
                    # Download transcript
                    transcript_response = await self._client.get(
                        rec.get("download_url"),
                        headers={"Authorization": f"Bearer {self._token}"},
                    )
                    return transcript_response.text
        return ""
    
    async def get_recording(self, meeting_id: str) -> Optional[str]:
        """Get meeting recording URL."""
        response = await self._client.get(f"/meetings/{meeting_id}/recordings")
        if response.status_code == 200:
            recordings = response.json().get("recording_files", [])
            for rec in recordings:
                if rec.get("file_type") == "MP4":
                    return rec.get("download_url")
        return None
    
    async def list_meetings(self, meeting_type: str = "scheduled") -> List[Dict[str, Any]]:
        """List meetings."""
        response = await self._client.get(f"/users/me/meetings?type={meeting_type}")
        response.raise_for_status()
        return response.json().get("meetings", [])
    
    async def get_meeting_participants(self, meeting_id: str) -> List[Dict[str, Any]]:
        """Get meeting participants."""
        response = await self._client.get(f"/past_meetings/{meeting_id}/participants")
        if response.status_code == 200:
            return response.json().get("participants", [])
        return []

