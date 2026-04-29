"""Microsoft Teams conversation ingestion."""

from __future__ import annotations
import os
import uuid
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


class TeamsIngestion(ConversationIngestion):
    """
    Microsoft Teams Conversation Ingestion.
    
    Captures:
    - Chat messages
    - Meeting transcripts
    - Channel conversations
    
    Uses Microsoft Graph API.
    """
    
    platform = ConversationPlatform.TEAMS
    GRAPH_URL = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize Teams ingestion."""
        super().__init__(tenant_id)
        self.ms_tenant_id = os.getenv("TEAMS_TENANT_ID", "")
        self.client_id = os.getenv("TEAMS_CLIENT_ID", "")
        self.client_secret = os.getenv("TEAMS_CLIENT_SECRET", "")
        self._token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        """Connect to Microsoft Graph."""
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
                f"https://login.microsoftonline.com/{self.ms_tenant_id}/oauth2/v2.0/token",
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
        """Disconnect from Teams."""
        if self._client:
            await self._client.aclose()
    
    async def start_capture(
        self,
        channel_id: Optional[str] = None,
        meeting_id: Optional[str] = None,
    ) -> str:
        """Start capturing a Teams conversation or meeting."""
        if meeting_id:
            return await self._start_meeting_capture(meeting_id)
        elif channel_id:
            return await self._start_channel_capture(channel_id)
        else:
            raise ValueError("channel_id or meeting_id required")
    
    async def _start_meeting_capture(self, meeting_id: str) -> str:
        """Start capturing a meeting."""
        # Get meeting details
        response = await self._client.get(f"/me/onlineMeetings/{meeting_id}")
        meeting = response.json() if response.status_code == 200 else {}
        
        conversation = self._create_conversation(
            platform_id=meeting_id,
            type=ConversationType.MEETING,
            title=meeting.get("subject", f"Meeting {meeting_id}"),
        )
        
        # Get participants
        participants = meeting.get("participants", {}).get("attendees", [])
        for p in participants:
            identity = p.get("identity", {}).get("user", {})
            conversation.speakers.append(Speaker(
                id=identity.get("id", str(uuid.uuid4())),
                name=identity.get("displayName", "Unknown"),
                platform_user_id=identity.get("id"),
            ))
        
        return conversation.id
    
    async def _start_channel_capture(self, channel_id: str) -> str:
        """Start capturing a channel."""
        # Parse team_id:channel_id format
        parts = channel_id.split(":")
        team_id = parts[0] if len(parts) > 1 else None
        ch_id = parts[1] if len(parts) > 1 else channel_id
        
        conversation = self._create_conversation(
            platform_id=channel_id,
            type=ConversationType.CHANNEL,
            title=f"Teams Channel {ch_id}",
        )
        
        # Fetch recent messages
        if team_id:
            await self._fetch_channel_messages(conversation, team_id, ch_id)
        
        return conversation.id
    
    async def stop_capture(self, conversation_id: str) -> Conversation:
        """Stop capturing a conversation."""
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # If it's a meeting, try to get transcript
        if conversation.type == ConversationType.MEETING:
            transcript = await self.get_transcript(conversation.platform_id)
            if transcript:
                conversation.transcript = transcript
        
        conversation.ended_at = datetime.utcnow()
        conversation.processing_status = "captured"
        
        await self._notify_complete(conversation)
        return conversation
    
    async def get_transcript(self, meeting_id: str) -> Optional[str]:
        """Get meeting transcript."""
        # Get transcripts list
        response = await self._client.get(
            f"/me/onlineMeetings/{meeting_id}/transcripts"
        )
        
        if response.status_code != 200:
            return None
        
        transcripts = response.json().get("value", [])
        if not transcripts:
            return None
        
        # Get first transcript content
        transcript_id = transcripts[0].get("id")
        content_response = await self._client.get(
            f"/me/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content",
            headers={"Accept": "text/vtt"},
        )
        
        if content_response.status_code == 200:
            return self._parse_vtt(content_response.text)
        
        return None
    
    def _parse_vtt(self, vtt_content: str) -> str:
        """Parse VTT transcript to plain text with speakers."""
        lines = []
        current_speaker = None
        
        for line in vtt_content.split('\n'):
            line = line.strip()
            
            # Skip VTT headers and timestamps
            if not line or line.startswith('WEBVTT') or '-->' in line:
                continue
            
            # Check for speaker tags
            if '<v ' in line:
                # Extract speaker and text
                import re
                match = re.match(r'<v\s+([^>]+)>(.+)', line)
                if match:
                    speaker = match.group(1)
                    text = match.group(2).replace('</v>', '')
                    
                    if speaker != current_speaker:
                        current_speaker = speaker
                        lines.append(f"\n[{speaker}]: {text}")
                    else:
                        lines.append(text)
            else:
                lines.append(line)
        
        return ' '.join(lines)
    
    async def _fetch_channel_messages(
        self,
        conversation: Conversation,
        team_id: str,
        channel_id: str,
    ) -> None:
        """Fetch messages from a channel."""
        response = await self._client.get(
            f"/teams/{team_id}/channels/{channel_id}/messages"
        )
        
        if response.status_code != 200:
            return
        
        messages = response.json().get("value", [])
        for msg in messages:
            sender = msg.get("from", {}).get("user", {})
            
            speaker = Speaker(
                id=sender.get("id", str(uuid.uuid4())),
                name=sender.get("displayName", "Unknown"),
                platform_user_id=sender.get("id"),
            )
            
            # Parse body
            body = msg.get("body", {})
            text = body.get("content", "")
            
            # Remove HTML tags for plaintext
            import re
            text = re.sub(r'<[^>]+>', '', text)
            
            message = ConversationMessage(
                id=msg.get("id"),
                speaker=speaker,
                text=text,
                timestamp=datetime.fromisoformat(msg.get("createdDateTime", "").replace("Z", "+00:00")),
            )
            
            conversation.messages.append(message)
            
            # Add speaker
            speaker_ids = [s.id for s in conversation.speakers]
            if speaker.id not in speaker_ids:
                conversation.speakers.append(speaker)

