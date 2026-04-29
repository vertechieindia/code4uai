"""Base class for conversation ingestion."""

from __future__ import annotations
import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Callable, Awaitable
from datetime import datetime

from ..models import (
    Conversation,
    ConversationMessage,
    ConversationPlatform,
    ConversationType,
    Speaker,
)


class ConversationIngestion(ABC):
    """
    Base class for conversation ingestion.
    
    Captures conversations from various platforms and
    normalizes them into a common format.
    """
    
    platform: ConversationPlatform
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize ingestion.
        
        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id
        self._conversations: Dict[str, Conversation] = {}
        self._callbacks: List[Callable[[Conversation], Awaitable[None]]] = []
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the platform.
        
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the platform."""
        pass
    
    @abstractmethod
    async def start_capture(
        self,
        channel_id: Optional[str] = None,
        meeting_id: Optional[str] = None,
    ) -> str:
        """Start capturing a conversation.
        
        Args:
            channel_id: Channel to capture (for Slack/Teams)
            meeting_id: Meeting to capture (for Zoom/Teams)
            
        Returns:
            Conversation ID
        """
        pass
    
    @abstractmethod
    async def stop_capture(self, conversation_id: str) -> Conversation:
        """Stop capturing and return the conversation.
        
        Args:
            conversation_id: Conversation to stop
            
        Returns:
            Complete conversation
        """
        pass
    
    @abstractmethod
    async def get_transcript(
        self,
        meeting_id: str,
    ) -> Optional[str]:
        """Get transcript for a meeting (if available).
        
        Args:
            meeting_id: Meeting identifier
            
        Returns:
            Transcript text or None
        """
        pass
    
    async def process_message(
        self,
        conversation_id: str,
        message: ConversationMessage,
    ) -> None:
        """Process an incoming message.
        
        Args:
            conversation_id: Conversation to add to
            message: Message to add
        """
        conversation = self._conversations.get(conversation_id)
        if conversation:
            conversation.messages.append(message)
            
            # Add speaker if new
            speaker_ids = [s.id for s in conversation.speakers]
            if message.speaker.id not in speaker_ids:
                conversation.speakers.append(message.speaker)
    
    async def process_transcript_segment(
        self,
        conversation_id: str,
        speaker: str,
        text: str,
        timestamp: str,
    ) -> None:
        """Process a transcript segment.
        
        Args:
            conversation_id: Conversation to add to
            speaker: Speaker name
            text: Spoken text
            timestamp: Timestamp
        """
        conversation = self._conversations.get(conversation_id)
        if conversation:
            conversation.transcript_segments.append({
                "speaker": speaker,
                "text": text,
                "timestamp": timestamp,
            })
    
    def on_conversation_complete(
        self,
        callback: Callable[[Conversation], Awaitable[None]],
    ) -> None:
        """Register callback for completed conversations.
        
        Args:
            callback: Async callback
        """
        self._callbacks.append(callback)
    
    async def _notify_complete(self, conversation: Conversation) -> None:
        """Notify callbacks of completed conversation."""
        for callback in self._callbacks:
            try:
                await callback(conversation)
            except:
                pass
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self._conversations.get(conversation_id)
    
    def list_conversations(self) -> List[Conversation]:
        """List all conversations."""
        return list(self._conversations.values())
    
    def _create_conversation(
        self,
        platform_id: str,
        type: ConversationType,
        title: Optional[str] = None,
    ) -> Conversation:
        """Create a new conversation.
        
        Args:
            platform_id: Platform-specific ID
            type: Conversation type
            title: Optional title
            
        Returns:
            Created conversation
        """
        conversation = Conversation(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            platform=self.platform,
            platform_id=platform_id,
            type=type,
            title=title,
            started_at=datetime.utcnow(),
        )
        
        self._conversations[conversation.id] = conversation
        return conversation

