"""Critic Agent — security and complexity red-teamer.

The Critic never writes code.  It only reviews ``ProposedPlan``
operations and produces a ``CriticReview`` containing:

  - A quality score (1-10).
  - A list of ``Violation`` entries, each classified by severity
    (``critical``, ``high``, ``medium``, ``low``, ``info``).

Focus areas (OWASP Top 10 + complexity):
  - Security: SQLi, XSS, hardcoded secrets, shell injection, eval/exec,
    unsafe deserialization, path traversal.
  - Complexity: nested loops (N+1), excessive function length,
    deep nesting, high cyclomatic complexity indicators.
  - Best practices: bare except, mutable default args, unused variables.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("critic")


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Category(str, Enum):
    SECURITY = "security"
    COMPLEXITY = "complexity"
    BEST_PRACTICE = "best_practice"
    PERFORMANCE = "performance"


@dataclass
class Violation:
    """A single issue found by the Critic."""
    rule_id: str
    message: str
    severity: Severity
    category: Category
    file_path: str = ""
    line_number: int = 0
    code_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "codeSnippet": self.code_snippet,
        }


@dataclass
class CriticReview:
    """The Critic's verdict on a proposed change."""
    score: int  # 1-10
    violations: List[Violation] = field(default_factory=list)
    summary: str = ""
    passed: bool = True

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.HIGH)

    @property
    def security_violations(self) -> List[Violation]:
        return [v for v in self.violations if v.category == Category.SECURITY]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "summary": self.summary,
            "criticalCount": self.critical_count,
            "highCount": self.high_count,
            "violations": [v.to_dict() for v in self.violations],
        }


# ---------------------------------------------------------------------------
# Security patterns
# ---------------------------------------------------------------------------

