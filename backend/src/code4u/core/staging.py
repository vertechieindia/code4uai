"""Shared Staging Area — collaborative pre-commit review.

Instead of writing directly to disk, a developer or AI agent can
"Stage" a proposed change.  Other team members can fetch, review,
approve, or reject the staged diff in real-time before it touches
the filesystem.

This is the "Live PR" experience — iterate on AI suggestions
before they become part of the git history.

Each ``StagedChange`` holds:
  - The full ``MigrationPlan`` or ``ProposedPlan`` diff.
  - Author info, timestamps, and approval status.
  - A list of reviewer votes (approve/reject with comments).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("staging")


class StageStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    EXPIRED = "expired"


@dataclass
class FileDiff:
    """A single file's diff in a staged change."""
    file_path: str
    operation: str  # "edit", "create", "delete"
    old_content: str = ""
    new_content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "operation": self.operation,
            "oldContent": self.old_content,
            "newContent": self.new_content,
        }


@dataclass
class ReviewVote:
    """A reviewer's decision on a staged change."""
    reviewer_id: str
    reviewer_name: str
    decision: str  # "approve" or "reject"
    comment: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reviewerId": self.reviewer_id,
            "reviewerName": self.reviewer_name,
            "decision": self.decision,
            "comment": self.comment,
            "timestamp": self.timestamp,
        }


@dataclass
class StagedChange:
    """A proposed change awaiting team review."""
    stage_id: str
    author_session_id: str
    author_name: str
    workspace: str
    description: str
    diffs: List[FileDiff] = field(default_factory=list)
    status: StageStatus = StageStatus.PENDING
    votes: List[ReviewVote] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    required_approvals: int = 1

    @property
    def approval_count(self) -> int:
        return sum(1 for v in self.votes if v.decision == "approve")

    @property
    def rejection_count(self) -> int:
        return sum(1 for v in self.votes if v.decision == "reject")

    @property
    def is_approved(self) -> bool:
        return self.approval_count >= self.required_approvals

    @property
    def affected_files(self) -> List[str]:
        return [d.file_path for d in self.diffs]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stageId": self.stage_id,
            "authorSessionId": self.author_session_id,
            "authorName": self.author_name,
            "workspace": self.workspace,
            "description": self.description,
            "diffs": [d.to_dict() for d in self.diffs],
            "status": self.status.value,
            "votes": [v.to_dict() for v in self.votes],
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "approvalCount": self.approval_count,
            "rejectionCount": self.rejection_count,
            "requiredApprovals": self.required_approvals,
            "isApproved": self.is_approved,
            "affectedFiles": self.affected_files,
        }


class StagingArea:
    """In-memory store for staged changes.

    In production, this would be backed by a database.
    For now it serves as a fast, team-local staging area.
    """

    def __init__(self) -> None:
        self._stages: Dict[str, StagedChange] = {}

    def create(
        self,
        author_session_id: str,
        author_name: str,
        workspace: str,
        description: str,
        diffs: List[FileDiff],
        required_approvals: int = 1,
    ) -> StagedChange:
        """Create a new staged change."""
        stage = StagedChange(
            stage_id=str(uuid.uuid4()),
            author_session_id=author_session_id,
            author_name=author_name,
            workspace=workspace,
            description=description,
            diffs=diffs,
            required_approvals=required_approvals,
        )
        self._stages[stage.stage_id] = stage
        logger.info(
            "stage_created",
            stage_id=stage.stage_id,
            files=len(diffs),
            author=author_name,
        )
        return stage

    def get(self, stage_id: str) -> Optional[StagedChange]:
        """Retrieve a staged change by ID."""
        return self._stages.get(stage_id)

    def list_stages(
        self,
        workspace: Optional[str] = None,
        status: Optional[StageStatus] = None,
    ) -> List[StagedChange]:
        """List staged changes, optionally filtered."""
        results = []
        for stage in self._stages.values():
            if workspace and stage.workspace != workspace:
                continue
            if status and stage.status != status:
                continue
            results.append(stage)
        return sorted(results, key=lambda s: s.created_at, reverse=True)

    def vote(
        self,
        stage_id: str,
        reviewer_id: str,
        reviewer_name: str,
        decision: str,
        comment: str = "",
    ) -> Optional[StagedChange]:
        """Add a review vote to a staged change."""
        stage = self._stages.get(stage_id)
        if not stage or stage.status in (StageStatus.APPLIED, StageStatus.EXPIRED):
            return None

        # Prevent double-voting
        for v in stage.votes:
            if v.reviewer_id == reviewer_id:
                v.decision = decision
                v.comment = comment
                v.timestamp = time.time()
                stage.updated_at = time.time()
                self._update_status(stage)
                return stage

        stage.votes.append(ReviewVote(
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            decision=decision,
            comment=comment,
        ))
        stage.updated_at = time.time()
        self._update_status(stage)

        logger.info(
            "stage_voted",
            stage_id=stage_id,
            reviewer=reviewer_name,
            decision=decision,
        )
        return stage

    def mark_applied(self, stage_id: str) -> Optional[StagedChange]:
        """Mark a stage as applied to disk."""
        stage = self._stages.get(stage_id)
        if stage:
            stage.status = StageStatus.APPLIED
            stage.updated_at = time.time()
        return stage

    def delete(self, stage_id: str) -> bool:
        """Remove a staged change."""
        return self._stages.pop(stage_id, None) is not None

    def _update_status(self, stage: StagedChange) -> None:
        """Auto-update status based on votes."""
        if stage.is_approved:
            stage.status = StageStatus.APPROVED
        elif stage.rejection_count > 0:
            stage.status = StageStatus.REJECTED

    @property
    def count(self) -> int:
        return len(self._stages)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_staging: Optional[StagingArea] = None


def get_staging_area() -> StagingArea:
    """Return the global StagingArea singleton."""
    global _staging
    if _staging is None:
        _staging = StagingArea()
    return _staging
