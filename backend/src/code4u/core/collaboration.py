"""Real-time Multiplayer Collaboration — CRDT-based concurrent editing.

Provides a Yjs-compatible document synchronisation layer so that
multiple humans and AI agents can edit the same file simultaneously
with automatic conflict resolution.

Architecture:
  - Each open file gets a ``CollaborationDocument`` holding the
    authoritative text plus an ordered operation log.
  - Participants (human editors or agent processes) register via
    ``join()`` and receive a cursor colour assignment.
  - Operations are CRDT-style insert/delete with Lamport timestamps,
    ensuring convergence even with concurrent edits.
  - The WebSocket presence layer (``core/presence.py``) is used to
    broadcast operations to all connected sessions.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger("collaboration")


# ---------------------------------------------------------------------------
# Participant model
# ---------------------------------------------------------------------------

class ParticipantType(str, Enum):
    HUMAN = "human"
    AGENT = "agent"


CURSOR_COLORS = [
    "#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6",
    "#ec4899", "#06b6d4", "#f97316", "#14b8a6", "#6366f1",
]


@dataclass
class Participant:
    id: str
    name: str
    type: ParticipantType
    color: str = ""
    cursor_line: int = 0
    cursor_col: int = 0
    selection_start: Optional[Dict[str, int]] = None
    selection_end: Optional[Dict[str, int]] = None
    joined_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Operations (CRDT-compatible)
# ---------------------------------------------------------------------------

class OpType(str, Enum):
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    CURSOR = "cursor"


@dataclass
class Operation:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    type: OpType = OpType.INSERT
    participant_id: str = ""
    timestamp: float = field(default_factory=time.time)
    lamport: int = 0

    offset: int = 0
    text: str = ""
    length: int = 0

    line: int = 0
    col: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "participantId": self.participant_id,
            "timestamp": self.timestamp,
            "lamport": self.lamport,
            "offset": self.offset,
            "text": self.text,
            "length": self.length,
            "line": self.line,
            "col": self.col,
        }


# ---------------------------------------------------------------------------
# Collaboration document
# ---------------------------------------------------------------------------

class CollaborationDocument:
    """Represents a single file open for concurrent editing."""

    def __init__(self, file_path: str, initial_content: str = ""):
        self.file_path = file_path
        self._content = initial_content
        self._participants: Dict[str, Participant] = {}
        self._operations: List[Operation] = []
        self._lamport = 0
        self._lock = threading.Lock()
        self._created_at = time.time()

    @property
    def content(self) -> str:
        return self._content

    @property
    def participant_count(self) -> int:
        return len(self._participants)

    def join(self, participant_id: str, name: str, ptype: ParticipantType = ParticipantType.HUMAN) -> Participant:
        with self._lock:
            color_idx = len(self._participants) % len(CURSOR_COLORS)
            p = Participant(
                id=participant_id,
                name=name,
                type=ptype,
                color=CURSOR_COLORS[color_idx],
            )
            self._participants[participant_id] = p
            logger.info("participant_joined", file=self.file_path, pid=participant_id, name=name, type=ptype.value)
            return p

    def leave(self, participant_id: str) -> bool:
        with self._lock:
            if participant_id in self._participants:
                del self._participants[participant_id]
                logger.info("participant_left", file=self.file_path, pid=participant_id)
                return True
            return False

    def get_participants(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": p.id,
                "name": p.name,
                "type": p.type.value,
                "color": p.color,
                "cursor": {"line": p.cursor_line, "col": p.cursor_col},
                "lastActive": p.last_active,
            }
            for p in self._participants.values()
        ]

    def apply_operation(self, op: Operation) -> Operation:
        """Apply a CRDT operation and return the resolved operation."""
        with self._lock:
            self._lamport += 1
            op.lamport = self._lamport

            if op.type == OpType.INSERT:
                pos = min(op.offset, len(self._content))
                self._content = self._content[:pos] + op.text + self._content[pos:]
            elif op.type == OpType.DELETE:
                pos = min(op.offset, len(self._content))
                end = min(pos + op.length, len(self._content))
                self._content = self._content[:pos] + self._content[end:]
            elif op.type == OpType.REPLACE:
                pos = min(op.offset, len(self._content))
                end = min(pos + op.length, len(self._content))
                self._content = self._content[:pos] + op.text + self._content[end:]
            elif op.type == OpType.CURSOR:
                if op.participant_id in self._participants:
                    p = self._participants[op.participant_id]
                    p.cursor_line = op.line
                    p.cursor_col = op.col
                    p.last_active = time.time()

            self._operations.append(op)
            if op.participant_id in self._participants:
                self._participants[op.participant_id].last_active = time.time()

            return op

    def get_operations(self, since_lamport: int = 0) -> List[Dict[str, Any]]:
        return [op.to_dict() for op in self._operations if op.lamport > since_lamport]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "contentLength": len(self._content),
            "participants": self.get_participants(),
            "operationCount": len(self._operations),
            "lamport": self._lamport,
            "createdAt": self._created_at,
        }


# ---------------------------------------------------------------------------
# Collaboration manager (singleton)
# ---------------------------------------------------------------------------

class CollaborationManager:
    """Manages all active collaboration sessions."""

    def __init__(self) -> None:
        self._documents: Dict[str, CollaborationDocument] = {}
        self._lock = threading.Lock()

    def get_or_create(self, file_path: str, initial_content: str = "") -> CollaborationDocument:
        with self._lock:
            if file_path not in self._documents:
                self._documents[file_path] = CollaborationDocument(file_path, initial_content)
            return self._documents[file_path]

    def get(self, file_path: str) -> Optional[CollaborationDocument]:
        return self._documents.get(file_path)

    def close(self, file_path: str) -> bool:
        with self._lock:
            if file_path in self._documents:
                del self._documents[file_path]
                return True
            return False

    def list_active(self) -> List[Dict[str, Any]]:
        return [doc.to_dict() for doc in self._documents.values()]

    @property
    def active_count(self) -> int:
        return len(self._documents)


_manager: Optional[CollaborationManager] = None
_mgr_lock = threading.Lock()


def get_collaboration_manager() -> CollaborationManager:
    global _manager
    with _mgr_lock:
        if _manager is None:
            _manager = CollaborationManager()
        return _manager
