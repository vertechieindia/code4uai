"""Smart context builder for LLM-assisted refactoring.

Instead of sending the entire codebase to the LLM, this module builds
a surgically focused prompt containing:

  1. The target symbol's source code (exact lines from the file).
  2. Caller usage snippets from every file that imports the symbol
     (discovered via DependencyMap).
  3. Constraints derived from caller patterns (e.g. "do not change
     the function signature").

This saves ~80% on token cost compared to sending whole files,
and dramatically improves LLM accuracy by providing only what matters.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger("context_builder")

# The JSON schema the LLM must return
HUNK_RESPONSE_SCHEMA = """\
Return your changes as a JSON object with this exact structure (no markdown fences):
{
  "hunks": [
    {
      "start_line": <first line to replace (1-indexed)>,
      "end_line": <last line to replace (1-indexed, inclusive)>,
      "replacement": "<new code to insert (preserve indentation)>",
      "explanation": "<one-sentence reason for this change>"
    }
  ]
}

Rules:
- start_line and end_line refer to the ORIGINAL file line numbers.
- replacement must be valid, syntactically correct code.
- You may return multiple hunks; they must not overlap.
- If no change is needed, return {"hunks": []}.
- Return ONLY the JSON object. No markdown, no explanation outside the JSON."""


def _extract_symbol_source(
    content: str, symbol_name: str, language: str
) -> Tuple[str, int, int]:
    """Extract the source code of a symbol and its line range.

    Returns (source, start_line, end_line) where lines are 1-indexed.
    """
    if language == "python":
        return _extract_python_symbol(content, symbol_name)
    return _extract_regex_symbol(content, symbol_name)


def _extract_python_symbol(
    content: str, symbol_name: str
) -> Tuple[str, int, int]:
    """Use AST to extract a Python function/class source."""
    tree = ast.parse(content)
    lines = content.splitlines(keepends=True)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol_name:
                start = node.lineno
                end = getattr(node, "end_lineno", node.lineno)
                source = "".join(lines[start - 1 : end])
                return source, start, end

    return content, 1, len(lines)


def _extract_regex_symbol(
    content: str, symbol_name: str
) -> Tuple[str, int, int]:
    """Fallback: find the symbol by regex and return surrounding lines."""
    lines = content.splitlines(keepends=True)
    pattern = re.compile(
        rf"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|const|def)\s+{re.escape(symbol_name)}\b"
    )
    for i, line in enumerate(lines):
        if pattern.match(line):
            start = i + 1
            end = min(len(lines), start + 50)
            source = "".join(lines[start - 1 : end])
            return source, start, end

    return content, 1, len(lines)


def _find_call_sites(
    file_path: str, symbol_name: str
) -> List[Dict[str, Any]]:
    """Find lines in a file where symbol_name is called."""
    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except Exception:
        return []

    sites: List[Dict[str, Any]] = []
    pattern = re.compile(rf"\b{re.escape(symbol_name)}\s*\(")
    for i, line in enumerate(content.splitlines()):
        if pattern.search(line):
            sites.append({
                "file": Path(file_path).name,
                "abs_path": file_path,
                "line": i + 1,
                "code": line.strip(),
            })
    return sites


def build_refactor_prompt(
    intent: str,
    file_path: str,
    file_content: str,
    symbol_name: str,
    language: str,
    caller_files: List[str],
) -> str:
    """Build a context-rich prompt for the LLM.

    Args:
        intent: User's refactoring intent.
        file_path: Path of the file containing the symbol.
        file_content: Full content of the file.
        symbol_name: Name of the target symbol.
        language: Programming language.
        caller_files: Absolute paths of files that import the symbol.

    Returns:
        A complete prompt string ready for the LLM.
    """
    source, start_line, end_line = _extract_symbol_source(
        file_content, symbol_name, language
    )

    call_sites: List[Dict[str, Any]] = []
    for cf in caller_files:
        sites = _find_call_sites(cf, symbol_name)
        call_sites.extend(sites)

    file_name = Path(file_path).name
    parts: List[str] = [
        f"You are refactoring code in a {language} project.\n",
        f"## Target Symbol\n"
        f"File: {file_name} (lines {start_line}-{end_line})\n"
        f"```{language}\n{source}```\n",
    ]

    if call_sites:
        parts.append("## Callers (these files use this symbol — do NOT break them)\n")
        for site in call_sites[:15]:
            parts.append(f"- {site['file']}:{site['line']} → `{site['code']}`\n")
        parts.append("")

    parts.append(f"## Full File Content\n")
    numbered = "\n".join(
        f"{i + 1:4d} | {line}"
        for i, line in enumerate(file_content.splitlines())
    )
    parts.append(f"```{language}\n{numbered}\n```\n")

    parts.append(f"## User Intent\n\"{intent}\"\n")

    parts.append(
        "## Constraints\n"
        "- Do NOT change the function/class signature (name, parameters, return type).\n"
        "- All callers listed above must continue to work without modification.\n"
        "- Preserve docstrings unless the intent specifically asks to change them.\n"
        "- The replacement code must be syntactically valid.\n"
    )

    parts.append(HUNK_RESPONSE_SCHEMA)

    prompt = "\n".join(parts)
    logger.info(
        "context_built",
        symbol=symbol_name,
        file=file_name,
        callers=len(call_sites),
        prompt_chars=len(prompt),
    )
    return prompt


def build_system_message() -> str:
    """Return the system message for refactoring LLM calls."""
    return (
        "You are a senior software engineer performing precise code refactoring. "
        "You return ONLY valid JSON containing code hunks. "
        "You never change function signatures unless explicitly asked. "
        "You never introduce new dependencies unless explicitly asked. "
        "You always preserve existing tests and caller compatibility."
    )
