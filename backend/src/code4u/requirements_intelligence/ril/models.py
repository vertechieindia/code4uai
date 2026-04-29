"""Data models for Requirements Intelligence Layer."""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ConversationPlatform(str, Enum):
    """Source platforms."""
    SLACK = "slack"
    TEAMS = "teams"
    ZOOM = "zoom"
    GOOGLE_MEET = "google_meet"
    DISCORD = "discord"


class ConversationType(str, Enum):
    """Types of conversations."""
    MEETING = "meeting"
    THREAD = "thread"
    CHANNEL = "channel"
    HUDDLE = "huddle"
    CALL = "call"


class SegmentType(str, Enum):
    """Types of conversation segments."""
    REQUIREMENT = "requirement"
    CONSTRAINT = "constraint"
    DECISION = "decision"
    OPEN_QUESTION = "open_question"
    RISK = "risk"
    ACTION_ITEM = "action_item"
    CONTEXT = "context"
    NON_TECHNICAL = "non_technical"


class RequirementType(str, Enum):
    """Types of requirements."""
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    TECHNICAL = "technical"
    BUSINESS = "business"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    INTEGRATION = "integration"


class RequirementPriority(str, Enum):
    """Priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementStatus(str, Enum):
    """Requirement lifecycle status."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"


@dataclass
class Speaker:
    """A speaker in a conversation."""
    id: str
    name: str
    email: Optional[str] = None
    role: Optional[str] = None  # PM, Engineer, Designer, etc.
    platform_user_id: Optional[str] = None


@dataclass
class ConversationMessage:
    """A single message in a conversation."""
    id: str
    speaker: Speaker
    text: str
    timestamp: datetime
    
    # Threading
    thread_id: Optional[str] = None
    reply_to: Optional[str] = None
    
    # Reactions/context
    reactions: List[str] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Processing
    processed: bool = False
    segments: List[str] = field(default_factory=list)  # Segment IDs


@dataclass
class Conversation:
    """A complete conversation (meeting, thread, etc.)."""
    id: str
    tenant_id: str
    
    # Source
    platform: ConversationPlatform
    platform_id: str  # Meeting ID, Channel ID, etc.
    type: ConversationType
    
    # Content
    title: Optional[str] = None
    messages: List[ConversationMessage] = field(default_factory=list)
    
    # Participants
    speakers: List[Speaker] = field(default_factory=list)
    
    # Transcript (for meetings)
    transcript: Optional[str] = None
    transcript_segments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Processing status
    processed: bool = False
    processing_status: str = "pending"
    
    # Timestamps
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    captured_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    # Consent
    consent_given: bool = False
    consent_by: List[str] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationSegment:
    """A classified segment of conversation."""
    id: str
    conversation_id: str
    
    # Content
    speaker: str
    text: str
    timestamp: str
    
    # Classification
    type: SegmentType
    confidence: float = 0.0
    
    # Extracted entities
    entities: Dict[str, Any] = field(default_factory=dict)
    
    # Relationships
    related_segments: List[str] = field(default_factory=list)
    
    # Processing
    structured_requirement_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StructuredRequirement:
    """An engineering-grade structured requirement."""
    id: str
    tenant_id: str
    
    # Core
    title: str
    description: str
    type: RequirementType
    priority: RequirementPriority = RequirementPriority.MEDIUM
    status: RequirementStatus = RequirementStatus.DRAFT
    
    # Deadline
    deadline: Optional[datetime] = None
    
    # Systems/Components
    systems: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    
    # Constraints
    constraints: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    # Acceptance criteria
    acceptance_criteria: List[str] = field(default_factory=list)
    
    # Source traceability
    source_platform: Optional[ConversationPlatform] = None
    source_conversation_id: Optional[str] = None
    source_segment_ids: List[str] = field(default_factory=list)
    source_url: Optional[str] = None
    
    # Stakeholders
    requested_by: Optional[str] = None
    owned_by: Optional[str] = None
    stakeholders: List[str] = field(default_factory=list)
    
    # Knowledge Graph
    graph_node_id: Optional[str] = None
    affected_nodes: List[str] = field(default_factory=list)
    
    # Execution
    execution_plan_id: Optional[str] = None
    implementation_pr: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    implemented_at: Optional[datetime] = None
    
    # Original text for reference
    original_text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "type": self.type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "systems": self.systems,
            "constraints": self.constraints,
            "acceptance_criteria": self.acceptance_criteria,
            "source": {
                "platform": self.source_platform.value if self.source_platform else None,
                "conversation_id": self.source_conversation_id,
                "url": self.source_url,
            },
            "stakeholders": self.stakeholders,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RequirementBatch:
    """A batch of requirements from a conversation."""
    id: str
    conversation_id: str
    
    # Requirements
    requirements: List[StructuredRequirement] = field(default_factory=list)
    
    # Summary
    total_segments: int = 0
    requirements_count: int = 0
    decisions_count: int = 0
    open_questions_count: int = 0
    risks_count: int = 0
    
    # Status
    status: str = "pending_review"
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    
    # Reviewer
    reviewed_by: Optional[str] = None