_SECURITY_PATTERNS = [
    {
        "id": "SEC-001",
        "pattern": re.compile(r"\beval\s*\(", re.IGNORECASE),
        "message": "Use of eval() is dangerous — allows arbitrary code execution",
        "severity": Severity.CRITICAL,
    },
    {
        "id": "SEC-002",
        "pattern": re.compile(r"\bexec\s*\(", re.IGNORECASE),
        "message": "Use of exec() is dangerous — allows arbitrary code execution",
        "severity": Severity.CRITICAL,
    },
    {
        "id": "SEC-003",
        "pattern": re.compile(r"shell\s*=\s*True"),
        "message": "subprocess with shell=True is a shell injection risk",
        "severity": Severity.CRITICAL,
    },
    {
        "id": "SEC-004",
        "pattern": re.compile(
            r"(?:AWS_SECRET|AWS_ACCESS_KEY|PRIVATE_KEY|api_key|apikey|secret_key|password)"
            r"\s*=\s*['\"][^'\"]{8,}['\"]",
            re.IGNORECASE,
        ),
        "message": "Hardcoded secret or API key detected",
        "severity": Severity.CRITICAL,
    },
    {
        "id": "SEC-005",
        "pattern": re.compile(r"Password\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
        "message": "Hardcoded password detected",
        "severity": Severity.CRITICAL,
    },
    {
        "id": "SEC-006",
        "pattern": re.compile(r"\bpickle\.loads?\s*\("),
        "message": "Unsafe deserialization with pickle — arbitrary code execution risk",
        "severity": Severity.HIGH,
    },
    {
        "id": "SEC-007",
        "pattern": re.compile(r"\.format\s*\(.*\bsql\b", re.IGNORECASE),
        "message": "String formatting in SQL query — SQL injection risk",
        "severity": Severity.HIGH,
    },
    {
        "id": "SEC-008",
        "pattern": re.compile(r"""f['"].*\{.*\}.*(?:SELECT|INSERT|UPDATE|DELETE|DROP)""", re.IGNORECASE),
        "message": "F-string in SQL query — SQL injection risk",
        "severity": Severity.HIGH,
    },
    {
        "id": "SEC-008b",
        "pattern": re.compile(r"""f['"](?:SELECT|INSERT|UPDATE|DELETE|DROP)\s""", re.IGNORECASE),
        "message": "F-string in SQL query — SQL injection risk",
        "severity": Severity.HIGH,
    },
    {
        "id": "SEC-009",
        "pattern": re.compile(r"innerHTML\s*="),
        "message": "Direct innerHTML assignment — XSS risk",
        "severity": Severity.HIGH,
    },
    {
        "id": "SEC-010",
        "pattern": re.compile(r"dangerouslySetInnerHTML"),
        "message": "dangerouslySetInnerHTML usage — XSS risk",
        "severity": Severity.MEDIUM,
    },
    {
        "id": "SEC-011",
        "pattern": re.compile(r"os\.system\s*\("),
        "message": "os.system() is a shell injection risk — use subprocess instead",
        "severity": Severity.HIGH,
    },
    {
        "id": "SEC-012",
        "pattern": re.compile(r"__import__\s*\("),
        "message": "Dynamic import via __import__() — potential code injection",
        "severity": Severity.MEDIUM,
    },
    {
        "id": "SEC-013",
        "pattern": re.compile(r"yaml\.load\s*\([^)]*\)(?!.*Loader)"),
        "message": "yaml.load() without SafeLoader — arbitrary code execution risk",
        "severity": Severity.HIGH,
    },
]

# ---------------------------------------------------------------------------
# Complexity patterns
# ---------------------------------------------------------------------------

_COMPLEXITY_PATTERNS = [
    {
        "id": "PERF-001",
        "pattern": re.compile(r"for\s+\w+\s+in\s+.*:\s*\n\s+for\s+\w+\s+in\s+"),
        "message": "Nested loop detected — consider using a dict/set lookup for O(1) access",
        "severity": Severity.MEDIUM,
        "category": Category.PERFORMANCE,
    },
    {
        "id": "PERF-002",
        "pattern": re.compile(r"time\.sleep\s*\(\s*\d{2,}"),
        "message": "Long sleep detected — consider async/event-driven approach",
        "severity": Severity.LOW,
        "category": Category.PERFORMANCE,
    },
]

_PRACTICE_PATTERNS = [
    {
        "id": "BP-001",
        "pattern": re.compile(r"except\s*:"),
        "message": "Bare except clause — catches all exceptions including SystemExit/KeyboardInterrupt",
        "severity": Severity.MEDIUM,
        "category": Category.BEST_PRACTICE,
    },
    {
        "id": "BP-002",
        "pattern": re.compile(r"def\s+\w+\s*\([^)]*=\s*\[\s*\]"),
        "message": "Mutable default argument (list) — shared across calls",
        "severity": Severity.MEDIUM,
        "category": Category.BEST_PRACTICE,
    },
    {
        "id": "BP-003",
        "pattern": re.compile(r"def\s+\w+\s*\([^)]*=\s*\{\s*\}"),
        "message": "Mutable default argument (dict) — shared across calls",
        "severity": Severity.MEDIUM,
        "category": Category.BEST_PRACTICE,
    },
]


# ---------------------------------------------------------------------------
# CriticAgent
# ---------------------------------------------------------------------------

class CriticAgent:
    """Deterministic + heuristic code reviewer.

    Scans proposed file changes for security vulnerabilities,
    performance smells, and best-practice violations.
    """

    def __init__(self, threshold: int = 7) -> None:
        self._threshold = threshold

    def review_content(self, content: str, file_path: str = "") -> CriticReview:
        """Review a single file's content."""
        violations: List[Violation] = []

        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            # Security patterns
            for pat in _SECURITY_PATTERNS:
                if pat["pattern"].search(line):
                    violations.append(Violation(
                        rule_id=pat["id"],
                        message=pat["message"],
                        severity=pat["severity"],
                        category=Category.SECURITY,
                        file_path=file_path,
                        line_number=i,
                        code_snippet=line.strip(),
                    ))

            # Best-practice patterns
            for pat in _PRACTICE_PATTERNS:
                if pat["pattern"].search(line):
                    violations.append(Violation(
                        rule_id=pat["id"],
                        message=pat["message"],
                        severity=pat["severity"],
                        category=pat["category"],
                        file_path=file_path,
                        line_number=i,
                        code_snippet=line.strip(),
                    ))

        # Multi-line patterns (complexity)
        for pat in _COMPLEXITY_PATTERNS:
            for m in pat["pattern"].finditer(content):
                line_num = content[:m.start()].count("\n") + 1
                violations.append(Violation(
                    rule_id=pat["id"],
                    message=pat["message"],
                    severity=pat["severity"],
                    category=pat.get("category", Category.PERFORMANCE),
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet=m.group(0).strip()[:120],
                ))

        # AST-based checks for Python files
        if file_path.endswith(".py"):
            violations.extend(self._ast_checks(content, file_path))

        score = self._calculate_score(violations)
        passed = score >= self._threshold

        review = CriticReview(
            score=score,
            violations=violations,
            passed=passed,
            summary=self._build_summary(score, violations),
        )

        logger.info(
            "critic_review",
            file=file_path,
            score=score,
            violations=len(violations),
            passed=passed,
        )

        return review

    def review_plan(self, operations: list) -> CriticReview:
        """Review all operations in a ProposedPlan.

        Args:
            operations: List of FileOperation-like objects with
                       ``content``, ``file_path``, and ``action`` attrs.
        """
        all_violations: List[Violation] = []

        for op in operations:
            if hasattr(op, "action") and op.action == "delete":
                continue
            content = op.content if hasattr(op, "content") else ""
            file_path = op.file_path if hasattr(op, "file_path") else ""
            if content:
                review = self.review_content(content, file_path)
                all_violations.extend(review.violations)

        score = self._calculate_score(all_violations)
        passed = score >= self._threshold

        return CriticReview(
            score=score,
            violations=all_violations,
            passed=passed,
            summary=self._build_summary(score, all_violations),
        )

    def review_diff(self, old_content: str, new_content: str, file_path: str = "") -> CriticReview:
        """Review only the newly introduced code (diff-aware)."""
        old_lines = set(old_content.splitlines())
        new_lines = new_content.splitlines()

        added_content = "\n".join(
            line for line in new_lines if line not in old_lines
        )
        return self.review_content(added_content, file_path)

    # -- AST checks ----------------------------------------------------------

    def _ast_checks(self, content: str, file_path: str) -> List[Violation]:
        """AST-based quality checks for Python."""
        violations: List[Violation] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            # Function length check
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, "end_lineno", None)
                if end and (end - node.lineno) > 50:
                    violations.append(Violation(
                        rule_id="CX-001",
                        message=f"Function '{node.name}' is {end - node.lineno} lines — consider splitting",
                        severity=Severity.LOW,
                        category=Category.COMPLEXITY,
                        file_path=file_path,
                        line_number=node.lineno,
                    ))

                # Deep nesting check
                max_depth = self._max_nesting(node)
                if max_depth > 4:
                    violations.append(Violation(
                        rule_id="CX-002",
                        message=f"Function '{node.name}' has nesting depth {max_depth} — consider early returns",
                        severity=Severity.MEDIUM,
                        category=Category.COMPLEXITY,
                        file_path=file_path,
                        line_number=node.lineno,
                    ))

        return violations

    def _max_nesting(self, node: ast.AST, depth: int = 0) -> int:
        """Calculate maximum nesting depth of control flow."""
        max_d = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With,
                                   ast.Try, ast.ExceptHandler)):
                max_d = max(max_d, self._max_nesting(child, depth + 1))
            else:
                max_d = max(max_d, self._max_nesting(child, depth))
        return max_d

    # -- Scoring -------------------------------------------------------------

    def _calculate_score(self, violations: List[Violation]) -> int:
        """Calculate quality score (1-10) based on violations."""
        if not violations:
            return 10

        penalty = 0
        for v in violations:
            if v.severity == Severity.CRITICAL:
                penalty += 4
            elif v.severity == Severity.HIGH:
                penalty += 2
            elif v.severity == Severity.MEDIUM:
                penalty += 1
            elif v.severity == Severity.LOW:
                penalty += 0.5

        score = max(1, 10 - int(penalty))
        return score

    def _build_summary(self, score: int, violations: List[Violation]) -> str:
        if not violations:
            return "Clean review — no issues found."

        parts = [f"Score: {score}/10."]
        sec = [v for v in violations if v.category == Category.SECURITY]
        if sec:
            parts.append(f"{len(sec)} security issue(s).")
        cx = [v for v in violations if v.category in (Category.COMPLEXITY, Category.PERFORMANCE)]
        if cx:
            parts.append(f"{len(cx)} complexity/performance issue(s).")
        bp = [v for v in violations if v.category == Category.BEST_PRACTICE]
        if bp:
            parts.append(f"{len(bp)} best-practice issue(s).")
        return " ".join(parts)
