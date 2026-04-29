"""
code4u.ai Integrations Package

Comprehensive integrations with enterprise tools:

Communication & Collaboration:
- Microsoft Teams
- Discord
- Google Workspace (Chat, Meet, Docs)

Project & Task Management:
- Jira (via Atlassian)
- Asana
- Trello
- Monday.com
- ClickUp
- Wrike
- Basecamp
- Notion

ITSM & Customer Service:
- ServiceNow
- Zendesk
- Freshservice

Meeting AI:
- Zoom
- Microsoft Teams
- Google Meet
- Webex

Visual Collaboration:
- Miro
- Figma

Storage:
- Google Drive
- Dropbox
"""

from .base import (
    IntegrationType,
    EventType,
    IntegrationConfig,
    IntegrationEvent,
    Requirement,
    MeetingMinutes,
    BaseIntegration,
    TaskIntegration,
    MeetingIntegration,
    CommunicationIntegration,
)

from .registry import (
    IntegrationRegistry,
    registry,
    register_integration,
)

from .approval_workflow import (
    ApprovalStatus,
    TaskExecutionStatus,
    ApprovalRequest,
    ExecutionResult,
    ApprovalWorkflow,
)

# Import all integrations to register them
from . import jira
from . import servicenow
from . import asana
from . import trello
from . import monday
from . import clickup
from . import wrike
from . import basecamp
from . import zendesk
from . import freshservice
from . import slack
from . import teams
from . import discord
from . import google
from . import zoom
from . import webex
from . import notion
from . import miro
from . import figma
from . import dropbox
from . import meeting_ai


__all__ = [
    # Base
    "IntegrationType",
    "EventType",
    "IntegrationConfig",
    "IntegrationEvent",
    "Requirement",
    "MeetingMinutes",
    "BaseIntegration",
    "TaskIntegration",
    "MeetingIntegration",
    "CommunicationIntegration",
    
    # Registry
    "IntegrationRegistry",
    "registry",
    "register_integration",
    
    # Approval Workflow
    "ApprovalStatus",
    "TaskExecutionStatus",
    "ApprovalRequest",
    "ExecutionResult",
    "ApprovalWorkflow",
]
