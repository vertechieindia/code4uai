"""Hunk parser and merger for LLM-generated code edits.

Instead of letting the LLM rewrite entire files, we instruct it to
return specific "hunks" — line ranges with replacement code.  This
module parses that JSON response and merges the hunks into the
original file content.

Advantages:
  - Smaller LLM output → fewer tokens → lower cost.
  - Merge-in-memory before validation → bad hunks never touch disk.
  - Each hunk carries an ``explanation`` for the UI to display.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("hunk_parser")


@dataclass(frozen=True)
class Hunk:
    """A single code replacement block."""
    start_line: int
    end_line: int
    replacement: str
    explanation: str


@dataclass
class HunkResult:
    """Result of parsing and merging hunks."""
    success: bool
    merged_content: str
    hunks: List[Hunk]
    error: Optional[str] = None


def parse_hunks(llm_response: str) -> List[Hunk]:
    """Parse the LLM JSON response into a list of Hunk objects.

    Handles:
      - Raw JSON responses.
      - JSON wrapped in ```json ... ``` code fences.
      - Responses with extra text before/after the JSON.

    Raises ValueError if the response cannot be parsed.
    """
    text = llm_response.strip()

    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()

    if not text.startswith("{"):
        brace_start = text.find("{")
        if brace_start >= 0:
            text = text[brace_start:]
        else:
            raise ValueError("No JSON object found in LLM response")

    brace_end = text.rfind("}")
    if brace_end >= 0:
        text = text[: brace_end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in LLM response: {e}") from e

    if not isinstance(data, dict) or "hunks" not in data:
        raise ValueError("LLM response missing 'hunks' key")

    raw_hunks = data["hunks"]
    if not isinstance(raw_hunks, list):
        raise ValueError("'hunks' must be a list")

    hunks: List[Hunk] = []
    for i, h in enumerate(raw_hunks):
        if not isinstance(h, dict):
            raise ValueError(f"Hunk {i} is not an object")
        try:
            hunks.append(Hunk(
                start_line=int(h["start_line"]),
                end_line=int(h["end_line"]),
                replacement=str(h["replacement"]),
                explanation=str(h.get("explanation", "")),
            ))
        except (KeyError, TypeError) as e:
            raise ValueError(f"Hunk {i} missing required field: {e}") from e

    hunks.sort(key=lambda h: h.start_line)

    for i in range(len(hunks) - 1):
        if hunks[i].end_line >= hunks[i + 1].start_line:
            raise ValueError(
                f"Overlapping hunks: hunk {i} ends at line {hunks[i].end_line}, "
                f"hunk {i+1} starts at line {hunks[i+1].start_line}"
            )

    return hunks


def apply_hunks(original_content: str, hunks: List[Hunk]) -> str:
    """Merge hunks into the original file content.

    Hunks are applied in reverse order (bottom-up) so that line
    numbers remain valid as earlier lines are replaced.

    Args:
        original_content: The full original file as a string.
        hunks: Sorted list of non-overlapping hunks.

    Returns:
        The merged file content.
    """
    if not hunks:
        return original_content

    lines = original_content.splitlines(keepends=True)

    for hunk in reversed(hunks):
        start_idx = hunk.start_line - 1
        end_idx = hunk.end_line

        if start_idx < 0:
            start_idx = 0
        if end_idx > len(lines):
            end_idx = len(lines)

        replacement_text = hunk.replacement
        if not replacement_text.endswith("\n"):
            replacement_text += "\n"
        replacement_lines = replacement_text.splitlines(keepends=True)

        lines[start_idx:end_idx] = replacement_lines

    return "".join(lines)


def parse_and_apply(
    llm_response: str, original_content: str
) -> HunkResult:
    """Parse LLM response and merge hunks into the original file.

    Returns a ``HunkResult`` with ``success=True`` and the merged
    content, or ``success=False`` with the parse error.
    """
    try:
        hunks = parse_hunks(llm_response)
    except ValueError as e:
        logger.warning("hunk_parse_failed", error=str(e))
        return HunkResult(
            success=False,
            merged_content=original_content,
            hunks=[],
            error=str(e),
        )

    if not hunks:
        return HunkResult(
            success=True,
            merged_content=original_content,
            hunks=[],
        )

    merged = apply_hunks(original_content, hunks)

    logger.info(
        "hunks_applied",
        hunk_count=len(hunks),
        original_lines=len(original_content.splitlines()),
        merged_lines=len(merged.splitlines()),
    )

    return HunkResult(
        success=True,
        merged_content=merged,
        hunks=hunks,
    )
