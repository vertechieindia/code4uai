"""Main Meeting Assistant that orchestrates all meeting AI features."""

from __future__ import annotations
import asyncio
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..base import MeetingMinutes, Requirement, IntegrationEvent, EventType


class MeetingPlatform(str, Enum):
    """Supported meeting platforms."""
    ZOOM = "zoom"
    TEAMS = "teams"
    WEBEX = "webex"
    GOOGLE_MEET = "google_meet"
    DISCORD = "discord"


class MeetingStatus(str, Enum):
    """Meeting session status."""
    JOINING = "joining"
    CONNECTED = "connected"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class MeetingSession:
    """Active meeting session."""
    id: str
    platform: MeetingPlatform
    meeting_url: str
    meeting_id: Optional[str] = None
    
    # Status
    status: MeetingStatus = MeetingStatus.JOINING
    
    # Participants
    participants: List[str] = field(default_factory=list)
    
    # Content
    transcript_buffer: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timestamps
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    # Output
    minutes: Optional[MeetingMinutes] = None
    requirements: List[Requirement] = field(default_factory=list)


class MeetingAssistant:
    """
    Intelligent Meeting Assistant for code4u.ai
    
    Capabilities:
    1. Join meetings across platforms (Zoom, Teams, Webex, Meet)
    2. Record and transcribe in real-time
    3. Extract requirements from discussions
    4. Generate meeting minutes
    5. Present requirements for approval
    6. Create tasks after approval
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize meeting assistant.
        
        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id
        self._sessions: Dict[str, MeetingSession] = {}
        self._transcriber = None
        self._extractor = None
    
    async def join_meeting(
        self,
        meeting_url: str,
        bot_name: str = "code4u.ai Assistant",
    ) -> MeetingSession:
        """Join a meeting.
        
        Args:
            meeting_url: URL of the meeting to join
            bot_name: Name to display for the bot
            
        Returns:
            MeetingSession object
        """
        # Detect platform from URL
        platform = self._detect_platform(meeting_url)
        
        # Create session
        session = MeetingSession(
            id=str(uuid.uuid4()),
            platform=platform,
            meeting_url=meeting_url,
            started_at=datetime.utcnow(),
        )
        
        self._sessions[session.id] = session
        
        # Platform-specific join logic
        try:
            if platform == MeetingPlatform.ZOOM:
                await self._join_zoom(session, bot_name)
            elif platform == MeetingPlatform.TEAMS:
                await self._join_teams(session, bot_name)
            elif platform == MeetingPlatform.WEBEX:
                await self._join_webex(session, bot_name)
            elif platform == MeetingPlatform.GOOGLE_MEET:
                await self._join_google_meet(session, bot_name)
            
            session.status = MeetingStatus.CONNECTED
            
        except Exception as e:
            session.status = MeetingStatus.ERROR
            raise
        
        return session
    
    def _detect_platform(self, url: str) -> MeetingPlatform:
        """Detect meeting platform from URL."""
        url_lower = url.lower()
        
        if "zoom.us" in url_lower or "zoom.com" in url_lower:
            return MeetingPlatform.ZOOM
        elif "teams.microsoft.com" in url_lower or "teams.live.com" in url_lower:
            return MeetingPlatform.TEAMS
        elif "webex.com" in url_lower:
            return MeetingPlatform.WEBEX
        elif "meet.google.com" in url_lower:
            return MeetingPlatform.GOOGLE_MEET
        elif "discord.com" in url_lower or "discord.gg" in url_lower:
            return MeetingPlatform.DISCORD
        else:
            raise ValueError(f"Unknown meeting platform: {url}")
    
    async def _join_zoom(self, session: MeetingSession, bot_name: str) -> None:
        """Join a Zoom meeting using Zoom SDK/API."""
        # In production, this would use:
        # 1. Zoom Meeting SDK for joining
        # 2. Zoom Recording API for audio
        # 3. Real-time transcription service
        
        # Simulated join
        session.meeting_id = session.meeting_url.split("/")[-1].split("?")[0]
    
    async def _join_teams(self, session: MeetingSession, bot_name: str) -> None:
        """Join a Microsoft Teams meeting."""
        # In production, this would use:
        # 1. Microsoft Graph API
        # 2. Teams Bot Framework
        # 3. Azure Communication Services
        pass
    
    async def _join_webex(self, session: MeetingSession, bot_name: str) -> None:
        """Join a Webex meeting."""
        # In production, this would use:
        # 1. Webex Meetings API
        # 2. Webex Bot SDK
        pass
    
    async def _join_google_meet(self, session: MeetingSession, bot_name: str) -> None:
        """Join a Google Meet meeting."""
        # In production, this would use:
        # 1. Google Calendar API
        # 2. Google Meet API
        # 3. Chrome automation for joining
        pass
    
    async def start_transcription(self, session_id: str) -> None:
        """Start transcribing a meeting.
        
        Args:
            session_id: Session identifier
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.status = MeetingStatus.TRANSCRIBING
        
        # In production, this would use:
        # 1. Whisper API or similar for transcription
        # 2. Speaker diarization
        # 3. Real-time streaming
    
    async def stop_transcription(self, session_id: str) -> str:
        """Stop transcription and return transcript.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Full transcript text
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Compile transcript
        transcript = "\n".join([
            f"{entry.get('speaker', 'Unknown')}: {entry.get('text', '')}"
            for entry in session.transcript_buffer
        ])
        
        session.status = MeetingStatus.PROCESSING
        return transcript
    
    async def leave_meeting(self, session_id: str) -> None:
        """Leave a meeting.
        
        Args:
            session_id: Session identifier
        """
        session = self._sessions.get(session_id)
        if not session:
            return
        
        session.ended_at = datetime.utcnow()
        
        # Platform-specific leave logic would go here
    
    async def process_meeting(self, session_id: str) -> MeetingMinutes:
        """Process a completed meeting to extract requirements.
        
        Args:
            session_id: Session identifier
            
        Returns:
            MeetingMinutes with extracted requirements
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Get transcript
        transcript = await self.stop_transcription(session_id)
        
        # Use LLM to extract requirements
        from .extractor import RequirementExtractor
        extractor = RequirementExtractor()
        
        # Generate minutes
        minutes = await extractor.generate_minutes(
            transcript=transcript,
            meeting_id=session.id,
            participants=session.participants,
        )
        
        # Extract requirements
        requirements = await extractor.extract_requirements(
            transcript=transcript,
            context={
                "meeting_id": session.id,
                "participants": session.participants,
            },
        )
        
        minutes.requirements = requirements
        minutes.transcript = transcript
        
        session.minutes = minutes
        session.requirements = requirements
        session.status = MeetingStatus.COMPLETED
        
        return minutes
    
    async def present_for_approval(
        self,
        session_id: str,
        channel: str,
        approvers: List[str],
    ) -> Dict[str, Any]:
        """Present extracted requirements for team approval.
        
        Args:
            session_id: Session identifier
            channel: Channel to present in (Slack, Teams, etc.)
            approvers: List of approver user IDs
            
        Returns:
            Presentation status
        """
        session = self._sessions.get(session_id)
        if not session or not session.minutes:
            raise ValueError("No meeting minutes available")
        
        from .presenter import RequirementPresenter
        presenter = RequirementPresenter()
        
        # Mark requirements as pending approval
        for req in session.requirements:
            req.status = "pending_approval"
            req.approvers = approvers
        
        # Present to channel
        result = await presenter.present(
            minutes=session.minutes,
            channel=channel,
            approvers=approvers,
        )
        
        return result
    
    def get_session(self, session_id: str) -> Optional[MeetingSession]:
        """Get a meeting session."""
        return self._sessions.get(session_id)
    
    def list_sessions(self) -> List[MeetingSession]:
        """List all sessions."""
        return list(self._sessions.values())
    
    async def add_transcript_entry(
        self,
        session_id: str,
        speaker: str,
        text: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a transcript entry (for real-time transcription).
        
        Args:
            session_id: Session identifier
            speaker: Speaker name
            text: Spoken text
            timestamp: When it was spoken
        """
        session = self._sessions.get(session_id)
        if not session:
            return
        
        session.transcript_buffer.append({
            "speaker": speaker,
            "text": text,
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
        })
    
    async def update_participants(
        self,
        session_id: str,
        participants: List[str],
    ) -> None:
        """Update participant list.
        
        Args:
            session_id: Session identifier
            participants: Current participants
        """
        session = self._sessions.get(session_id)
        if session:
            session.participants = participants

