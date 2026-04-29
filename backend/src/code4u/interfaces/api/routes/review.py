"""Synthetic Code Review API — AI-powered review without a real PR.

Analyzes proposed diffs or code changes and returns structured review
comments covering complexity, error handling, performance, and style.

Endpoints:
  - ``POST /review/synthetic``  — review proposed changes and return AI notes.
  - ``POST /review/scan``       — scan a single file for issues.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class SyntheticReviewRequest(BaseModel):
    diffs: Dict[str, str] = Field(default_factory=dict, description="file_path → unified diff")
    proposedCode: Dict[str, str] = Field(default_factory=dict, description="file_path → proposed file content")
    workspacePath: str = Field(".", description="Workspace root.")
    intent: str = Field("", description="The refactor intent for context.")


class FileScanRequest(BaseModel):
    filePath: str = Field(..., description="File path for context.")
    source: str = Field(..., description="Source code to review.")


class ReviewNote:
    """A single review observation."""

    def __init__(
        self,
        file_path: str,
        line: int,
        category: str,
        severity: str,
        message: str,
        suggestion: str = "",
    ):
        self.file_path = file_path
        self.line = line
        self.category = category
        self.severity = severity
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "line": self.line,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "suggestion": self.suggestion,
        }


def _analyze_code(source: str, file_path: str) -> List[ReviewNote]:
    """Run multi-dimensional analysis on source code."""
    import ast
    import re

    notes: List[ReviewNote] = []
    lines = source.splitlines()

    # --- Complexity analysis ---
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = _cyclomatic_complexity(node)
                if complexity > 10:
                    notes.append(ReviewNote(
                        file_path=file_path,
                        line=node.lineno,
                        category="High Complexity",
                        severity="warning",
                        message=f"Function '{node.name}' has cyclomatic complexity {complexity} (threshold: 10).",
                        suggestion=f"Consider extracting logic from '{node.name}' into smaller helper functions.",
                    ))

                nesting = _max_nesting_depth(node)
                if nesting > 4:
                    notes.append(ReviewNote(
                        file_path=file_path,
                        line=node.lineno,
                        category="Deep Nesting",
                        severity="warning",
                        message=f"Function '{node.name}' has nesting depth {nesting} (threshold: 4).",
                        suggestion="Use early returns or extract nested logic to reduce depth.",
                    ))

                body_lines = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno
                if body_lines > 50:
                    notes.append(ReviewNote(
                        file_path=file_path,
                        line=node.lineno,
                        category="Long Function",
                        severity="info",
                        message=f"Function '{node.name}' is {body_lines} lines long.",
                        suggestion="Consider splitting into smaller, focused functions.",
                    ))
    except SyntaxError:
        pass

    # --- Missing error handling ---
    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if re.search(r"\bexcept\s*:", stripped) and "pass" in stripped:
            notes.append(ReviewNote(
                file_path=file_path, line=i,
                category="Missing Error Handling",
                severity="warning",
                message="Bare except with pass — errors will be silently swallowed.",
                suggestion="Catch specific exceptions and log or handle them.",
            ))

        if re.search(r"\bexcept\s+Exception\s*:", stripped):
            notes.append(ReviewNote(
                file_path=file_path, line=i,
                category="Broad Exception",
                severity="info",
                message="Catching broad 'Exception' — may mask unexpected errors.",
                suggestion="Catch the most specific exception type possible.",
            ))

        if re.search(r"# ?TODO|# ?FIXME|# ?HACK|# ?XXX", stripped, re.IGNORECASE):
            notes.append(ReviewNote(
                file_path=file_path, line=i,
                category="Technical Debt",
                severity="info",
                message=f"TODO/FIXME marker found: {stripped[:80]}",
                suggestion="Address or track this TODO before merging.",
            ))

    # --- Performance patterns ---
    from code4u.agents.performance.optimizer import Optimizer
    optimizer = Optimizer()
    smells = optimizer.scan_source(source, file_path)
    for smell in smells:
        notes.append(ReviewNote(
            file_path=file_path,
            line=smell.line_number,
            category=f"Performance: {smell.category}",
            severity=smell.severity,
            message=smell.description,
            suggestion="",
        ))

    return notes


def _cyclomatic_complexity(node: Any) -> int:
    """Compute McCabe cyclomatic complexity for a function AST node."""
    import ast
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, (ast.Assert, ast.With)):
            complexity += 1
    return complexity


def _max_nesting_depth(node: Any, depth: int = 0) -> int:
    """Compute maximum nesting depth of control flow inside a function."""
    import ast
    max_depth = depth
    nesting_types = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)

    for child in ast.iter_child_nodes(node):
        if isinstance(child, nesting_types):
            child_depth = _max_nesting_depth(child, depth + 1)
            max_depth = max(max_depth, child_depth)
        else:
            child_depth = _max_nesting_depth(child, depth)
            max_depth = max(max_depth, child_depth)

    return max_depth


@router.post("/review/synthetic")
async def synthetic_review(request: SyntheticReviewRequest):
    """Run a synthetic code review on proposed changes.

    Analyzes each file in proposedCode for complexity, error handling,
    performance smells, and style issues. Returns structured review notes.
    """
    all_notes: List[Dict[str, Any]] = []
    files_reviewed = 0

    for file_path, content in request.proposedCode.items():
        if not content or not content.strip():
            continue

        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        if ext not in ("py", "ts", "tsx", "js", "jsx", "go", "rs"):
            continue

        files_reviewed += 1
        notes = _analyze_code(content, file_path)
        all_notes.extend(n.to_dict() for n in notes)

    severity_counts = {"error": 0, "warning": 0, "info": 0}
    for n in all_notes:
        sev = n.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    return {
        "notes": all_notes,
        "filesReviewed": files_reviewed,
        "totalNotes": len(all_notes),
        "severityCounts": severity_counts,
        "intent": request.intent,
    }


@router.post("/review/scan")
async def scan_file(request: FileScanRequest):
    """Scan a single file for code quality issues."""
    notes = _analyze_code(request.source, request.filePath)
    return {
        "notes": [n.to_dict() for n in notes],
        "totalNotes": len(notes),
        "filePath": request.filePath,
    }
