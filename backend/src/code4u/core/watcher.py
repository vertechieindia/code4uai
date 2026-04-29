"""Incremental File Watcher — real-time DependencyMap sync.

Uses the ``watchdog`` library to monitor file changes in a workspace.
When a ``.py``, ``.ts``, ``.tsx``, ``.js``, or ``.jsx`` file is
created, modified, or deleted, the watcher triggers a
``PartialReindexJob`` that surgically updates the ``DependencyMap``
for only that file — no full workspace re-scan required.

Usage::

    from code4u.core.watcher import WorkspaceWatcher

    dep_map = indexer.index_workspace("/path/to/repo")
    watcher = WorkspaceWatcher(
        workspace_path="/path/to/repo",
        dep_map=dep_map,
    )
    watcher.start()
    # ... dep_map is updated live as files change ...
    watcher.stop()
"""

from __future__ import annotations

import time
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger("watcher")

_WATCHED_EXTENSIONS = frozenset({".py", ".ts", ".tsx", ".js", ".jsx"})

_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "target", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "egg-info",
})


class PartialReindexJob:
    """A single file re-index operation.

    Tracks the file path, event type, and timing metadata.
    """

    __slots__ = ("file_path", "event_type", "root_path", "timestamp", "duration_ms")

    def __init__(
        self,
        file_path: str,
        event_type: str,
        root_path: str,
    ) -> None:
        self.file_path = file_path
        self.event_type = event_type
        self.root_path = root_path
        self.timestamp = time.time()
        self.duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "eventType": self.event_type,
            "rootPath": self.root_path,
            "timestamp": self.timestamp,
            "durationMs": round(self.duration_ms, 2),
        }


class WorkspaceWatcher:
    """Watches a workspace directory for file changes and updates
    a ``DependencyMap`` incrementally.

    The watcher coalesces rapid changes (e.g. multiple saves within
    a debounce window) to avoid redundant re-indexes.
    """

    def __init__(
        self,
        workspace_path: str,
        dep_map: Any,
        *,
        debounce_ms: float = 200,
        on_reindex: Optional[Callable[[PartialReindexJob], None]] = None,
    ) -> None:
        self._workspace = str(Path(workspace_path).resolve())
        self._dep_map = dep_map
        self._debounce_s = debounce_ms / 1000.0
        self._on_reindex = on_reindex

        self._observer: Any = None
        self._running = False
        self._lock = threading.Lock()
        self._pending: Dict[str, float] = {}
        self._debounce_thread: Optional[threading.Thread] = None
        self._jobs: List[PartialReindexJob] = []

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def recent_jobs(self) -> List[PartialReindexJob]:
        """Return the last 100 reindex jobs."""
        return list(self._jobs[-100:])

    def start(self) -> None:
        """Start watching the workspace directory."""
        if self._running:
            return

        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        watcher_ref = self

        class _Handler(FileSystemEventHandler):
            def on_modified(self, event: Any) -> None:
                if not event.is_directory:
                    watcher_ref._on_file_event(event.src_path, "modified")

            def on_created(self, event: Any) -> None:
                if not event.is_directory:
                    watcher_ref._on_file_event(event.src_path, "created")

            def on_deleted(self, event: Any) -> None:
                if not event.is_directory:
                    watcher_ref._on_file_event(event.src_path, "deleted")

            def on_moved(self, event: Any) -> None:
                if not event.is_directory:
                    watcher_ref._on_file_event(event.src_path, "deleted")
                    if hasattr(event, "dest_path"):
                        watcher_ref._on_file_event(event.dest_path, "created")

        self._observer = Observer()
        self._observer.schedule(_Handler(), self._workspace, recursive=True)
        self._observer.start()
        self._running = True

        self._debounce_thread = threading.Thread(
            target=self._debounce_loop, daemon=True,
        )
        self._debounce_thread.start()

        logger.info("watcher_started", workspace=self._workspace)

    def stop(self) -> None:
        """Stop watching and clean up."""
        if not self._running:
            return

        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        logger.info("watcher_stopped", workspace=self._workspace)

    def _on_file_event(self, file_path: str, event_type: str) -> None:
        """Handle a raw file system event."""
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext not in _WATCHED_EXTENSIONS:
            return

        parts = path.parts
        if any(p in _SKIP_DIRS for p in parts):
            return

        resolved = str(path.resolve())

        with self._lock:
            self._pending[resolved] = time.monotonic()

    def _debounce_loop(self) -> None:
        """Background thread that processes pending events after debounce."""
        while self._running:
            time.sleep(self._debounce_s)

            with self._lock:
                now = time.monotonic()
                ready = {
                    fp: ts for fp, ts in self._pending.items()
                    if now - ts >= self._debounce_s
                }
                for fp in ready:
                    del self._pending[fp]

            for fp in ready:
                self._reindex_file(fp)

    def _reindex_file(self, file_path: str) -> None:
        """Perform a partial reindex for a single file."""
        exists = Path(file_path).is_file()
        event_type = "deleted" if not exists else "modified"

        job = PartialReindexJob(
            file_path=file_path,
            event_type=event_type,
            root_path=self._workspace,
        )

        t0 = time.monotonic()

        try:
            from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
                SymbolIndexer,
            )

            if not exists:
                self._dep_map.remove_file(file_path)
            else:
                indexer = SymbolIndexer()
                indexer.index_single_file(
                    file_path, self._dep_map, root_path=self._workspace,
                )

            job.duration_ms = (time.monotonic() - t0) * 1000

            self._jobs.append(job)
            if len(self._jobs) > 500:
                self._jobs = self._jobs[-250:]

            if self._on_reindex:
                self._on_reindex(job)

            logger.debug(
                "file_reindexed",
                file=file_path,
                change_type=event_type,
                duration_ms=round(job.duration_ms, 2),
            )

        except Exception as exc:
            logger.warning(
                "reindex_failed",
                file=file_path,
                error=str(exc)[:200],
            )

    def force_reindex(self, file_path: str) -> PartialReindexJob:
        """Manually trigger a reindex for a specific file (no debounce)."""
        resolved = str(Path(file_path).resolve())
        self._reindex_file(resolved)
        return self._jobs[-1] if self._jobs else PartialReindexJob(
            file_path=resolved, event_type="manual", root_path=self._workspace,
        )
