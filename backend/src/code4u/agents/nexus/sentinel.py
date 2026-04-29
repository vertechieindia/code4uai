"""Drift Sentinel — architectural immune system.

Background agent that scans code changes against the ``GlobalRegistry``
and ``RuleRegistry`` to detect structural violations *before* they land.

The Sentinel operates at two granularities:

  1. **Full scan** — checks every file in a DependencyMap against all rules.
  2. **Delta scan** — checks only changed files (from a diff or watcher event),
     which is the hot path for real-time IDE/TUI feedback.

It also generates remediation suggestions via ``suggest_fix()`` so the
HealAgent or developer can correct violations instantly.

Usage::

    sentinel = Sentinel(rule_registry, dep_map)
    violations = sentinel.scan_file("routes/users.py")
    violations = sentinel.scan_delta(["routes/users.py"])
    fix = sentinel.suggest_fix(violations[0])
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import structlog

from code4u.agents.nexus.rules import (
    ArchitecturalRule,
    ForbiddenImport,
    NamingConvention,
    RequiredDecorator,
    RuleRegistry,
    Violation,
)
from code4u.code_intelligence.knowledge_graph.symbol_indexer import DependencyMap

logger = structlog.get_logger("sentinel")


# ---------------------------------------------------------------------------
# Scan result
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    """Aggregated result of a Sentinel scan."""
    violations: List[Violation] = field(default_factory=list)
    files_scanned: int = 0
    rules_checked: int = 0
    duration_ms: float = 0.0
    clean: bool = True

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity in ("error", "critical"))

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violations": [v.to_dict() for v in self.violations],
            "filesScanned": self.files_scanned,
            "rulesChecked": self.rules_checked,
            "durationMs": round(self.duration_ms, 1),
            "clean": self.clean,
            "errorCount": self.error_count,
            "warningCount": self.warning_count,
        }


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------

class Sentinel:
    """Architectural drift detector.

    Checks code against a ``RuleRegistry`` using symbol and import
    data from a ``DependencyMap``.
    """

    def __init__(
        self,
        rules: RuleRegistry,
        dep_map: Optional[DependencyMap] = None,
        *,
        on_violation: Optional[Callable[[Violation], None]] = None,
    ) -> None:
        self._rules = rules
        self._dep_map = dep_map
        self._on_violation = on_violation

    @property
    def rule_count(self) -> int:
        return len(self._rules.all())

    def set_dep_map(self, dep_map: DependencyMap) -> None:
        self._dep_map = dep_map

    # -- Scanning ------------------------------------------------------------

    def scan_full(self) -> ScanResult:
        """Scan all files in the DependencyMap against all rules."""
        if not self._dep_map:
            return ScanResult()

        t0 = time.time()
        result = ScanResult()
        rules = self._rules.all()
        result.rules_checked = len(rules)

        for file_path in self._dep_map.all_files:
            file_violations = self._check_file(file_path, rules)
            result.violations.extend(file_violations)
            result.files_scanned += 1

        result.clean = len(result.violations) == 0
        result.duration_ms = (time.time() - t0) * 1000

        logger.info(
            "sentinel_full_scan",
            files=result.files_scanned,
            violations=len(result.violations),
            duration_ms=round(result.duration_ms, 1),
        )
        return result

    def scan_delta(self, changed_files: List[str]) -> ScanResult:
        """Scan only the changed files (hot path for real-time feedback)."""
        t0 = time.time()
        result = ScanResult()
        rules = self._rules.all()
        result.rules_checked = len(rules)

        for file_path in changed_files:
            file_violations = self._check_file(file_path, rules)
            result.violations.extend(file_violations)
            result.files_scanned += 1

        result.clean = len(result.violations) == 0
        result.duration_ms = (time.time() - t0) * 1000

        if result.violations:
            logger.warning(
                "sentinel_drift_detected",
                files=changed_files,
                violations=len(result.violations),
            )

        return result

    def scan_file(self, file_path: str) -> List[Violation]:
        """Scan a single file against all applicable rules."""
        rules = self._rules.all()
        return self._check_file(file_path, rules)

    def suggest_fix(self, violation: Violation) -> Dict[str, Any]:
        """Generate a remediation suggestion for a violation."""
        fix: Dict[str, Any] = {
            "violation": violation.to_dict(),
            "action": "manual_review",
            "description": "",
            "automatable": False,
        }

        if violation.suggestion:
            fix["description"] = violation.suggestion
            fix["automatable"] = True

        rule = self._rules.get(violation.rule_id)
        if not rule:
            return fix

        # Forbidden import → suggest using the approved abstraction
        for fi in rule.forbidden_imports:
            if fi.matches_module(violation.symbol_name or violation.message):
                fix["action"] = "replace_import"
                fix["description"] = fi.reason or f"Remove forbidden import matching '{fi.module_pattern}'"
                fix["automatable"] = True
                fix["heal_intent"] = (
                    f"Remove the import of '{violation.symbol_name}' from "
                    f"'{violation.file_path}' and replace with an approved abstraction. "
                    f"Reason: {fi.reason}"
                )
                break

        # Naming convention → suggest renaming
        for nc in rule.naming_conventions:
            if not nc.matches(violation.symbol_name or ""):
                fix["action"] = "rename_symbol"
                fix["description"] = nc.reason or f"Rename to match pattern: {nc.pattern}"
                fix["automatable"] = True
                fix["heal_intent"] = (
                    f"Rename '{violation.symbol_name}' in '{violation.file_path}' "
                    f"to follow the pattern '{nc.pattern}'. {nc.reason}"
                )
                break

        return fix

    # -- Internal checks -----------------------------------------------------

    def _check_file(
        self, file_path: str, rules: List[ArchitecturalRule]
    ) -> List[Violation]:
        """Run all rules against a single file."""
        violations: List[Violation] = []
        fname = Path(file_path).name

        for rule in rules:
            violations.extend(self._check_forbidden_imports(rule, file_path, fname))
            violations.extend(self._check_naming_conventions(rule, file_path, fname))

        for v in violations:
            if self._on_violation:
                self._on_violation(v)

        return violations

    def _check_forbidden_imports(
        self,
        rule: ArchitecturalRule,
        file_path: str,
        fname: str,
    ) -> List[Violation]:
        """Check forbidden import rules."""
        violations = []
        if not self._dep_map:
            return violations

        for fi in rule.forbidden_imports:
            if not (fnmatch(fname, fi.file_glob) or fnmatch(file_path, fi.file_glob)):
                continue

            for imp in self._dep_map.get_file_imports(file_path):
                if fi.matches_module(imp.module):
                    violations.append(Violation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        severity=rule.severity,
                        file_path=file_path,
                        line=imp.line,
                        message=f"Forbidden import '{imp.module}' in {fname}",
                        symbol_name=imp.module,
                        suggestion=fi.reason,
                    ))

        return violations

    def _check_naming_conventions(
        self,
        rule: ArchitecturalRule,
        file_path: str,
        fname: str,
    ) -> List[Violation]:
        """Check naming convention rules."""
        violations = []
        if not self._dep_map:
            return violations

        for nc in rule.naming_conventions:
            if not (fnmatch(fname, nc.file_glob) or fnmatch(file_path, nc.file_glob)):
                continue

            for sym in self._dep_map.get_file_symbols(file_path):
                if nc.symbol_type == "function" and sym.kind != "function":
                    continue
                if nc.symbol_type == "class" and sym.kind != "class":
                    continue

                if not nc.matches(sym.name):
                    violations.append(Violation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        severity=rule.severity,
                        file_path=file_path,
                        line=sym.start_line,
                        message=f"Symbol '{sym.name}' violates naming convention: {nc.pattern}",
                        symbol_name=sym.name,
                        suggestion=nc.reason or f"Rename to match pattern: {nc.pattern}",
                    ))

        return violations
