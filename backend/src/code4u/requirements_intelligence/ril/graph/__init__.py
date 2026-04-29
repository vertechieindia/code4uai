"""
Requirements → Knowledge Graph Integration

Extends the existing Code Knowledge Graph with:
- Requirement nodes
- Decision nodes
- Stakeholder nodes
- Meeting nodes

Enables:
- Searchable requirements
- Traceable requirements
- Validated requirements
- Agent-triggerable requirements
"""

from .integration import RequirementGraphIntegration
from .nodes import RequirementNode, DecisionNode, StakeholderNode, MeetingNode

__all__ = [
    "RequirementGraphIntegration",
    "RequirementNode",
    "DecisionNode",
    "StakeholderNode",
    "MeetingNode",
]

