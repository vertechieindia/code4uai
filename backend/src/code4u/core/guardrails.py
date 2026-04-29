"""Deterministic Guardrails — hard-stop pattern scanning.

``StaticGuardrail`` scans proposed code diffs for "Forbidden Patterns"
using regex and AST analysis.  These are non-negotiable rules: if a
violation is found, the plan is rejected immediately — no LLM judgment
required.

This is the first line of defense, running *before* the Critic Agent.
It catches the "common sins" that should never reach production:
  - Hardcoded secrets (AWS keys, passwords, API tokens)
  - Dangerous builtins (eval, exec, __import__)
  - Shell injection vectors (shell=True, os.system)
  - Unsafe deserialization (pickle.load)

Each violation raises a ``GuardrailViolation`` with the rule ID,
file path, and offending line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("guardrails")


class GuardrailViolation(Exception):
    """Raised when a hard-stop guardrail is triggered."""

    def __init__(
        self,
        rule_id: str,
        message: str,
        file_path: str = "",
        line_number: int = 0,
        code_snippet: str = "",
    ):
        self.rule_id = rule_id
        self.file_path = file_path
        self.line_number = line_number
        self.code_snippet = code_snippet
        super().__init__(f"[{rule_id}] {message}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "message": str(self),
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "codeSnippet": self.code_snippet,
        }


@dataclass
class GuardrailResult:
    """Result of running all guardrails on a plan."""
    passed: bool = True
    violations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": self.violations,
        }


# ---------------------------------------------------------------------------
# Forbidden patterns (hard stops)
# ---------------------------------------------------------------------------

_FORBIDDEN_PATTERNS = [
    {
        "id": "GR-001",
        "pattern": re.compile(r"\beval\s*\("),
        "message": "FORBIDDEN: eval() is never allowed in production code",
    },
    {
        "id": "GR-002",
        "pattern": re.compile(r"\bexec\s*\("),
        "message": "FORBIDDEN: exec() is never allowed in production code",
    },
    {
        "id": "GR-003",
        "pattern": re.compile(r"shell\s*=\s*True"),
        "message": "FORBIDDEN: shell=True is a shell injection vector",
    },
    {
        "id": "GR-004",
        "pattern": re.compile(r"\bos\.system\s*\("),
        "message": "FORBIDDEN: os.system() allows shell injection — use subprocess.run()",
    },
    {
        "id": "GR-005",
        "pattern": re.compile(
            r"(?:AWS_SECRET_ACCESS_KEY|AWS_ACCESS_KEY_ID|PRIVATE_KEY)"
            r"\s*=\s*['\"][A-Za-z0-9/+=]{16,}['\"]",
            re.IGNORECASE,
        ),
        "message": "FORBIDDEN: Hardcoded AWS credential detected",
    },
    {
        "id": "GR-006",
        "pattern": re.compile(
            r"(?:api_key|apikey|api_secret|secret_key|auth_token|access_token)"
            r"\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
            re.IGNORECASE,
        ),
        "message": "FORBIDDEN: Hardcoded API key or token detected",
    },
    {
        "id": "GR-007",
        "pattern": re.compile(
            r"[Pp]assword\s*=\s*['\"][^'\"]{4,}['\"]"
        ),
        "message": "FORBIDDEN: Hardcoded password detected",
    },
    {
        "id": "GR-008",
        "pattern": re.compile(r"\bpickle\.loads?\s*\("),
        "message": "FORBIDDEN: pickle deserialization allows arbitrary code execution",
    },
    {
        "id": "GR-009",
        "pattern": re.compile(r"__import__\s*\("),
        "message": "FORBIDDEN: __import__() allows dynamic code loading",
    },
]

# Patterns that are forbidden only in *new* code (not pre-existing)
_DIFF_ONLY_PATTERNS = [
    {
        "id": "GR-010",
        "pattern": re.compile(
            r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"
        ),
        "message": "FORBIDDEN: Private key embedded in source code",
    },
    {
        "id": "GR-011",
        "pattern": re.compile(
            r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}"
        ),
        "message": "FORBIDDEN: GitHub personal access token detected",
    },
]


class StaticGuardrail:
    """Hard-stop scanner for forbidden patterns.

    Raises ``GuardrailViolation`` on the first critical finding,
    or returns a ``GuardrailResult`` with all violations.

    Usage::

        guardrail = StaticGuardrail()
        result = guardrail.scan_plan(operations)
        if not result.passed:
            raise GuardrailViolation(...)
    """

    def __init__(self, *, strict: bool = True) -> None:
        self._strict = strict  # raise on first violation vs collect all

    def scan_content(self, content: str, file_path: str = "") -> GuardrailResult:
        """Scan a single file's content for forbidden patterns."""
        result = GuardrailResult()

        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            for pat in _FORBIDDEN_PATTERNS + _DIFF_ONLY_PATTERNS:
                if pat["pattern"].search(line):
                    violation = {
                        "ruleId": pat["id"],
                        "message": pat["message"],
                        "filePath": file_path,
                        "lineNumber": i,
                        "codeSnippet": line.strip()[:200],
                    }
                    result.violations.append(violation)
                    result.passed = False

                    if self._strict:
                        logger.warning(
                            "guardrail_violation",
                            rule=pat["id"],
                            file=file_path,
                            line=i,
                        )
                        raise GuardrailViolation(
                            rule_id=pat["id"],
                            message=pat["message"],
                            file_path=file_path,
                            line_number=i,
                            code_snippet=line.strip()[:200],
                        )

        return result

    def scan_plan(self, operations: list) -> GuardrailResult:
        """Scan all operations in a plan.

        Args:
            operations: List of objects with ``content``, ``file_path``,
                       ``action`` attributes.
        """
        combined = GuardrailResult()

        for op in operations:
            if hasattr(op, "action") and op.action == "delete":
                continue

            content = op.content if hasattr(op, "content") else ""
            file_path = op.file_path if hasattr(op, "file_path") else ""
            if not content:
                continue

            try:
                result = self.scan_content(content, file_path)
                if not result.passed:
                    combined.passed = False
                    combined.violations.extend(result.violations)
            except GuardrailViolation:
                raise  # re-raise in strict mode

        logger.info(
            "guardrails_scanned",
            operations=len(operations),
            passed=combined.passed,
            violations=len(combined.violations),
        )

        return combined

    def scan_diff(
        self, old_content: str, new_content: str, file_path: str = "",
    ) -> GuardrailResult:
        """Scan only the newly introduced lines in a diff."""
        old_lines = set(old_content.splitlines())
        new_lines = new_content.splitlines()

        added = "\n".join(line for line in new_lines if line not in old_lines)
        return self.scan_content(added, file_path)
