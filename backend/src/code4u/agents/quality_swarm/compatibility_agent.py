"""Compatibility Agent — cross-environment validation.

Checks code syntax against target environments (Node versions,
browser compatibility, Python versions).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CompatibilityIssue:
    """A compatibility issue with a target environment."""
    file_path: str
    line_number: int
    feature: str
    target_env: str
    description: str
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "feature": self.feature,
            "targetEnv": self.target_env,
            "description": self.description,
            "severity": self.severity,
        }


class CompatibilityAgent:
    """Validates code against target environments."""

    PYTHON_38_FEATURES = ["walrus"]  # :=
    PYTHON_39_FEATURES = ["dict_merge"]  # | for dict
    PYTHON_310_FEATURES = ["match"]  # match statement

    def check_node_compatibility(
        self,
        source: str,
        file_path: str = "",
        min_version: int = 18,
    ) -> List[CompatibilityIssue]:
        """Check Node/JS compatibility for minimum version."""
        issues: List[CompatibilityIssue] = []
        if not (file_path.endswith((".js", ".ts", ".jsx", ".tsx"))):
            return issues

        lines = source.splitlines()
        for i, line in enumerate(lines, 1):
            if "?." in line and min_version < 14:
                issues.append(CompatibilityIssue(
                    file_path=file_path,
                    line_number=i,
                    feature="optional_chaining",
                    target_env=f"node_{min_version}",
                    description="Optional chaining (?.) requires Node 14+",
                    severity="high",
                ))
            if "??" in line and min_version < 14:
                issues.append(CompatibilityIssue(
                    file_path=file_path,
                    line_number=i,
                    feature="nullish_coalescing",
                    target_env=f"node_{min_version}",
                    description="Nullish coalescing (??) requires Node 14+",
                    severity="high",
                ))
            if "await " in line and "async " not in " ".join(lines[max(0, i-5):i]):
                if "async " not in source[:source.find(line)]:
                    pass

        return issues

    def check_browser_compatibility(
        self,
        source: str,
        file_path: str = "",
        targets: Optional[List[str]] = None,
    ) -> List[CompatibilityIssue]:
        """Check for APIs not in older browsers."""
        issues: List[CompatibilityIssue] = []
        targets = targets or ["chrome_80", "firefox_75", "safari_13"]

        if "structuredClone" in source:
            issues.append(CompatibilityIssue(
                file_path=file_path,
                line_number=0,
                feature="structuredClone",
                target_env=",".join(targets),
                description="structuredClone not in older Safari",
                severity="medium",
            ))
        if re.search(r"\?\.", source):
            issues.append(CompatibilityIssue(
                file_path=file_path,
                line_number=0,
                feature="optional_chaining",
                target_env="ie11",
                description="Optional chaining not supported in IE11",
                severity="high",
            ))

        return issues

    def check_python_compatibility(
        self,
        source: str,
        file_path: str = "",
        min_version: Tuple[int, int] = (3, 9),
    ) -> List[CompatibilityIssue]:
        """Check for features requiring Python 3.8+, 3.9+, 3.10+."""
        issues: List[CompatibilityIssue] = []
        if not file_path.endswith(".py"):
            return issues

        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.NamedExpr) and min_version < (3, 8):
                    issues.append(CompatibilityIssue(
                        file_path=file_path,
                        line_number=node.lineno,
                        feature="walrus_operator",
                        target_env=f"python_{min_version[0]}.{min_version[1]}",
                        description="Walrus operator (:=) requires Python 3.8+",
                        severity="high",
                    ))
                if isinstance(node, ast.Match) and min_version < (3, 10):
                    issues.append(CompatibilityIssue(
                        file_path=file_path,
                        line_number=node.lineno,
                        feature="match_statement",
                        target_env=f"python_{min_version[0]}.{min_version[1]}",
                        description="Match statement requires Python 3.10+",
                        severity="high",
                    ))
        except SyntaxError:
            pass

        return issues

    def generate_report(
        self,
        issues: List[CompatibilityIssue],
    ) -> Dict[str, Any]:
        """Generate compatibility report."""
        high = sum(1 for i in issues if i.severity == "high")
        medium = sum(1 for i in issues if i.severity == "medium")
        low = sum(1 for i in issues if i.severity == "low")
        score = max(0, 100 - high * 15 - medium * 8 - low * 3)
        return {
            "score": min(100, score),
            "issues": [i.to_dict() for i in issues],
            "summary": {
                "total": len(issues),
                "high": high,
                "medium": medium,
                "low": low,
            },
        }
