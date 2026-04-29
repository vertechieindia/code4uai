"""Review Analytics Model — audit trail and ROI metrics.

Every automated PR review generates a ``ReviewAudit`` record
persisted to ``~/.code4u/review_audit.jsonl``.  The ``AuditStore``
provides aggregation methods for the analytics API.

ROI formula:
    Engineering Minutes Saved = accepted_suggestions * MINUTES_PER_SUGGESTION
    Engineering Days Saved    = minutes_saved / 480  (8-hour workday)
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("analytics")

_AUDIT_DIR = Path.home() / ".code4u"
_AUDIT_FILE = _AUDIT_DIR / "review_audit.jsonl"

MINUTES_PER_SUGGESTION = 5
MINUTES_PER_WORKDAY = 480


# ---------------------------------------------------------------------------
# ReviewAudit record
# ---------------------------------------------------------------------------

@dataclass
class ReviewAudit:
    """Immutable record of a single PR review session."""
    repo_name: str
    pr_id: int
    pr_url: str = ""
    author: str = ""
    head_sha: str = ""
    suggestions_count: int = 0
    accepted_count: int = 0
    triggered_recipes: List[str] = field(default_factory=list)
    files_reviewed: int = 0
    review_duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    status: str = "completed"

    @property
    def minutes_saved(self) -> float:
        return self.accepted_count * MINUTES_PER_SUGGESTION

    @property
    def adoption_rate(self) -> float:
        if self.suggestions_count == 0:
            return 0.0
        return self.accepted_count / self.suggestions_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repoName": self.repo_name,
            "prId": self.pr_id,
            "prUrl": self.pr_url,
            "author": self.author,
            "headSha": self.head_sha,
            "suggestionsCount": self.suggestions_count,
            "acceptedCount": self.accepted_count,
            "triggeredRecipes": self.triggered_recipes,
            "filesReviewed": self.files_reviewed,
            "reviewDurationMs": round(self.review_duration_ms, 1),
            "timestamp": self.timestamp,
            "status": self.status,
            "minutesSaved": self.minutes_saved,
            "adoptionRate": round(self.adoption_rate, 3),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ReviewAudit":
        return ReviewAudit(
            repo_name=data.get("repoName", data.get("repo_name", "")),
            pr_id=data.get("prId", data.get("pr_id", 0)),
            pr_url=data.get("prUrl", data.get("pr_url", "")),
            author=data.get("author", ""),
            head_sha=data.get("headSha", data.get("head_sha", "")),
            suggestions_count=data.get("suggestionsCount", data.get("suggestions_count", 0)),
            accepted_count=data.get("acceptedCount", data.get("accepted_count", 0)),
            triggered_recipes=data.get("triggeredRecipes", data.get("triggered_recipes", [])),
            files_reviewed=data.get("filesReviewed", data.get("files_reviewed", 0)),
            review_duration_ms=data.get("reviewDurationMs", data.get("review_duration_ms", 0.0)),
            timestamp=data.get("timestamp", 0.0),
            status=data.get("status", "completed"),
        )


# ---------------------------------------------------------------------------
# AuditStore — append-only JSONL persistence + aggregation
# ---------------------------------------------------------------------------

class AuditStore:
    """Append-only store for review audit records.

    Writes to ``~/.code4u/review_audit.jsonl`` by default.
    All reads load from disk so the store survives server restarts.
    """

    def __init__(self, audit_file: Optional[Path] = None):
        self._file = audit_file or _AUDIT_FILE
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)

    def record(self, audit: ReviewAudit) -> None:
        """Append an audit record to the store."""
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit.to_dict()) + "\n")
        except Exception as exc:
            logger.warning("audit_write_failed", error=str(exc)[:200])

    def load_all(self) -> List[ReviewAudit]:
        """Load all audit records from disk."""
        if not self._file.is_file():
            return []
        records: List[ReviewAudit] = []
        try:
            for line in self._file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(ReviewAudit.from_dict(json.loads(line)))
                except Exception:
                    pass
        except Exception:
            pass
        return records

    def load_recent(self, limit: int = 50) -> List[ReviewAudit]:
        """Load the most recent audit records."""
        all_records = self.load_all()
        all_records.sort(key=lambda r: r.timestamp, reverse=True)
        return all_records[:limit]

    def load_since(self, since_ts: float) -> List[ReviewAudit]:
        """Load records after a specific timestamp."""
        return [r for r in self.load_all() if r.timestamp >= since_ts]

    # -------------------------------------------------------------------
    # Aggregation methods
    # -------------------------------------------------------------------

    def summary(self, since_ts: float = 0.0) -> Dict[str, Any]:
        """Compute a full analytics summary.

        Returns the "Savings Report" — total suggestions, accepted,
        adoption rate, time saved, and per-repo breakdown.
        """
        records = self.load_since(since_ts) if since_ts else self.load_all()
        return self._aggregate(records)

    def _aggregate(self, records: List[ReviewAudit]) -> Dict[str, Any]:
        if not records:
            return {
                "totalReviews": 0,
                "totalSuggestions": 0,
                "totalAccepted": 0,
                "adoptionRate": 0.0,
                "totalMinutesSaved": 0.0,
                "totalDaysSaved": 0.0,
                "totalFilesReviewed": 0,
                "repos": {},
                "topRecipes": [],
                "authorStats": {},
                "period": {"from": 0, "to": 0},
            }

        total_suggestions = sum(r.suggestions_count for r in records)
        total_accepted = sum(r.accepted_count for r in records)
        total_minutes = total_accepted * MINUTES_PER_SUGGESTION
        total_files = sum(r.files_reviewed for r in records)

        adoption = total_accepted / total_suggestions if total_suggestions else 0.0

        # Per-repo breakdown
        repo_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "reviews": 0, "suggestions": 0, "accepted": 0, "minutesSaved": 0.0,
        })
        for r in records:
            rs = repo_stats[r.repo_name]
            rs["reviews"] += 1
            rs["suggestions"] += r.suggestions_count
            rs["accepted"] += r.accepted_count
            rs["minutesSaved"] += r.minutes_saved

        # Recipe frequency heatmap
        recipe_counter: Counter = Counter()
        for r in records:
            recipe_counter.update(r.triggered_recipes)

        top_recipes = [
            {"recipeId": rid, "triggerCount": count}
            for rid, count in recipe_counter.most_common(20)
        ]

        # Per-author stats
        author_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "reviews": 0, "suggestions": 0, "accepted": 0,
        })
        for r in records:
            if r.author:
                a = author_stats[r.author]
                a["reviews"] += 1
                a["suggestions"] += r.suggestions_count
                a["accepted"] += r.accepted_count

        timestamps = [r.timestamp for r in records if r.timestamp > 0]

        return {
            "totalReviews": len(records),
            "totalSuggestions": total_suggestions,
            "totalAccepted": total_accepted,
            "adoptionRate": round(adoption, 3),
            "totalMinutesSaved": round(total_minutes, 1),
            "totalDaysSaved": round(total_minutes / MINUTES_PER_WORKDAY, 2),
            "totalFilesReviewed": total_files,
            "repos": dict(repo_stats),
            "topRecipes": top_recipes,
            "authorStats": dict(author_stats),
            "period": {
                "from": min(timestamps) if timestamps else 0,
                "to": max(timestamps) if timestamps else 0,
            },
        }

    def recipe_heatmap(self, since_ts: float = 0.0) -> List[Dict[str, Any]]:
        """Return recipes ranked by trigger frequency (noisiest first)."""
        records = self.load_since(since_ts) if since_ts else self.load_all()
        counter: Counter = Counter()
        for r in records:
            counter.update(r.triggered_recipes)
        return [
            {"recipeId": rid, "triggerCount": count}
            for rid, count in counter.most_common()
        ]

    def clear(self) -> None:
        """Remove all audit records (for testing)."""
        if self._file.is_file():
            self._file.unlink()
