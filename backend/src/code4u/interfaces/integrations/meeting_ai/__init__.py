"""
Meeting AI - Intelligent Meeting Assistant

Features:
- Join Zoom, Teams, Webex, Google Meet meetings
- Real-time transcription
- Requirement extraction using LLM
- Meeting minutes generation
- Approval workflow for extracted requirements
- Automatic task creation after approval
"""

from .assistant import MeetingAssistant
from .transcriber import MeetingTranscriber
from .extractor import RequirementExtractor
from .presenter import RequirementPresenter

__all__ = [
    "MeetingAssistant",
    "MeetingTranscriber",
    "RequirementExtractor",
    "RequirementPresenter",
]

