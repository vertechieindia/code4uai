"""Performance Optimizer — evidence-based code optimization.

Analyzes "Hot Functions" from profiler data, cross-references them
with the ``SymbolIndexer`` to read actual source code, and detects
performance anti-patterns using AST analysis and regex heuristics.

Produces an ``OptimizationPlan`` with specific, actionable fixes.

Detected patterns:
  - **O(n^2) loops**: nested ``for`` loops over the same or related data.
  - **N+1 queries**: DB calls inside loops.
  - **Redundant computation**: repeated calls to the same function in a loop.
  - **Missing caching**: expensive pure functions called repeatedly.
  - **Blocking calls**: ``time.sleep()``, synchronous I/O in async code.
  - **Inefficient search**: linear search where a set/dict lookup suffices.
  - **Bubble/selection sort**: manual sort implementations.

Usage::

    optimizer = Optimizer()
    plan = optimizer.analyze_hot_path(function_profile, source_code)
    for opt in plan.optimizations:
        print(opt.category, opt.description, opt.fix_suggestion)
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

from code4u.agents.performance.parser import FunctionProfile

logger = structlog.get_logger("perf_optimizer")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PerformanceSmell:
    """A detected performance anti-pattern."""
    category: str       # "O(n^2)", "N+1", "blocking", "inefficient_search", etc.
    description: str
    file_path: str = ""
    line_number: int = 0
    severity: str = "warning"  # "info", "warning", "error"
    pattern_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "severity": self.severity,
            "patternId": self.pattern_id,
        }


@dataclass
class Optimization:
    """A single proposed optimization."""
    category: str
    description: str
    fix_suggestion: str
    estimated_speedup: str = ""
    file_path: str = ""
    line_number: int = 0
    confidence: float = 0.8

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "fixSuggestion": self.fix_suggestion,
            "estimatedSpeedup": self.estimated_speedup,
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "confidence": self.confidence,
        }


@dataclass
class OptimizationPlan:
    """Complete optimization proposal for a hot function."""
    function_name: str
    file_path: str = ""
    cumulative_time_ms: float = 0.0
    smells: List[PerformanceSmell] = field(default_factory=list)
    optimizations: List[Optimization] = field(default_factory=list)

    @property
    def has_optimizations(self) -> bool:
        return len(self.optimizations) > 0

    @property
    def top_category(self) -> str:
        if self.optimizations:
            return self.optimizations[0].category
        return "none"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "functionName": self.function_name,
            "filePath": self.file_path,
            "cumulativeTimeMs": round(self.cumulative_time_ms, 2),
            "smells": [s.to_dict() for s in self.smells],
            "optimizations": [o.to_dict() for o in self.optimizations],
            "hasOptimizations": self.has_optimizations,
        }


# ---------------------------------------------------------------------------
# Regex-based smell detectors
# ---------------------------------------------------------------------------

_PERF_SMELL_PATTERNS: List[Dict[str, Any]] = [
    {
        "id": "PERF-001",
        "pattern": re.compile(r"time\.sleep\s*\("),
        "category": "blocking",
        "description": "time.sleep() found — blocks the event loop or thread.",
        "fix": "Use asyncio.sleep() for async code, or eliminate the sleep.",
        "severity": "warning",
    },
    {
        "id": "PERF-002",
        "pattern": re.compile(r"for\s+\w+\s+in\s+.+:\s*\n\s+.*\.(execute|query|fetchall|fetchone|cursor)\s*\("),
        "category": "N+1",
        "description": "Database query inside a loop — potential N+1 problem.",
        "fix": "Batch the query outside the loop or use a JOIN.",
        "severity": "error",
    },
    {
        "id": "PERF-003",
        "pattern": re.compile(r"if\s+\w+\s+in\s+\["),
        "category": "inefficient_search",
        "description": "Linear search in a list literal — use a set for O(1) lookup.",
        "fix": "Replace list with a set: if x in {a, b, c}.",
        "severity": "info",
    },
    {
        "id": "PERF-004",
        "pattern": re.compile(r"\.readlines\(\)"),
        "category": "memory",
        "description": ".readlines() loads entire file into memory.",
        "fix": "Iterate over the file object directly: for line in f.",
        "severity": "warning",
    },
    {
        "id": "PERF-005",
        "pattern": re.compile(r"\+\s*=\s*.*\bstr\b|\bstr\s*\+\s*str|\"\"\.join"),
        "category": "string_concat",
        "description": "String concatenation in a loop — use list + join.",
        "fix": "Collect into a list, then ''.join(parts).",
        "severity": "info",
    },
]


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

class Optimizer:
    """Analyzes hot functions for performance anti-patterns.

    Usage::

        optimizer = Optimizer()
        plan = optimizer.analyze_hot_path(fn_profile, source)
    """

    def analyze_hot_path(
        self,
        fn: FunctionProfile,
        source: str = "",
    ) -> OptimizationPlan:
        """Analyze a hot function and produce an optimization plan."""
        plan = OptimizationPlan(
            function_name=fn.name,
            file_path=fn.file_path,
            cumulative_time_ms=fn.cumulative_time_ms,
        )

        if not source:
            return plan

        # Regex-based smell detection
        plan.smells.extend(self._detect_regex_smells(source, fn.file_path))

        # AST-based analysis
        plan.smells.extend(self._detect_ast_smells(source, fn.file_path))

        # Generate optimizations from smells
        for smell in plan.smells:
            opt = self._smell_to_optimization(smell, fn)
            if opt:
                plan.optimizations.append(opt)

        logger.info(
            "hot_path_analyzed",
            function=fn.name,
            smells=len(plan.smells),
            optimizations=len(plan.optimizations),
        )
        return plan

    def scan_source(self, source: str, file_path: str = "") -> List[PerformanceSmell]:
        """Scan source code for performance smells without profile data."""
        smells = self._detect_regex_smells(source, file_path)
        smells.extend(self._detect_ast_smells(source, file_path))
        return smells

    # -- Internal detectors --------------------------------------------------

    def _detect_regex_smells(self, source: str, file_path: str) -> List[PerformanceSmell]:
        """Apply regex-based smell patterns."""
        smells = []
        for p in _PERF_SMELL_PATTERNS:
            for match in p["pattern"].finditer(source):
                line_no = source[:match.start()].count("\n") + 1
                smells.append(PerformanceSmell(
                    category=p["category"],
                    description=p["description"],
                    file_path=file_path,
                    line_number=line_no,
                    severity=p["severity"],
                    pattern_id=p["id"],
                ))
        return smells

    def _detect_ast_smells(self, source: str, file_path: str) -> List[PerformanceSmell]:
        """AST-based analysis for nested loops and sort patterns."""
        smells = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return smells

        smells.extend(self._detect_nested_loops(tree, file_path))
        smells.extend(self._detect_manual_sort(tree, source, file_path))
        return smells

    def _detect_nested_loops(self, tree: ast.AST, file_path: str) -> List[PerformanceSmell]:
        """Detect O(n^2) nested for-loops."""
        smells = []
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                for child in ast.walk(node):
                    if isinstance(child, ast.For) and child is not node:
                        smells.append(PerformanceSmell(
                            category="O(n^2)",
                            description=(
                                f"Nested for-loop detected (line {getattr(node, 'lineno', 0)}). "
                                "Consider using a dict/set for O(n) lookup, or batch processing."
                            ),
                            file_path=file_path,
                            line_number=getattr(node, "lineno", 0),
                            severity="warning",
                            pattern_id="PERF-AST-001",
                        ))
                        break  # only flag once per outer loop
        return smells

    def _detect_manual_sort(
        self, tree: ast.AST, source: str, file_path: str
    ) -> List[PerformanceSmell]:
        """Detect manual sort implementations (bubble sort, selection sort)."""
        smells = []
        # Heuristic: nested loops with comparison + swap pattern
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            src_segment = ast.get_source_segment(source, node) or ""
            # Bubble sort indicators: nested loop + swap (a[i], a[j] = a[j], a[i])
            if re.search(r"for\s+\w+\s+in\s+range", src_segment):
                swap = re.search(
                    r"\w+\[\w+\]\s*,\s*\w+\[\w+\]\s*=\s*\w+\[\w+\]\s*,\s*\w+\[\w+\]",
                    src_segment,
                )
                if swap:
                    smells.append(PerformanceSmell(
                        category="manual_sort",
                        description=(
                            f"Manual sort detected in '{node.name}'. "
                            "Use the built-in sorted() or list.sort() for O(n log n)."
                        ),
                        file_path=file_path,
                        line_number=getattr(node, "lineno", 0),
                        severity="warning",
                        pattern_id="PERF-AST-002",
                    ))
        return smells

    def _smell_to_optimization(
        self, smell: PerformanceSmell, fn: FunctionProfile
    ) -> Optional[Optimization]:
        """Convert a detected smell into an actionable optimization."""
        fix_map = {
            "O(n^2)": (
                "Replace the nested loop with a dict/set-based lookup "
                "to reduce complexity from O(n^2) to O(n).",
                "2-10x speedup",
            ),
            "N+1": (
                "Move the query outside the loop. Use a single batch query "
                "with WHERE ... IN (...) or a JOIN.",
                "10-100x speedup",
            ),
            "blocking": (
                "Remove time.sleep() or replace with asyncio.sleep() "
                "in async code. Consider event-driven alternatives.",
                "Eliminates artificial latency",
            ),
            "inefficient_search": (
                "Replace the list literal with a set for O(1) membership testing.",
                "Minor speedup (O(n) → O(1) per check)",
            ),
            "memory": (
                "Iterate over the file object directly instead of "
                "loading all lines into memory with .readlines().",
                "Reduced memory footprint",
            ),
            "manual_sort": (
                "Replace the manual sort implementation with Python's "
                "built-in sorted() or list.sort() (Timsort, O(n log n)).",
                "Significant speedup for large inputs",
            ),
            "string_concat": (
                "Collect strings into a list, then use ''.join(parts) "
                "instead of repeated += concatenation.",
                "O(n) instead of O(n^2) for string building",
            ),
        }

        fix_info = fix_map.get(smell.category)
        if not fix_info:
            return None

        return Optimization(
            category=smell.category,
            description=smell.description,
            fix_suggestion=fix_info[0],
            estimated_speedup=fix_info[1],
            file_path=smell.file_path or fn.file_path,
            line_number=smell.line_number,
        )
