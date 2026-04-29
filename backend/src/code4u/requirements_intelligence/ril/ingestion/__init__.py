"""
Conversation Ingestion Layer

Captures conversations from:
- Slack (Events API)
- Microsoft Teams (Graph API)
- Zoom (Webhooks + Cloud Recording API)
- Google Meet (Calendar + Meet API)

Key principles:
- Opt-in per workspace
- Per-meeting consent
- Audio deletion policy
- PII redaction ready
"""

from .base import ConversationIngestion
from .slack import SlackIngestion
from .teams import TeamsIngestion
from .zoom import ZoomIngestion

__all__ = [
    "ConversationIngestion",
    "SlackIngestion",
    "TeamsIngestion",
    "ZoomIngestion",
]

