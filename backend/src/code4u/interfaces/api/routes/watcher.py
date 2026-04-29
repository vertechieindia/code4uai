"""Watcher API — file system monitoring endpoints.

Endpoints:
  - ``POST /watcher/start``   — start watching a workspace.
  - ``POST /watcher/stop``    — stop the active watcher.
  - ``GET  /watcher/status``  — current watcher state + recent jobs.
  - ``POST /watcher/reindex`` — manually trigger reindex of a file.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from code4u.core.watcher import WorkspaceWatcher, PartialReindexJob

router = APIRouter()

_active_watcher: Optional[WorkspaceWatcher] = None


class WatcherStartRequest(BaseModel):
    workspacePath: str = Field(..., description="Directory to watch.")
    debouncMs: float = Field(200, description="Debounce window (ms).")


class ReindexRequest(BaseModel):
    filePath: str = Field(..., description="Absolute file path to reindex.")


@router.post("/watcher/start")
async def start_watcher(request: WatcherStartRequest):
    """Start watching a workspace for file changes."""
    global _active_watcher

    if _active_watcher is not None and _active_watcher.is_running:
        _active_watcher.stop()

    from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
        SymbolIndexer,
    )

    indexer = SymbolIndexer()
    dep_map = indexer.index_workspace(request.workspacePath)

    _active_watcher = WorkspaceWatcher(
        workspace_path=request.workspacePath,
        dep_map=dep_map,
        debounce_ms=request.debouncMs,
    )
    _active_watcher.start()

    return {
        "status": "started",
        "workspace": request.workspacePath,
        "indexedFiles": dep_map.stats["indexed_files"],
    }


@router.post("/watcher/stop")
async def stop_watcher():
    """Stop the active file watcher."""
    global _active_watcher
    if _active_watcher is None or not _active_watcher.is_running:
        return {"status": "not_running"}

    _active_watcher.stop()
    return {"status": "stopped"}


@router.get("/watcher/status")
async def watcher_status():
    """Return current watcher state and recent reindex jobs."""
    if _active_watcher is None:
        return {"running": False, "recentJobs": []}

    return {
        "running": _active_watcher.is_running,
        "recentJobs": [j.to_dict() for j in _active_watcher.recent_jobs],
        "jobCount": len(_active_watcher.recent_jobs),
    }


@router.post("/watcher/reindex")
async def manual_reindex(request: ReindexRequest):
    """Manually trigger a reindex for a specific file."""
    if _active_watcher is None or not _active_watcher.is_running:
        raise HTTPException(
            status_code=409,
            detail="No active watcher. Start one first.",
        )

    job = _active_watcher.force_reindex(request.filePath)
    return {
        "status": "reindexed",
        "job": job.to_dict(),
    }
