"""Zoom meeting ingestion."""

from __future__ import annotations
import os
import uuid
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx

from ..models import (
    Conversation,
    ConversationMessage,
    ConversationPlatform,
    ConversationType,
    Speaker,
)
from .base import ConversationIngestion


class ZoomIngestion(ConversationIngestion):
    """
    Zoom Meeting Ingestion.
    
    Captures:
    - Meeting metadata
    - Participant information
    - Cloud recordings (audio/video)
    - Native transcripts
    
    Uses Zoom Webhooks + Cloud Recording API.
    """
    
    platform = ConversationPlatform.ZOOM
    BASE_URL = "https://api.zoom.us/v2"
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize Zoom ingestion."""
        super().__init__(tenant_id)
        self.account_id = os.getenv("ZOOM_ACCOUNT_ID", "")
        self.client_id = os.getenv("ZOOM_CLIENT_ID", "")
        self.client_secret = os.getenv("ZOOM_CLIENT_SECRET", "")
        self._token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        """Connect to Zoom API."""
        await self._get_token()
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        return True
    
    async def _get_token(self) -> None:
        """Get OAuth2 access token."""
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={self.account_id}",
                headers={"Authorization": f"Basic {auth}"},
            )
            response.raise_for_status()
            self._token = response.json().get("access_token")
    
    async def disconnect(self) -> None:
        """Disconnect from Zoom."""
        if self._client:
            await self._client.aclose()
    
    async def start_capture(
        self,
        channel_id: Optional[str] = None,
        meeting_id: Optional[str] = None,
    ) -> str:
        """Start capturing a Zoom meeting."""
        if not meeting_id:
            raise ValueError("meeting_id required for Zoom")
        
        # Get meeting details
        response = await self._client.get(f"/meetings/{meeting_id}")
        meeting = response.json() if response.status_code == 200 else {}
        
        conversation = self._create_conversation(
            platform_id=meeting_id,
            type=ConversationType.MEETING,
            title=meeting.get("topic", f"Zoom Meeting {meeting_id}"),
        )
        
        conversation.metadata["zoom_meeting"] = {
            "uuid": meeting.get("uuid"),
            "host_id": meeting.get("host_id"),
            "type": meeting.get("type"),
            "start_time": meeting.get("start_time"),
            "duration": meeting.get("duration"),
        }
        
        return conversation.id
    
    async def stop_capture(self, conversation_id: str) -> Conversation:
        """Stop capturing and process recordings."""
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        conversation.ended_at = datetime.utcnow()
        
        # Get transcript
        transcript = await self.get_transcript(conversation.platform_id)
        if transcript:
            conversation.transcript = transcript
        
        # Get participants
        participants = await self._get_participants(conversation.platform_id)
        for p in participants:
            conversation.speakers.append(Speaker(
                id=p.get("id", str(uuid.uuid4())),
                name=p.get("name", "Unknown"),
                email=p.get("user_email"),
            ))
        
        conversation.processing_status = "captured"
        
        await self._notify_complete(conversation)
        return conversation
    
    async def get_transcript(self, meeting_id: str) -> Optional[str]:
        """Get meeting transcript from cloud recordings."""
        # Get recordings
        response = await self._client.get(f"/meetings/{meeting_id}/recordings")
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        recording_files = data.get("recording_files", [])
        
        # Find transcript file
        for rec in recording_files:
            if rec.get("file_type") == "TRANSCRIPT":
                # Download transcript
                download_url = rec.get("download_url")
                if download_url:
                    transcript_response = await self._client.get(
                        download_url,
                        headers={"Authorization": f"Bearer {self._token}"},
                    )
                    if transcript_response.status_code == 200:
                        return self._parse_vtt(transcript_response.text)
        
        return None
    
    def _parse_vtt(self, vtt_content: str) -> str:
        """Parse VTT transcript to structured format."""
        segments = []
        current_speaker = None
        current_text = []
        
        lines = vtt_content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip VTT header and empty lines
            if not line or line.startswith('WEBVTT') or line.startswith('NOTE'):
                i += 1
                continue
            
            # Skip cue identifiers (just numbers)
            if line.isdigit():
                i += 1
                continue
            
            # Skip timestamp lines
            if '-->' in line:
                i += 1
                continue
            
            # Check for speaker
            if ': ' in line:
                # New speaker
                parts = line.split(': ', 1)
                speaker = parts[0]
                text = parts[1] if len(parts) > 1 else ""
                
                if speaker != current_speaker:
                    if current_speaker and current_text:
                        segments.append(f"[{current_speaker}]: {' '.join(current_text)}")
                    current_speaker = speaker
                    current_text = [text] if text else []
                else:
                    current_text.append(text)
            else:
                # Continue current speaker
                current_text.append(line)
            
            i += 1
        
        # Add last segment
        if current_speaker and current_text:
            segments.append(f"[{current_speaker}]: {' '.join(current_text)}")
        
        return '\n'.join(segments)
    
    async def _get_participants(self, meeting_id: str) -> List[Dict[str, Any]]:
        """Get meeting participants."""
        response = await self._client.get(f"/past_meetings/{meeting_id}/participants")
        
        if response.status_code != 200:
            return []
        
        return response.json().get("participants", [])
    
    async def handle_webhook(self, event: Dict[str, Any]) -> None:
        """Handle a Zoom webhook event.
        
        Args:
            event: Webhook payload
        """
        event_type = event.get("event")
        payload = event.get("payload", {}).get("object", {})
        
        if event_type == "meeting.started":
            meeting_id = payload.get("id")
            await self.start_capture(meeting_id=meeting_id)
        
        elif event_type == "meeting.ended":
            meeting_id = payload.get("id")
            # Find conversation by meeting_id
            for conv in self._conversations.values():
                if conv.platform_id == str(meeting_id):
                    await self.stop_capture(conv.id)
                    break
        
        elif event_type == "recording.completed":
            meeting_id = payload.get("id")
            # Trigger transcript processing
            for conv in self._conversations.values():
                if conv.platform_id == str(meeting_id):
                    transcript = await self.get_transcript(meeting_id)
                    if transcript:
                        conv.transcript = transcript
                    break
    
    async def get_past_meeting_transcript(
        self,
        meeting_uuid: str,
    ) -> Optional[str]:
        """Get transcript for a past meeting.
        
        Args:
            meeting_uuid: Meeting UUID (must be double-encoded if starts with /)
            
        Returns:
            Transcript text
        """
        import urllib.parse
        
        # Double-encode if needed
        if meeting_uuid.startswith('/'):
            meeting_uuid = urllib.parse.quote(urllib.parse.quote(meeting_uuid, safe=''), safe='')
        
        return await self.get_transcript(meeting_uuid)

