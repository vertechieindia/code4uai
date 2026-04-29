"""
Requirement Structuring Engine

The killer differentiator.

Converts human language → engineering-grade requirements.

Example Input:
  "We need SSO with Okta before Q4 and it has to be SOC2 compliant."

Structured Output:
{
  "requirement_id": "REQ-401",
  "title": "Implement Okta SSO",
  "type": "functional",
  "priority": "high",
  "deadline": "2025-10-01",
  "systems": ["Auth", "Frontend", "Backend"],
  "constraints": ["SOC2"],
  "source": {
    "platform": "Zoom",
    "meeting_id": "abc-123"
  }
}

This is not a summary.
This is a machine-usable contract.
"""

from .engine import RequirementStructurer
from .templates import RequirementTemplate

__all__ = [
    "RequirementStructurer",
    "RequirementTemplate",
]

