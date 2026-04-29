"""Knowledge Graph node types for requirements."""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RequirementNodeType(str, Enum):
    """Requirement node types."""
    REQUIREMENT = "requirement"
    DECISION = "decision"
    STAKEHOLDER = "stakeholder"
    MEETING = "meeting"
    CONSTRAINT = "constraint"


class RequirementRelationType(str, Enum):
    """Relationship types for requirements."""
    AFFECTS = "AFFECTS"              # Requirement -> Service/Module
    OWNED_BY = "OWNED_BY"            # Requirement -> Team/Stakeholder
    DERIVED_FROM = "DERIVED_FROM"    # Requirement -> Meeting
    DEPENDS_ON = "DEPENDS_ON"        # Requirement -> Requirement
    BLOCKED_BY = "BLOCKED_BY"        # Requirement -> Requirement
    IMPLEMENTS = "IMPLEMENTS"        # Code change -> Requirement
    DECIDES = "DECIDES"              # Decision -> Requirement
    PARTICIPATED = "PARTICIPATED"    # Stakeholder -> Meeting
    REQUESTED = "REQUESTED"          # Stakeholder -> Requirement


@dataclass
class RequirementNode:
    """A requirement node in the Knowledge Graph."""
    id: str
    type: str = RequirementNodeType.REQUIREMENT.value
    
    # Core data
    title: str = ""
    description: str = ""
    requirement_type: str = "functional"
    priority: str = "medium"
    status: str = "draft"
    
    # Metadata
    tenant_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    # Source
    source_conversation_id: Optional[str] = None
    source_platform: Optional[str] = None
    source_url: Optional[str] = None
    
    # Systems affected
    systems: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    
    # Constraints
    constraints: List[str] = field(default_factory=list)
    
    # Acceptance criteria
    acceptance_criteria: List[str] = field(default_factory=list)
    
    # Embedding for semantic search
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "requirement_type": self.requirement_type,
            "priority": self.priority,
            "status": self.status,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
            "systems": self.systems,
            "constraints": self.constraints,
        }


@dataclass
class DecisionNode:
    """A decision node in the Knowledge Graph."""
    id: str
    type: str = RequirementNodeType.DECISION.value
    
    # Core data
    title: str = ""
    description: str = ""
    decision_type: str = "technical"  # technical, business, process
    
    # Decision details
    options_considered: List[str] = field(default_factory=list)
    chosen_option: str = ""
    rationale: str = ""
    
    # Participants
    decision_makers: List[str] = field(default_factory=list)
    
    # Source
    source_conversation_id: Optional[str] = None
    source_segment_id: Optional[str] = None
    
    # Timestamps
    decided_at: datetime = field(default_factory=datetime.utcnow)
    
    # Embedding
    embedding: Optional[List[float]] = None


@dataclass
class StakeholderNode:
    """A stakeholder node in the Knowledge Graph."""
    id: str
    type: str = RequirementNodeType.STAKEHOLDER.value
    
    # Identity
    name: str = ""
    email: Optional[str] = None
    role: str = ""  # PM, Engineer, Designer, etc.
    
    # Organization
    team: Optional[str] = None
    department: Optional[str] = None
    
    # Platform identities
    slack_id: Optional[str] = None
    teams_id: Optional[str] = None
    github_username: Optional[str] = None
    
    # Metadata
    tenant_id: str = ""


@dataclass
class MeetingNode:
    """A meeting node in the Knowledge Graph."""
    id: str
    type: str = RequirementNodeType.MEETING.value
    
    # Meeting info
    title: str = ""
    platform: str = ""  # zoom, teams, google_meet
    platform_id: str = ""  # Meeting ID on the platform
    
    # Timing
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: int = 0
    
    # Participants
    participant_count: int = 0
    participant_ids: List[str] = field(default_factory=list)
    
    # Processing
    conversation_id: Optional[str] = None
    has_transcript: bool = False
    
    # Extracted data counts
    requirements_count: int = 0
    decisions_count: int = 0
    action_items_count: int = 0
    
    # Metadata
    tenant_id: str = ""
    
    # Embedding of meeting summary
    embedding: Optional[List[float]] = None

