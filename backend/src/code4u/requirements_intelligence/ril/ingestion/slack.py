"""Slack conversation ingestion."""

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


class SlackIngestion(ConversationIngestion):
    """
    Slack Conversation Ingestion.
    
    Captures:
    - Channel messages
    - Thread conversations
    - Huddle metadata
    - File attachments
    
    Uses Slack Events API for real-time capture.
    """
    
    platform = ConversationPlatform.SLACK
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize Slack ingestion."""
        super().__init__(tenant_id)
        self.bot_token = os.getenv("SLACK_BOT_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
        self._active_captures: Dict[str, str] = {}  # channel_id -> conversation_id
    
    async def connect(self) -> bool:
        """Connect to Slack."""
        self._client = httpx.AsyncClient(
            base_url="https://slack.com/api",
            headers={"Authorization": f"Bearer {self.bot_token}"},
        )
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from Slack."""
        if self._client:
            await self._client.aclose()
    
    async def start_capture(
        self,
        channel_id: Optional[str] = None,
        meeting_id: Optional[str] = None,
    ) -> str:
        """Start capturing a Slack channel or thread."""
        if not channel_id:
            raise ValueError("channel_id required for Slack")
        
        # Get channel info
        channel_info = await self._get_channel_info(channel_id)
        
        conversation = self._create_conversation(
            platform_id=channel_id,
            type=ConversationType.CHANNEL,
            title=channel_info.get("name", f"Channel {channel_id}"),
        )
        
        self._active_captures[channel_id] = conversation.id
        
        # Optionally fetch recent history
        await self._fetch_recent_messages(conversation, channel_id)
        
        return conversation.id
    
    async def stop_capture(self, conversation_id: str) -> Conversation:
        """Stop capturing a conversation."""
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        conversation.ended_at = datetime.utcnow()
        conversation.processing_status = "captured"
        
        # Remove from active captures
        self._active_captures = {
            k: v for k, v in self._active_captures.items()
            if v != conversation_id
        }
        
        await self._notify_complete(conversation)
        return conversation
    
    async def get_transcript(self, meeting_id: str) -> Optional[str]:
        """Slack doesn't have native transcripts (Huddles have limited API)."""
        return None
    
    async def handle_event(self, event: Dict[str, Any]) -> None:
        """Handle a Slack event.
        
        Args:
            event: Slack event payload
        """
        event_type = event.get("type")
        
        if event_type == "message":
            await self._handle_message(event)
        elif event_type == "reaction_added":
            await self._handle_reaction(event)
    
    async def _handle_message(self, event: Dict[str, Any]) -> None:
        """Handle a message event."""
        channel_id = event.get("channel")
        
        # Check if we're capturing this channel
        conversation_id = self._active_captures.get(channel_id)
        if not conversation_id:
            return
        
        # Get user info
        user_id = event.get("user")
        user_info = await self._get_user_info(user_id)
        
        speaker = Speaker(
            id=user_id,
            name=user_info.get("real_name", user_info.get("name", "Unknown")),
            email=user_info.get("profile", {}).get("email"),
            platform_user_id=user_id,
        )
        
        message = ConversationMessage(
            id=event.get("ts", str(uuid.uuid4())),
            speaker=speaker,
            text=event.get("text", ""),
            timestamp=datetime.fromtimestamp(float(event.get("ts", 0))),
            thread_id=event.get("thread_ts"),
        )
        
        await self.process_message(conversation_id, message)
    
    async def _handle_reaction(self, event: Dict[str, Any]) -> None:
        """Handle a reaction event."""
        # Could track reactions for sentiment/importance analysis
        pass
    
    async def _get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get channel information."""
        response = await self._client.get(
            "/conversations.info",
            params={"channel": channel_id},
        )
        data = response.json()
        return data.get("channel", {})
    
    async def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user information."""
        response = await self._client.get(
            "/users.info",
            params={"user": user_id},
        )
        data = response.json()
        return data.get("user", {})
    
    async def _fetch_recent_messages(
        self,
        conversation: Conversation,
        channel_id: str,
        limit: int = 100,
    ) -> None:
        """Fetch recent messages from a channel."""
        response = await self._client.get(
            "/conversations.history",
            params={"channel": channel_id, "limit": limit},
        )
        data = response.json()
        
        messages = data.get("messages", [])
        for msg in reversed(messages):  # Oldest first
            user_id = msg.get("user")
            if not user_id:
                continue
            
            user_info = await self._get_user_info(user_id)
            
            speaker = Speaker(
                id=user_id,
                name=user_info.get("real_name", user_info.get("name", "Unknown")),
                platform_user_id=user_id,
            )
            
            message = ConversationMessage(
                id=msg.get("ts"),
                speaker=speaker,
                text=msg.get("text", ""),
                timestamp=datetime.fromtimestamp(float(msg.get("ts", 0))),
                thread_id=msg.get("thread_ts"),
            )
            
            conversation.messages.append(message)
            
            # Add speaker if new
            speaker_ids = [s.id for s in conversation.speakers]
            if speaker.id not in speaker_ids:
                conversation.speakers.append(speaker)
    
    async def capture_thread(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> str:
        """Capture a specific thread.
        
        Args:
            channel_id: Channel containing the thread
            thread_ts: Thread timestamp
            
        Returns:
            Conversation ID
        """
        conversation = self._create_conversation(
            platform_id=f"{channel_id}:{thread_ts}",
            type=ConversationType.THREAD,
            title=f"Thread in {channel_id}",
        )
        
        # Fetch thread messages
        response = await self._client.get(
            "/conversations.replies",
            params={"channel": channel_id, "ts": thread_ts},
        )
        data = response.json()
        
        for msg in data.get("messages", []):
            user_id = msg.get("user")
            if not user_id:
                continue
            
            user_info = await self._get_user_info(user_id)
            
            speaker = Speaker(
                id=user_id,
                name=user_info.get("real_name", "Unknown"),
                platform_user_id=user_id,
            )
            
            message = ConversationMessage(
                id=msg.get("ts"),
                speaker=speaker,
                text=msg.get("text", ""),
                timestamp=datetime.fromtimestamp(float(msg.get("ts", 0))),
                thread_id=thread_ts,
            )
            
            conversation.messages.append(message)
        
        conversation.ended_at = datetime.utcnow()
        conversation.processing_status = "captured"
        
        await self._notify_complete(conversation)
        return conversation.id

