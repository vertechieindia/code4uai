"""
Agent Manager - Mobile / Web Interface for Managing Agents

Control code4u.ai agents from:
- Mobile app
- Web dashboard
- CLI
- Slack/Teams

Features:
- Start tasks from anywhere
- Monitor progress
- Approve/reject changes
- View history
"""

from .manager import AgentManager
from .session import AgentSession
from .notifications import NotificationService

__all__ = [
    "AgentManager",
    "AgentSession",
    "NotificationService",
]

