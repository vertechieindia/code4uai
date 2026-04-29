"""Proposed plan for multi-file refactoring operations.

A ``ProposedPlan`` is a structured description of *every* filesystem
change the AI intends to make — edits, file creations, and deletions —
produced during the GENERATE_CODE phase *before* anything touches disk.

This enables:
  - Preview: show the user exactly what will happen.
  - Dry-run validation: ``ast.parse`` every proposed file in memory.
  - Atomic rollback: if any operation fails, undo everything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Intent types
# ---------------------------------------------------------------------------

INTENT_RENAME = "rename"
INTENT_EXTRACT = "extract"
INTENT_CONVERT_TO_CLASS = "convert_to_class"
INTENT_UI_LAYOUT = "ui_layout"
INTENT_OPTIMIZE = "optimize"
INTENT_UPGRADE_LIBRARY = "upgrade_library"
INTENT_DEPLOY = "deploy"
INTENT_GENERIC = "generic"


# ---------------------------------------------------------------------------
# FileOperation — one atomic change to one file
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileOperation:
    """A single proposed change to a file.

    Attributes:
        file_path: Absolute path to the file.
        action: One of ``"edit"``, ``"create"``, ``"delete"``.
        content: Proposed new content (full file). Empty string for delete.
        original_content: Content before the change. Empty string for create.
        reason: Human-readable explanation of why this change is needed.
    """
    file_path: str
    action: str
    content: str
    original_content: str
    reason: str

    def __post_init__(self) -> None:
        if self.action not in ("edit", "create", "delete"):
            raise ValueError(f"Invalid action: {self.action!r}")


# ---------------------------------------------------------------------------
# ProposedPlan — the full set of operations
# ---------------------------------------------------------------------------

@dataclass
class ProposedPlan:
    """Structured description of all changes before they are applied.

    Built during GENERATE_CODE and consumed by VALIDATE, PREVIEW_DIFF,
    and APPLY_DIFF.  The ``summary`` property produces a JSON-friendly
    overview suitable for API responses and logging.
    """
    intent: str
    intent_type: str
    operations: List[FileOperation] = field(default_factory=list)
    validation_passed: bool = False
    visual_reasoning_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def files_to_edit(self) -> List[str]:
        return [op.file_path for op in self.operations if op.action == "edit"]

    @property
    def files_to_create(self) -> List[str]:
        return [op.file_path for op in self.operations if op.action == "create"]

    @property
    def files_to_delete(self) -> List[str]:
        return [op.file_path for op in self.operations if op.action == "delete"]

    @property
    def all_files(self) -> List[str]:
        return [op.file_path for op in self.operations]

    @property
    def summary(self) -> Dict[str, Any]:
        result = {
            "intent": self.intent,
            "intentType": self.intent_type,
            "totalOperations": len(self.operations),
            "edits": len(self.files_to_edit),
            "creates": len(self.files_to_create),
            "deletes": len(self.files_to_delete),
            "validationPassed": self.validation_passed,
            "operations": [
                {
                    "path": op.file_path,
                    "action": op.action,
                    "reason": op.reason,
                }
                for op in self.operations
            ],
        }
        if self.visual_reasoning_metadata:
            result["visualReasoningMetadata"] = self.visual_reasoning_metadata
        return result
