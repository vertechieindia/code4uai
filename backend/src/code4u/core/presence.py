"""Presence Manager — real-time session tracking & intent locking.

Tracks which users/agents are online, which files they have open,
and what refactoring intent they are currently executing.  Provides
a "Soft-Lock" system that warns (or blocks) when two developers
try to touch the same files simultaneously.

Architecture:
  - ``PresenceManager`` is the central hub (singleton per process).
  - Each connected client is a ``PresenceSession`` with an ID, display
    name, open files, and optional active intent.
  - When a ``MigrationPlan`` or refactor starts, the session registers
    a ``LockIntent`` listing all impacted files.
  - All connected WebSocket clients receive broadcast messages for
    session joins, file opens, lock intents, and departures.
  - ``is_file_locked()`` / ``check_conflict()`` allow the refactor
    API to reject operations on files already under active intent.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger("presence")


# ---------------------------------------------------------------------------
# Message types for WebSocket broadcast
# ---------------------------------------------------------------------------

class MessageType(str, Enum):
    SESSION_JOIN = "SESSION_JOIN"
    SESSION_LEAVE = "SESSION_LEAVE"
    FILE_OPEN = "FILE_OPEN"
    FILE_CLOSE = "FILE_CLOSE"
    LOCK_INTENT = "LOCK_INTENT"
    UNLOCK_INTENT = "UNLOCK_INTENT"
    INCOMING_LOCK = "INCOMING_LOCK"
    STAGE_CREATED = "STAGE_CREATED"
    STAGE_UPDATED = "STAGE_UPDATED"
    STAGE_APPROVED = "STAGE_APPROVED"
    STAGE_REJECTED = "STAGE_REJECTED"
    HEARTBEAT = "HEARTBEAT"
    SWARM_STARTED = "SWARM_STARTED"
    SWARM_UPDATE = "SWARM_UPDATE"
    SWARM_COMPLETED = "SWARM_COMPLETED"
    DRIFT_DETECTED = "DRIFT_DETECTED"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class LockIntent:
    """A soft-lock on a set of files during an active refactor."""
    intent_id: str
    session_id: str
    description: str
    locked_files: List[str]
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intentId": self.intent_id,
            "sessionId": self.session_id,
            "description": self.description,
            "lockedFiles": self.locked_files,
            "createdAt": self.created_at,
        }


@dataclass
class PresenceSession:
    """Tracks the real-time state of one connected client."""
    session_id: str
    display_name: str
    workspace: str
    current_files: List[str] = field(default_factory=list)
    active_intent: Optional[LockIntent] = None
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "displayName": self.display_name,
            "workspace": self.workspace,
            "currentFiles": self.current_files,
            "activeIntent": self.active_intent.to_dict() if self.active_intent else None,
            "connectedAt": self.connected_at,
            "lastHeartbeat": self.last_heartbeat,
        }


# ---------------------------------------------------------------------------
# PresenceManager (singleton hub)
# ---------------------------------------------------------------------------

class PresenceManager:
    """Central hub for presence tracking and intent broadcasting.

    Thread-safe via asyncio primitives.  WebSocket connections register
    a send callback; the manager broadcasts to all callbacks.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, PresenceSession] = {}
        self._ws_callbacks: Dict[str, Callable] = {}  # session_id → async send fn
        self._lock = asyncio.Lock()

    # -- Session lifecycle ---------------------------------------------------

    async def join(
        self,
        session_id: str,
        display_name: str,
        workspace: str,
        send_callback: Optional[Callable] = None,
    ) -> PresenceSession:
        """Register a new presence session."""
        async with self._lock:
            session = PresenceSession(
                session_id=session_id,
                display_name=display_name,
                workspace=workspace,
            )
            self._sessions[session_id] = session
            if send_callback:
                self._ws_callbacks[session_id] = send_callback

        logger.info("session_joined", session_id=session_id, name=display_name)
        await self._broadcast(MessageType.SESSION_JOIN, {
            "session": session.to_dict(),
        }, exclude=session_id)
        return session

    async def leave(self, session_id: str) -> None:
        """Remove a session and release any locks it held."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            self._ws_callbacks.pop(session_id, None)

        if session:
            logger.info("session_left", session_id=session_id)
            await self._broadcast(MessageType.SESSION_LEAVE, {
                "sessionId": session_id,
                "displayName": session.display_name,
            })

    # -- File tracking -------------------------------------------------------

    async def open_file(self, session_id: str, file_path: str) -> None:
        """Record that a session has opened a file."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session and file_path not in session.current_files:
                session.current_files.append(file_path)

        await self._broadcast(MessageType.FILE_OPEN, {
            "sessionId": session_id,
            "filePath": file_path,
        }, exclude=session_id)

    async def close_file(self, session_id: str, file_path: str) -> None:
        """Record that a session has closed a file."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session and file_path in session.current_files:
                session.current_files.remove(file_path)

        await self._broadcast(MessageType.FILE_CLOSE, {
            "sessionId": session_id,
            "filePath": file_path,
        }, exclude=session_id)

    # -- Intent locking ------------------------------------------------------

    async def lock_intent(
        self,
        session_id: str,
        description: str,
        locked_files: List[str],
    ) -> LockIntent:
        """Register a lock intent for a set of files.

        Returns the created ``LockIntent``.
        Raises ``FileLockedError`` if any file is already locked
        by another session.
        """
        conflict = self.check_conflict(session_id, locked_files)
        if conflict:
            raise FileLockedError(
                file_path=conflict["file"],
                owning_session=conflict["ownerSessionId"],
                owning_name=conflict["ownerName"],
            )

        intent = LockIntent(
            intent_id=str(uuid.uuid4()),
            session_id=session_id,
            description=description,
            locked_files=locked_files,
        )

        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.active_intent = intent

        logger.info(
            "intent_locked",
            session_id=session_id,
            files=len(locked_files),
            description=description,
        )

        await self._broadcast(MessageType.LOCK_INTENT, {
            "intent": intent.to_dict(),
        }, exclude=session_id)

        # Send INCOMING_LOCK to sessions that have the same files open
        await self._notify_overlapping_sessions(session_id, intent)

        return intent

    async def unlock_intent(self, session_id: str) -> None:
        """Release a session's active lock intent."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.active_intent = None

        logger.info("intent_unlocked", session_id=session_id)
        await self._broadcast(MessageType.UNLOCK_INTENT, {
            "sessionId": session_id,
        })

    # -- Conflict detection --------------------------------------------------

    def check_conflict(
        self,
        requesting_session: str,
        files: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Check if any file is locked by another session.

        Returns conflict details or None if no conflict.
        """
        for sid, session in self._sessions.items():
            if sid == requesting_session:
                continue
            if not session.active_intent:
                continue
            overlap = set(files) & set(session.active_intent.locked_files)
            if overlap:
                return {
                    "file": sorted(overlap)[0],
                    "overlappingFiles": sorted(overlap),
                    "ownerSessionId": sid,
                    "ownerName": session.display_name,
                    "intentDescription": session.active_intent.description,
                    "intentId": session.active_intent.intent_id,
                }
        return None

    def is_file_locked(self, file_path: str, exclude_session: str = "") -> bool:
        """Check if a specific file is under any active lock intent."""
        for sid, session in self._sessions.items():
            if sid == exclude_session:
                continue
            if session.active_intent and file_path in session.active_intent.locked_files:
                return True
        return False

    def get_file_owner(self, file_path: str) -> Optional[Dict[str, str]]:
        """Return info about the session locking a file, or None."""
        for sid, session in self._sessions.items():
            if session.active_intent and file_path in session.active_intent.locked_files:
                return {
                    "sessionId": sid,
                    "displayName": session.display_name,
                    "intentDescription": session.active_intent.description,
                }
        return None

    # -- Queries -------------------------------------------------------------

    def list_sessions(self, workspace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all active sessions, optionally filtered by workspace."""
        results = []
        for session in self._sessions.values():
            if workspace and session.workspace != workspace:
                continue
            results.append(session.to_dict())
        return results

    def get_session(self, session_id: str) -> Optional[PresenceSession]:
        """Get a specific session by ID."""
        return self._sessions.get(session_id)

    def active_locks(self) -> List[Dict[str, Any]]:
        """Return all active lock intents across all sessions."""
        locks = []
        for session in self._sessions.values():
            if session.active_intent:
                locks.append({
                    "session": session.to_dict(),
                    "intent": session.active_intent.to_dict(),
                })
        return locks

    async def heartbeat(self, session_id: str) -> None:
        """Update heartbeat timestamp for a session."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_heartbeat = time.time()

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    # -- Broadcasting --------------------------------------------------------

    async def _broadcast(
        self,
        msg_type: MessageType,
        payload: Dict[str, Any],
        exclude: str = "",
    ) -> None:
        """Send a message to all connected WebSocket clients."""
        message = {"type": msg_type.value, "payload": payload, "timestamp": time.time()}
        dead: List[str] = []

        for sid, callback in list(self._ws_callbacks.items()):
            if sid == exclude:
                continue
            try:
                await callback(message)
            except Exception:
                dead.append(sid)

        for sid in dead:
            self._ws_callbacks.pop(sid, None)

    async def _notify_overlapping_sessions(
        self, locking_session: str, intent: LockIntent,
    ) -> None:
        """Send INCOMING_LOCK to sessions that have overlapping open files."""
        locked_set = set(intent.locked_files)
        for sid, session in self._sessions.items():
            if sid == locking_session:
                continue
            overlap = set(session.current_files) & locked_set
            if overlap and sid in self._ws_callbacks:
                try:
                    await self._ws_callbacks[sid]({
                        "type": MessageType.INCOMING_LOCK.value,
                        "payload": {
                            "lockerSessionId": locking_session,
                            "lockerName": self._sessions[locking_session].display_name,
                            "overlappingFiles": sorted(overlap),
                            "intentDescription": intent.description,
                        },
                        "timestamp": time.time(),
                    })
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class FileLockedError(Exception):
    """Raised when a file is locked by another session's intent."""

    def __init__(
        self,
        file_path: str,
        owning_session: str,
        owning_name: str = "",
    ):
        self.file_path = file_path
        self.owning_session = owning_session
        self.owning_name = owning_name
        msg = f"File '{file_path}' is locked by {owning_name or owning_session}"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_manager: Optional[PresenceManager] = None


def get_presence_manager() -> PresenceManager:
    """Return the global PresenceManager singleton."""
    global _manager
    if _manager is None:
        _manager = PresenceManager()
    return _manager
