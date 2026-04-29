from __future__ import annotations
"""Protocol message definitions for IDE ↔ Backend communication.

All messages have strict schemas.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


# ============================================================
# IDE → Backend Messages
# ============================================================

class CursorContext(BaseModel):
    """Cursor position context from IDE."""
    file: str
    line: int
    column: int = 0
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None
    selection_text: Optional[str] = None


class IntentRequest(BaseModel):
    """
    Intent request from IDE.
    
    Example:
    {
      "intent": "refactor",
      "cursor": {
        "file": "UserProfile.tsx",
        "line": 42
      },
      "selection": "user.email",
      "workspace_id": "tenant-123"
    }
    """
    intent: Literal["refactor", "add_api", "fix_bug", "explain", "rename", "extract"]
    cursor: CursorContext
    selection: str = ""
    instruction: str = ""
    workspace_id: str
    user_id: str = ""
    
    # Options
    preview_only: bool = True  # Always preview first
    include_tests: bool = False


class ApplyRequest(BaseModel):
    """Request to apply a diff."""
    execution_id: str
    workspace_id: str
    user_id: str
    
    # Optional: apply specific diffs only
    diff_ids: List[str] | None = None


class RejectRequest(BaseModel):
    """Request to reject a diff."""
    execution_id: str
    workspace_id: str
    user_id: str
    reason: str = ""


# ============================================================
# Backend → IDE Messages
# ============================================================

class ImpactedComponent(BaseModel):
    """Component impacted by a change."""
    name: str
    type: str  # file, module, service, schema
    path: str
    owner: Optional[str] = None
    breaking: bool = False


class ValidationResult(BaseModel):
    """Validation result for a diff."""
    types: Literal["pass", "fail", "pending"] = "pending"
    schemas: Literal["pass", "fail", "pending"] = "pending"
    tests: Literal["pass", "fail", "pending", "skipped"] = "pending"
    ownership: Literal["pass", "warning", "fail"] = "pass"


class DiffItem(BaseModel):
    """A single diff in a payload."""
    diff_id: str
    file_path: str
    diff_content: str
    language: str = "typescript"
    
    # Metadata
    lines_added: int = 0
    lines_removed: int = 0
    
    # Validation
    is_breaking: bool = False
    owner: Optional[str] = None


class ExecutionUpdate(BaseModel):
    """
    Streaming update from backend.
    
    Example:
    {
      "state": "PLAN_GENERATED",
      "summary": "Renaming email → primaryEmail",
      "impacted_components": ["UserSchema", "ProfileUI"],
      "breaking_change": true
    }
    """
    execution_id: str
    state: str
    summary: str = ""
    impacted_components: list[ImpactedComponent] = Field(default_factory=list)
    breaking_change: bool = False
    
    # Progress
    phase: str = ""
    progress: int = 0  # 0-100
    
    # Timing
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class DiffPayload(BaseModel):
    """
    Diff payload for review.
    
    Example:
    {
      "state": "READY_FOR_REVIEW",
      "diffs": [...],
      "validation": {
        "types": "pass",
        "schemas": "pass"
      }
    }
    """
    execution_id: str
    state: Literal["READY_FOR_REVIEW"] = "READY_FOR_REVIEW"
    diffs: list[DiffItem] = Field(default_factory=list)
    validation: ValidationResult = Field(default_factory=ValidationResult)
    
    # Summary
    summary: str = ""
    total_files: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0
    
    # Warnings
    breaking_changes: List[str] = Field(default_factory=list)
    ownership_warnings: List[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Error response."""
    execution_id: Optional[str] = None
    error: str
    error_code: str = "UNKNOWN_ERROR"
    details: Dict[str, Any] | None = None
    recoverable: bool = False


# ============================================================
# WebSocket Message Envelope
# ============================================================

class WebSocketMessage(BaseModel):
    """WebSocket message envelope."""
    type: Literal[
        "intent_request",
        "execution_update",
        "diff_payload",
        "apply_request",
        "reject_request",
        "error",
        "ping",
        "pong",
    ]
    payload: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    request_id: Optional[str] = None

