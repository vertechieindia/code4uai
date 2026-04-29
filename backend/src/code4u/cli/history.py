"""Refactor analytics — local-only job history.

Every completed ``PlanExecutor.run()`` writes a one-line JSON record to
``~/.code4u/history.jsonl``.  This allows developers to track success vs.
failure rates across refactor types and identify which patterns work best.

Records are **append-only** and never sent to a remote server.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

_HISTORY_DIR = Path.home() / ".code4u"
_HISTORY_FILE = _HISTORY_DIR / "history.jsonl"


def _ensure_dir() -> None:
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def record_job(
    *,
    execution_id: str,
    intent: str,
    intent_type: str,
    file_count: int,
    duration_ms: float,
    outcome: str,
    validation_passed: bool,
    error: Optional[str] = None,
    workspace: Optional[str] = None,
    dry_run: bool = False,
) -> None:
    """Append a single job record to ``~/.code4u/history.jsonl``.

    This function is fail-safe: filesystem errors are silently ignored
    so analytics never break the refactor pipeline.
    """
    entry: Dict[str, Any] = {
        "ts": time.time(),
        "execution_id": execution_id,
        "intent": intent,
        "intent_type": intent_type,
        "file_count": file_count,
        "duration_ms": round(duration_ms, 1),
        "outcome": outcome,
        "validation_passed": validation_passed,
        "dry_run": dry_run,
    }
    if error:
        entry["error"] = error[:500]
    if workspace:
        entry["workspace"] = workspace

    try:
        _ensure_dir()
        with open(_HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass


def read_history(limit: int = 50) -> list:
    """Read the last *limit* records from the history file."""
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, FileNotFoundError):
        return []

    entries = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def summary_stats() -> Dict[str, Any]:
    """Compute aggregate stats from the full history file."""
    records = read_history(limit=10_000)
    if not records:
        return {"total_jobs": 0}

    total = len(records)
    success = sum(1 for r in records if r.get("outcome") == "APPLIED")
    failed = sum(1 for r in records if r.get("outcome") == "FAILED")
    dry_runs = sum(1 for r in records if r.get("dry_run"))

    by_type: Dict[str, Dict[str, int]] = {}
    for r in records:
        it = r.get("intent_type", "unknown")
        bucket = by_type.setdefault(it, {"total": 0, "success": 0, "failed": 0})
        bucket["total"] += 1
        if r.get("outcome") == "APPLIED":
            bucket["success"] += 1
        elif r.get("outcome") == "FAILED":
            bucket["failed"] += 1

    durations = [r["duration_ms"] for r in records if "duration_ms" in r]
    avg_ms = sum(durations) / len(durations) if durations else 0.0

    return {
        "total_jobs": total,
        "success": success,
        "failed": failed,
        "dry_runs": dry_runs,
        "success_rate": round(success / total * 100, 1) if total else 0,
        "avg_duration_ms": round(avg_ms, 1),
        "by_intent_type": by_type,
    }
