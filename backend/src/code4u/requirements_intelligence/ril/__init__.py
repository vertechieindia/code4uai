"""
Requirements Intelligence Layer (RIL)

Converts human conversations → structured engineering intent → executable plans.

Otter stops at transcription + summary.
code4u.ai goes all the way to engineering execution.

Pipeline:
1. Conversation Ingestion (Slack / Teams / Zoom)
2. Speech-to-Text + Message Capture
3. Conversation Intelligence Engine
4. Requirement Structuring Engine
5. Knowledge Graph Integration
6. Agent Planner (Optional Execution)

Each layer is replaceable, auditable, and deterministic.
"""

from .ingestion import ConversationIngestion
from .intelligence import ConversationIntelligence
from .structuring import RequirementStructurer
from .models import (
    Conversation,
    ConversationSegment,
    StructuredRequirement,
    RequirementType,
    SegmentType,
)

__all__ = [
    "ConversationIngestion",
    "ConversationIntelligence",
    "RequirementStructurer",
    "Conversation",
    "ConversationSegment",
    "StructuredRequirement",
    "RequirementType",
    "SegmentType",
]

