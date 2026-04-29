"""Agent Session - Track user sessions across devices."""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DeviceType(str, Enum):
    """Type of device."""
    WEB = "web"
    MOBILE_IOS = "mobile_ios"
    MOBILE_ANDROID = "mobile_android"
    DESKTOP = "desktop"
    IDE_VSCODE = "ide_vscode"
    IDE_JETBRAINS = "ide_jetbrains"
    CLI = "cli"


class SessionStatus(str, Enum):
    """Session status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


@dataclass
class AgentSession:
    """A user session for managing agents."""
    id: str
    user_id: str
    tenant_id: str
    
    # Device
    device_type: DeviceType = DeviceType.WEB
    device_name: Optional[str] = None
    device_id: Optional[str] = None
    
    # Status
    status: SessionStatus = SessionStatus.ACTIVE
    
    # Connection
    connected: bool = False
    last_ping: Optional[datetime] = None
    
    # Context
    active_workspace: Optional[str] = None
    active_task_id: Optional[str] = None
    
    # Capabilities
    can_approve: bool = True
    can_execute: bool = True
    notifications_enabled: bool = True
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Metadata
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


class SessionManager:
    """
    Manages user sessions across devices.
    
    Features:
    - Multi-device support
    - Session sync
    - Activity tracking
    - Push notifications
    """
    
    def __init__(self):
        """Initialize session manager."""
        self._sessions: Dict[str, AgentSession] = {}
        self._user_sessions: Dict[str, List[str]] = {}  # user_id -> session_ids
    
    def create_session(
        self,
        user_id: str,
        tenant_id: str,
        device_type: DeviceType = DeviceType.WEB,
        device_name: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> AgentSession:
        """Create a new session.
        
        Args:
            user_id: User identifier
            tenant_id: Tenant identifier
            device_type: Type of device
            device_name: Device name
            device_id: Device identifier
            
        Returns:
            Created session
        """
        session = AgentSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            tenant_id=tenant_id,
            device_type=device_type,
            device_name=device_name,
            device_id=device_id,
        )
        
        self._sessions[session.id] = session
        
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = []
        self._user_sessions[user_id].append(session.id)
        
        return session
    
    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)
    
    def get_user_sessions(self, user_id: str) -> List[AgentSession]:
        """Get all sessions for a user."""
        session_ids = self._user_sessions.get(user_id, [])
        return [self._sessions[sid] for sid in session_ids if sid in self._sessions]
    
    def get_active_sessions(self, user_id: str) -> List[AgentSession]:
        """Get active sessions for a user."""
        sessions = self.get_user_sessions(user_id)
        return [s for s in sessions if s.status == SessionStatus.ACTIVE]
    
    def update_activity(self, session_id: str) -> None:
        """Update session activity."""
        session = self._sessions.get(session_id)
        if session:
            session.last_ping = datetime.utcnow()
            session.status = SessionStatus.ACTIVE
    
    def set_workspace(
        self,
        session_id: str,
        workspace_id: str,
    ) -> None:
        """Set active workspace for a session."""
        session = self._sessions.get(session_id)
        if session:
            session.active_workspace = workspace_id
    
    def set_active_task(
        self,
        session_id: str,
        task_id: Optional[str],
    ) -> None:
        """Set active task for a session."""
        session = self._sessions.get(session_id)
        if session:
            session.active_task_id = task_id
    
    def end_session(self, session_id: str) -> None:
        """End a session."""
        session = self._sessions.get(session_id)
        if session:
            session.status = SessionStatus.EXPIRED
            session.connected = False
    
    def sync_state(self, user_id: str) -> Dict[str, Any]:
        """Sync state across all user sessions.
        
        Args:
            user_id: User identifier
            
        Returns:
            Synced state
        """
        sessions = self.get_active_sessions(user_id)
        
        # Find most recent activity
        most_recent = max(sessions, key=lambda s: s.last_ping or s.created_at, default=None)
        
        if not most_recent:
            return {}
        
        return {
            "active_workspace": most_recent.active_workspace,
            "active_task_id": most_recent.active_task_id,
            "devices": [
                {
                    "type": s.device_type.value,
                    "name": s.device_name,
                    "connected": s.connected,
                    "last_active": s.last_ping.isoformat() if s.last_ping else None,
                }
                for s in sessions
            ],
        }
    
    def broadcast_to_user(
        self,
        user_id: str,
        message: Dict[str, Any],
    ) -> int:
        """Broadcast message to all user sessions.
        
        Args:
            user_id: User identifier
            message: Message to broadcast
            
        Returns:
            Number of sessions notified
        """
        sessions = self.get_active_sessions(user_id)
        connected = [s for s in sessions if s.connected and s.notifications_enabled]
        
        # Would push to websocket connections
        # for session in connected:
        #     await websocket_manager.send(session.id, message)
        
        return len(connected)

