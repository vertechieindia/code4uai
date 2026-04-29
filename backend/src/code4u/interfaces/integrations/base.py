"""Base classes for all integrations."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Awaitable
from enum import Enum
from datetime import datetime
import asyncio


class IntegrationType(str, Enum):
    """Types of integrations."""
    COMMUNICATION = "communication"
    PROJECT_MANAGEMENT = "project_management"
    ITSM = "itsm"
    MEETING = "meeting"
    STORAGE = "storage"
    DESIGN = "design"


class EventType(str, Enum):
    """Types of events from integrations."""
    # Task/Issue events
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    
    # Message events
    MESSAGE_RECEIVED = "message_received"
    MENTION = "mention"
    COMMAND = "command"
    
    # Meeting events
    MEETING_STARTED = "meeting_started"
    MEETING_ENDED = "meeting_ended"
    TRANSCRIPT_READY = "transcript_ready"
    
    # Approval events
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    
    # Document events
    DOCUMENT_CREATED = "document_created"
    DOCUMENT_UPDATED = "document_updated"


@dataclass
class IntegrationConfig:
    """Base configuration for integrations."""
    enabled: bool = True
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    tenant_id: str = "default"
    
    # Rate limiting
    rate_limit_rpm: int = 100
    
    # Custom settings
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegrationEvent:
    """An event from an integration."""
    id: str
    type: EventType
    source: str  # Integration name
    
    # Event data
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Context
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    channel_id: Optional[str] = None
    project_id: Optional[str] = None
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Raw payload
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Requirement:
    """A requirement extracted from any source."""
    id: str
    title: str
    description: str
    
    # Source
    source_type: str  # meeting, ticket, message, etc.
    source_id: str
    source_url: Optional[str] = None
    
    # Classification
    type: str = "feature"  # feature, bug, enhancement, task
    priority: str = "medium"  # low, medium, high, critical
    
    # Assignment
    assignee: Optional[str] = None
    team: Optional[str] = None
    
    # Status
    status: str = "draft"  # draft, pending_approval, approved, rejected, in_progress, done
    
    # Approval
    approvers: List[str] = field(default_factory=list)
    approved_by: List[str] = field(default_factory=list)
    rejected_by: List[str] = field(default_factory=list)
    approval_comments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Technical
    estimated_effort: Optional[str] = None
    affected_files: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None


@dataclass  
class MeetingMinutes:
    """Minutes from a meeting."""
    id: str
    meeting_id: str
    meeting_title: str
    
    # Participants
    participants: List[str] = field(default_factory=list)
    
    # Content
    summary: str = ""
    key_points: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    
    # Requirements extracted
    requirements: List[Requirement] = field(default_factory=list)
    
    # Timestamps
    meeting_start: Optional[datetime] = None
    meeting_end: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Approval
    status: str = "draft"  # draft, pending_approval, approved
    
    # Raw transcript
    transcript: Optional[str] = None


class BaseIntegration(ABC):
    """Base class for all integrations."""
    
    name: str = "base"
    type: IntegrationType = IntegrationType.COMMUNICATION
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        """Initialize integration.
        
        Args:
            config: Integration configuration
        """
        self.config = config or IntegrationConfig()
        self._event_handlers: Dict[EventType, List[Callable]] = {}
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the service.
        
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the service."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check integration health.
        
        Returns:
            Health status
        """
        pass
    
    def on_event(self, event_type: EventType) -> Callable:
        """Decorator to register event handler.
        
        Args:
            event_type: Event type to handle
        """
        def decorator(func: Callable):
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(func)
            return func
        return decorator
    
    async def emit_event(self, event: IntegrationEvent) -> None:
        """Emit an event to handlers.
        
        Args:
            event: Event to emit
        """
        handlers = self._event_handlers.get(event.type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                # Log error but continue
                pass


class TaskIntegration(BaseIntegration):
    """Base class for task/project management integrations."""
    
    type = IntegrationType.PROJECT_MANAGEMENT
    
    @abstractmethod
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get a task by ID."""
        pass
    
    @abstractmethod
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a new task."""
        pass
    
    @abstractmethod
    async def update_task(
        self,
        task_id: str,
        **updates,
    ) -> Dict[str, Any]:
        """Update a task."""
        pass
    
    @abstractmethod
    async def add_comment(
        self,
        task_id: str,
        comment: str,
    ) -> Dict[str, Any]:
        """Add comment to a task."""
        pass
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        """Convert a task to a Requirement.
        
        Args:
            task: Task data from the platform
            
        Returns:
            Requirement object
        """
        # Default implementation - subclasses should override
        import uuid
        return Requirement(
            id=str(uuid.uuid4()),
            title=task.get("title", task.get("name", "")),
            description=task.get("description", task.get("body", "")),
            source_type=self.name,
            source_id=str(task.get("id", "")),
        )


class MeetingIntegration(BaseIntegration):
    """Base class for meeting integrations."""
    
    type = IntegrationType.MEETING
    
    @abstractmethod
    async def join_meeting(self, meeting_url: str) -> Dict[str, Any]:
        """Join a meeting.
        
        Args:
            meeting_url: URL of the meeting
            
        Returns:
            Meeting session info
        """
        pass
    
    @abstractmethod
    async def leave_meeting(self, session_id: str) -> None:
        """Leave a meeting."""
        pass
    
    @abstractmethod
    async def get_transcript(self, meeting_id: str) -> str:
        """Get meeting transcript.
        
        Args:
            meeting_id: Meeting identifier
            
        Returns:
            Transcript text
        """
        pass
    
    @abstractmethod
    async def get_recording(self, meeting_id: str) -> Optional[str]:
        """Get meeting recording URL.
        
        Args:
            meeting_id: Meeting identifier
            
        Returns:
            Recording URL or None
        """
        pass


class CommunicationIntegration(BaseIntegration):
    """Base class for communication integrations."""
    
    type = IntegrationType.COMMUNICATION
    
    @abstractmethod
    async def send_message(
        self,
        channel_id: str,
        message: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a message.
        
        Args:
            channel_id: Channel/conversation ID
            message: Message content
            
        Returns:
            Message info
        """
        pass
    
    @abstractmethod
    async def send_rich_message(
        self,
        channel_id: str,
        blocks: List[Dict[str, Any]],
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a rich/formatted message.
        
        Args:
            channel_id: Channel/conversation ID
            blocks: Rich content blocks
            
        Returns:
            Message info
        """
        pass

