"""Workspace Sentinel — concurrency control for refactoring operations.

Prevents two refactor operations from writing to the same workspace
simultaneously using a file-based lock.  When a second operation
attempts to acquire a workspace that is already locked, the sentinel
raises ``WorkspaceBusyError`` (mapped to HTTP 409 Conflict).

The lock file (``<workspace>/.code4u.lock``) is automatically
released when the context manager exits, even on exceptions.

Usage::

    sentinel = WorkspaceSentinel()

    async with sentinel.acquire(workspace, session_id) as guard:
        # workspace is exclusively locked
        await executor.run(plan, context, intent=intent)
    # lock released automatically

    # Non-async version:
    with sentinel.acquire_sync(workspace, session_id) as guard:
        ...
"""

from __future__ import annotations

import time
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import structlog
from filelock import FileLock, Timeout

logger = structlog.get_logger("sentinel")

_DEFAULT_TIMEOUT = 0.5


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class WorkspaceBusyError(Exception):
    """Raised when a workspace is already locked by another operation."""

    def __init__(
        self,
        workspace: str,
        owning_session: Optional[str] = None,
        message: Optional[str] = None,
    ):
        self.workspace = workspace
        self.owning_session = owning_session
        super().__init__(
            message or (
                f"Workspace '{workspace}' is currently locked"
                + (f" by session {owning_session}" if owning_session else "")
                + ". Another refactor is in progress. Try again shortly."
            )
        )


# ---------------------------------------------------------------------------
# LockGuard — returned from acquire, tracks metadata
# ---------------------------------------------------------------------------

@dataclass
class LockGuard:
    """Metadata about an active workspace lock."""
    workspace: str
    session_id: Optional[str]
    acquired_at: float
    lock_path: str


# ---------------------------------------------------------------------------
# WorkspaceSentinel
# ---------------------------------------------------------------------------

class WorkspaceSentinel:
    """File-based concurrency controller for workspace operations.

    Each workspace gets a ``<root>/.code4u.lock`` file.  The lock is
    acquired with a very short timeout (default 0.5s) — if contention
    occurs, the caller receives a ``WorkspaceBusyError`` immediately
    rather than blocking.

    The sentinel also maintains an in-memory registry of which
    session currently owns each workspace lock, enabling richer
    error messages.
    """

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        self._timeout = timeout
        self._active: Dict[str, str] = {}

    def _lock_path(self, workspace: str) -> str:
        root = Path(workspace).resolve()
        return str(root / ".code4u.lock")

    def _owning_session(self, workspace: str) -> Optional[str]:
        resolved = str(Path(workspace).resolve())
        return self._active.get(resolved)

    @asynccontextmanager
    async def acquire(
        self,
        workspace: str,
        session_id: Optional[str] = None,
    ):
        """Async context manager that acquires a workspace lock.

        Yields a ``LockGuard`` on success.  Raises ``WorkspaceBusyError``
        if the workspace is already locked.
        """
        resolved = str(Path(workspace).resolve())
        lock_path = self._lock_path(workspace)
        lock = FileLock(lock_path, timeout=self._timeout)

        existing_owner = self._active.get(resolved)
        if existing_owner and existing_owner != session_id:
            raise WorkspaceBusyError(
                workspace=resolved,
                owning_session=existing_owner,
            )

        try:
            lock.acquire(timeout=self._timeout)
        except Timeout:
            raise WorkspaceBusyError(
                workspace=resolved,
                owning_session=existing_owner,
            )

        self._active[resolved] = session_id or ""
        guard = LockGuard(
            workspace=resolved,
            session_id=session_id,
            acquired_at=time.time(),
            lock_path=lock_path,
        )

        logger.info(
            "workspace_locked",
            workspace=resolved,
            session_id=session_id,
        )

        try:
            yield guard
        finally:
            self._active.pop(resolved, None)
            try:
                lock.release()
            except Exception:
                pass
            logger.info(
                "workspace_unlocked",
                workspace=resolved,
                session_id=session_id,
            )

    @contextmanager
    def acquire_sync(
        self,
        workspace: str,
        session_id: Optional[str] = None,
    ):
        """Synchronous context manager variant."""
        resolved = str(Path(workspace).resolve())
        lock_path = self._lock_path(workspace)
        lock = FileLock(lock_path, timeout=self._timeout)

        existing_owner = self._active.get(resolved)
        if existing_owner and existing_owner != session_id:
            raise WorkspaceBusyError(
                workspace=resolved,
                owning_session=existing_owner,
            )

        try:
            lock.acquire(timeout=self._timeout)
        except Timeout:
            raise WorkspaceBusyError(
                workspace=resolved,
                owning_session=existing_owner,
            )

        self._active[resolved] = session_id or ""
        guard = LockGuard(
            workspace=resolved,
            session_id=session_id,
            acquired_at=time.time(),
            lock_path=lock_path,
        )

        logger.info(
            "workspace_locked",
            workspace=resolved,
            session_id=session_id,
        )

        try:
            yield guard
        finally:
            self._active.pop(resolved, None)
            try:
                lock.release()
            except Exception:
                pass
            logger.info(
                "workspace_unlocked",
                workspace=resolved,
                session_id=session_id,
            )

    def is_locked(self, workspace: str) -> bool:
        """Check whether a workspace is currently locked."""
        resolved = str(Path(workspace).resolve())
        return resolved in self._active

    def owning_session(self, workspace: str) -> Optional[str]:
        """Return the session ID that currently owns the lock, or None."""
        return self._owning_session(workspace)
