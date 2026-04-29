"""Performance Agent — runtime regression detector.

Analyzes profiling data and code structure to detect performance
regressions. Rejects code if hot function execution time increases
by more than 5%.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PerformanceIssue:
    """A performance regression or concern."""
    file_path: str
    function_name: str
    metric: str
    old_value: float
    new_value: float
    threshold: float
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "functionName": self.function_name,
            "metric": self.metric,
            "oldValue": self.old_value,
            "newValue": self.new_value,
            "threshold": self.threshold,
            "severity": self.severity,
        }


class PerformanceAgent:
    """Analyzes code complexity and profile data for regressions."""

    MAX_FUNCTION_LINES = 100
    MAX_NESTING_DEPTH = 5

    def analyze_code_complexity(
        self,
        source: str,
        file_path: str = "",
    ) -> List[PerformanceIssue]:
        """Analyze function length, nesting depth, cyclomatic complexity."""
        issues: List[PerformanceIssue] = []

        if file_path.endswith(".py"):
            try:
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        start = node.lineno
                        end = node.end_lineno or start
                        lines = end - start + 1
                        if lines > self.MAX_FUNCTION_LINES:
                            issues.append(PerformanceIssue(
                                file_path=file_path,
                                function_name=node.name,
                                metric="function_lines",
                                old_value=self.MAX_FUNCTION_LINES,
                                new_value=float(lines),
                                threshold=float(self.MAX_FUNCTION_LINES),
                                severity="medium",
                            ))
                        depth = self._nesting_depth(node)
                        if depth > self.MAX_NESTING_DEPTH:
                            issues.append(PerformanceIssue(
                                file_path=file_path,
                                function_name=node.name,
                                metric="nesting_depth",
                                old_value=float(self.MAX_NESTING_DEPTH),
                                new_value=float(depth),
                                threshold=float(self.MAX_NESTING_DEPTH),
                                severity="low",
                            ))
                        cc = self._cyclomatic_complexity(node)
                        if cc > 10:
                            issues.append(PerformanceIssue(
                                file_path=file_path,
                                function_name=node.name,
                                metric="cyclomatic_complexity",
                                old_value=10.0,
                                new_value=float(cc),
                                threshold=10.0,
                                severity="medium",
                            ))
            except SyntaxError:
                pass

        return issues

    def _nesting_depth(self, node: ast.AST) -> int:
        """Estimate max nesting depth of control flow."""
        depth = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                depth += 1
        return min(depth, 20)

    def _cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        """Estimate cyclomatic complexity (1 + branches)."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def compare_profiles(
        self,
        old_profile: Dict[str, Any],
        new_profile: Dict[str, Any],
        threshold_pct: float = 5.0,
    ) -> List[PerformanceIssue]:
        """Compare cProfile-style data for regressions."""
        issues: List[PerformanceIssue] = []
        old_times = old_profile.get("functions", {}) or old_profile.get("cumtime", {})
        new_times = new_profile.get("functions", {}) or new_profile.get("cumtime", {})

        if isinstance(old_times, dict) and isinstance(new_times, dict):
            for func, new_val in new_times.items():
                if isinstance(new_val, (int, float)):
                    old_val = old_times.get(func, 0) or 0
                    if old_val > 0 and new_val > old_val * (1 + threshold_pct / 100):
                        pct = ((new_val - old_val) / old_val) * 100
                        issues.append(PerformanceIssue(
                            file_path="",
                            function_name=str(func),
                            metric="execution_time",
                            old_value=float(old_val),
                            new_value=float(new_val),
                            threshold=threshold_pct,
                            severity="high" if pct > 10 else "medium",
                        ))

        return issues

    def check_hot_functions(
        self,
        source: str,
        profile_data: Dict[str, Any],
    ) -> List[PerformanceIssue]:
        """Check if hot functions from profile have complexity issues."""
        issues = self.analyze_code_complexity(source, "")
        hot = profile_data.get("hot_functions", []) or profile_data.get("top", [])
        if hot:
            hot_names = {h if isinstance(h, str) else h.get("name", "") for h in hot}
            return [i for i in issues if i.function_name in hot_names]
        return issues

    def generate_report(
        self,
        issues: List[PerformanceIssue],
    ) -> Dict[str, Any]:
        """Generate performance report."""
        high = sum(1 for i in issues if i.severity == "high")
        medium = sum(1 for i in issues if i.severity == "medium")
        low = sum(1 for i in issues if i.severity == "low")
        score = max(0, 100 - high * 20 - medium * 10 - low * 3)
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
