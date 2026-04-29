"""Stateful session management for iterative refactoring.

Tracks conversation history across multiple refactor operations so
that follow-up intents ("Actually, use camelCase for that") can
reference previous plans without re-indexing the workspace.

Sessions are persisted to ``~/.code4u/sessions/`` as JSON files,
surviving server restarts.

Usage::

    mgr = SessionManager()
    session = mgr.create_session(workspace_path="/my/project")
    session = mgr.add_job(session.session_id, job)
    session = mgr.get_session(session.session_id)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("session_manager")

_SESSIONS_DIR = Path.home() / ".code4u" / "sessions"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RefactorJobRecord:
    """Immutable record of one refactor operation within a session."""
    job_id: str
    intent: str
    intent_type: str
    file_path: str
    affected_files: List[str] = field(default_factory=list)
    diffs: Dict[str, str] = field(default_factory=dict)
    plan_summary: Optional[Dict[str, Any]] = None
    state: str = ""
    execution_id: str = ""
    timestamp: float = 0.0
    success: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RefactorJobRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DependencySnapshot:
    """Lightweight snapshot of index stats at session creation time."""
    indexed_files: int = 0
    total_symbols: int = 0
    total_imports: int = 0
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DependencySnapshot":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


_DEFAULT_OWNER = "local_user"


@dataclass
class Session:
    """A stateful refactoring conversation.

    Tracks the workspace, all jobs performed in this session, and
    the DependencyMap stats at session creation time.
    """
    session_id: str
    workspace_path: str
    owner_id: str = _DEFAULT_OWNER
    jobs: List[RefactorJobRecord] = field(default_factory=list)
    dep_snapshot: Optional[DependencySnapshot] = None
    created_at: float = 0.0
    updated_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def last_job(self) -> Optional[RefactorJobRecord]:
        return self.jobs[-1] if self.jobs else None

    @property
    def last_successful_job(self) -> Optional[RefactorJobRecord]:
        for job in reversed(self.jobs):
            if job.success:
                return job
        return None

    @property
    def previous_diffs(self) -> Dict[str, str]:
        """Aggregate diffs from the most recent successful job."""
        job = self.last_successful_job
        return dict(job.diffs) if job else {}

    @property
    def previous_intents(self) -> List[str]:
        return [j.intent for j in self.jobs]

    @property
    def job_count(self) -> int:
        return len(self.jobs)

    @property
    def summary(self) -> Dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "workspacePath": self.workspace_path,
            "ownerId": self.owner_id,
            "jobCount": self.job_count,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "lastIntent": self.last_job.intent if self.last_job else None,
            "lastState": self.last_job.state if self.last_job else None,
            "previousIntents": self.previous_intents,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "workspace_path": self.workspace_path,
            "owner_id": self.owner_id,
            "jobs": [j.to_dict() for j in self.jobs],
            "dep_snapshot": self.dep_snapshot.to_dict() if self.dep_snapshot else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        jobs_raw = data.get("jobs", [])
        jobs = [RefactorJobRecord.from_dict(j) for j in jobs_raw]
        snap_raw = data.get("dep_snapshot")
        snap = DependencySnapshot.from_dict(snap_raw) if snap_raw else None
        return cls(
            session_id=data["session_id"],
            workspace_path=data["workspace_path"],
            owner_id=data.get("owner_id", _DEFAULT_OWNER),
            jobs=jobs,
            dep_snapshot=snap,
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

class SessionManager:
    """Manages refactor sessions with disk persistence.

    Sessions are stored as individual JSON files in
    ``~/.code4u/sessions/{session_id}.json``.  The in-memory cache
    is populated lazily on first access and updated on every mutation.
    """

    def __init__(self, sessions_dir: Optional[Path] = None):
        self._dir = sessions_dir or _SESSIONS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Session] = {}
        self._loaded_from_disk = False

    def _ensure_loaded(self) -> None:
        """Lazily load all sessions from disk on first access."""
        if self._loaded_from_disk:
            return
        self._loaded_from_disk = True
        for fp in self._dir.glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                session = Session.from_dict(data)
                self._cache[session.session_id] = session
            except Exception as exc:
                logger.warning("session_load_failed", path=str(fp), error=str(exc))

    def _persist(self, session: Session) -> None:
        """Write a session to disk."""
        try:
            fp = self._dir / f"{session.session_id}.json"
            fp.write_text(
                json.dumps(session.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("session_persist_failed", error=str(exc))

    # -- Public API ----------------------------------------------------------

    def create_session(
        self,
        workspace_path: str,
        dep_snapshot: Optional[DependencySnapshot] = None,
        owner_id: Optional[str] = None,
    ) -> Session:
        """Create a new session for a workspace."""
        now = time.time()
        session = Session(
            session_id=str(uuid.uuid4()),
            workspace_path=workspace_path,
            owner_id=owner_id or _DEFAULT_OWNER,
            dep_snapshot=dep_snapshot,
            created_at=now,
            updated_at=now,
        )
        self._cache[session.session_id] = session
        self._persist(session)
        logger.info(
            "session_created",
            session_id=session.session_id,
            workspace=workspace_path,
        )
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by ID (from cache or disk)."""
        self._ensure_loaded()
        return self._cache.get(session_id)

    def add_job(self, session_id: str, job: RefactorJobRecord) -> Optional[Session]:
        """Append a completed job to the session and persist."""
        self._ensure_loaded()
        session = self._cache.get(session_id)
        if session is None:
            return None
        if not job.timestamp:
            job.timestamp = time.time()
        session.jobs.append(job)
        session.updated_at = time.time()
        self._persist(session)
        logger.info(
            "session_job_added",
            session_id=session_id,
            job_id=job.job_id,
            intent=job.intent[:60],
            job_count=len(session.jobs),
        )
        return session

    def list_sessions(
        self,
        limit: int = 20,
        owner_id: Optional[str] = None,
    ) -> List[Session]:
        """Return recent sessions, newest first.

        When *owner_id* is provided, only sessions belonging to that
        user are returned — enforcing multi-tenant privacy.
        """
        self._ensure_loaded()
        pool = self._cache.values()
        if owner_id:
            pool = [s for s in pool if s.owner_id == owner_id]
        sessions = sorted(pool, key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session from cache and disk."""
        self._ensure_loaded()
        session = self._cache.pop(session_id, None)
        if session is None:
            return False
        fp = self._dir / f"{session_id}.json"
        try:
            fp.unlink(missing_ok=True)
        except OSError:
            pass
        return True

    def get_or_create_session(
        self,
        workspace_path: str,
        session_id: Optional[str] = None,
        dep_snapshot: Optional[DependencySnapshot] = None,
        owner_id: Optional[str] = None,
    ) -> Session:
        """Get an existing session or create a new one."""
        if session_id:
            existing = self.get_session(session_id)
            if existing is not None:
                return existing
        return self.create_session(workspace_path, dep_snapshot, owner_id=owner_id)

    def build_refinement_context(self, session_id: str) -> Dict[str, Any]:
        """Build context from a session for follow-up intents.

        Returns a dict suitable for injection into the LLM prompt,
        containing previous intents, diffs, and file states.
        """
        session = self.get_session(session_id)
        if session is None:
            return {}

        last = session.last_successful_job
        if last is None:
            return {"previousIntents": session.previous_intents}

        return {
            "previousIntents": session.previous_intents,
            "lastIntent": last.intent,
            "lastIntentType": last.intent_type,
            "lastAffectedFiles": last.affected_files,
            "lastDiffs": last.diffs,
            "lastPlanSummary": last.plan_summary,
            "jobCount": session.job_count,
        }
