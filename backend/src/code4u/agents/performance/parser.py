"""Performance Profile Parser — ingests profiler output.

Supports:
  - **cProfile JSON** (Python ``pstats`` exported to JSON).
  - **cpuprofile** (Chrome/Node V8 CPU profile format).
  - **Generic JSON** (function name, total time, call count).

Produces a ``ProfileSummary`` with ranked ``FunctionProfile`` entries
ordered by cumulative time (hottest first).

Usage::

    ingestor = PerformanceIngestor()
    summary = ingestor.from_json(profile_data)
    for fn in summary.hot_functions(top=5):
        print(fn.name, fn.cumulative_time_ms, fn.call_count)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("perf_parser")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FunctionProfile:
    """Profile data for a single function."""
    name: str
    file_path: str = ""
    line_number: int = 0
    cumulative_time_ms: float = 0.0
    self_time_ms: float = 0.0
    call_count: int = 0
    callers: List[str] = field(default_factory=list)
    callees: List[str] = field(default_factory=list)

    @property
    def avg_time_ms(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.cumulative_time_ms / self.call_count

    @property
    def is_hot(self) -> bool:
        return self.cumulative_time_ms > 100 or self.call_count > 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "cumulativeTimeMs": round(self.cumulative_time_ms, 2),
            "selfTimeMs": round(self.self_time_ms, 2),
            "callCount": self.call_count,
            "avgTimeMs": round(self.avg_time_ms, 4),
            "isHot": self.is_hot,
            "callers": self.callers[:5],
            "callees": self.callees[:5],
        }


@dataclass
class ProfileSummary:
    """Aggregated profile summary with ranked functions."""
    functions: List[FunctionProfile] = field(default_factory=list)
    total_time_ms: float = 0.0
    profile_type: str = "generic"
    source_file: str = ""

    def hot_functions(self, top: int = 10) -> List[FunctionProfile]:
        """Return the top N functions by cumulative time."""
        ranked = sorted(
            self.functions,
            key=lambda f: f.cumulative_time_ms,
            reverse=True,
        )
        return ranked[:top]

    def hot_files(self) -> List[Dict[str, Any]]:
        """Aggregate time per file and return sorted by total time."""
        file_times: Dict[str, float] = {}
        for fn in self.functions:
            if fn.file_path:
                file_times[fn.file_path] = (
                    file_times.get(fn.file_path, 0) + fn.cumulative_time_ms
                )
        ranked = sorted(file_times.items(), key=lambda x: x[1], reverse=True)
        return [
            {"file": f, "totalTimeMs": round(t, 2)}
            for f, t in ranked
        ]

    @property
    def function_count(self) -> int:
        return len(self.functions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "functions": [f.to_dict() for f in self.hot_functions(20)],
            "totalTimeMs": round(self.total_time_ms, 2),
            "profileType": self.profile_type,
            "functionCount": self.function_count,
            "hotFiles": self.hot_files()[:10],
        }


# ---------------------------------------------------------------------------
# PerformanceIngestor
# ---------------------------------------------------------------------------

class PerformanceIngestor:
    """Parses profiler output into a ``ProfileSummary``."""

    def from_json(self, data: Dict[str, Any]) -> ProfileSummary:
        """Auto-detect format and parse."""
        if "nodes" in data and "samples" in data:
            return self._parse_cpuprofile(data)
        if "stats" in data:
            return self._parse_cprofile(data)
        if "functions" in data:
            return self._parse_generic(data)
        # Fallback: try generic
        return self._parse_generic(data)

    def from_cprofile(self, data: Dict[str, Any]) -> ProfileSummary:
        """Parse Python cProfile / pstats JSON export."""
        return self._parse_cprofile(data)

    def from_cpuprofile(self, data: Dict[str, Any]) -> ProfileSummary:
        """Parse Chrome/Node V8 cpuprofile format."""
        return self._parse_cpuprofile(data)

    def from_generic(self, data: Dict[str, Any]) -> ProfileSummary:
        """Parse a generic list of function profiles."""
        return self._parse_generic(data)

    # -- Internal parsers ----------------------------------------------------

    def _parse_cprofile(self, data: Dict[str, Any]) -> ProfileSummary:
        """Parse Python cProfile stats format.

        Expected shape::

            {
                "stats": {
                    "file.py:42(func_name)": {
                        "cumulative_time": 1.234,
                        "total_time": 0.567,
                        "call_count": 100,
                        "callers": ["other.py:10(caller)"]
                    }
                },
                "total_time": 5.0
            }
        """
        summary = ProfileSummary(profile_type="cprofile")
        summary.total_time_ms = data.get("total_time", 0) * 1000

        for key, stats in data.get("stats", {}).items():
            name, file_path, line = self._parse_cprofile_key(key)
            fp = FunctionProfile(
                name=name,
                file_path=file_path,
                line_number=line,
                cumulative_time_ms=stats.get("cumulative_time", 0) * 1000,
                self_time_ms=stats.get("total_time", 0) * 1000,
                call_count=stats.get("call_count", 0),
                callers=stats.get("callers", []),
            )
            summary.functions.append(fp)

        logger.info("profile_parsed", type="cprofile", functions=len(summary.functions))
        return summary

    def _parse_cpuprofile(self, data: Dict[str, Any]) -> ProfileSummary:
        """Parse V8 cpuprofile format.

        Expected shape::

            {
                "nodes": [
                    {"id": 1, "callFrame": {"functionName": "f", "url": "file.js", "lineNumber": 10}, "hitCount": 50},
                    ...
                ],
                "samples": [1, 1, 2, 3, ...],
                "startTime": 0,
                "endTime": 1000000
            }
        """
        summary = ProfileSummary(profile_type="cpuprofile")

        start = data.get("startTime", 0)
        end = data.get("endTime", 0)
        summary.total_time_ms = (end - start) / 1000.0

        total_samples = len(data.get("samples", []))
        sample_duration_ms = summary.total_time_ms / total_samples if total_samples else 0

        # Count hits per node
        hit_counts: Dict[int, int] = {}
        for sample_id in data.get("samples", []):
            hit_counts[sample_id] = hit_counts.get(sample_id, 0) + 1

        for node in data.get("nodes", []):
            call_frame = node.get("callFrame", {})
            node_id = node.get("id", 0)
            hit_count = node.get("hitCount", 0) + hit_counts.get(node_id, 0)

            fn_name = call_frame.get("functionName", "(anonymous)")
            if not fn_name or fn_name == "(idle)":
                continue

            fp = FunctionProfile(
                name=fn_name,
                file_path=call_frame.get("url", ""),
                line_number=call_frame.get("lineNumber", 0),
                self_time_ms=hit_count * sample_duration_ms,
                cumulative_time_ms=hit_count * sample_duration_ms,
                call_count=hit_count,
            )
            summary.functions.append(fp)

        logger.info("profile_parsed", type="cpuprofile", functions=len(summary.functions))
        return summary

    def _parse_generic(self, data: Dict[str, Any]) -> ProfileSummary:
        """Parse a generic function profile list.

        Expected shape::

            {
                "functions": [
                    {"name": "func", "file": "a.py", "line": 10,
                     "cumulative_time_ms": 500, "self_time_ms": 200,
                     "call_count": 50},
                    ...
                ],
                "total_time_ms": 1000
            }
        """
        summary = ProfileSummary(profile_type="generic")
        summary.total_time_ms = data.get("total_time_ms", 0)

        for entry in data.get("functions", []):
            fp = FunctionProfile(
                name=entry.get("name", "unknown"),
                file_path=entry.get("file", entry.get("file_path", "")),
                line_number=entry.get("line", entry.get("line_number", 0)),
                cumulative_time_ms=entry.get("cumulative_time_ms", 0),
                self_time_ms=entry.get("self_time_ms", 0),
                call_count=entry.get("call_count", 0),
                callers=entry.get("callers", []),
                callees=entry.get("callees", []),
            )
            summary.functions.append(fp)

        if not summary.total_time_ms and summary.functions:
            summary.total_time_ms = max(f.cumulative_time_ms for f in summary.functions)

        logger.info("profile_parsed", type="generic", functions=len(summary.functions))
        return summary

    @staticmethod
    def _parse_cprofile_key(key: str) -> tuple:
        """Parse 'file.py:42(func_name)' into (name, file, line)."""
        m = re.match(r"(.+?):(\d+)\((.+?)\)", key)
        if m:
            return m.group(3), m.group(1), int(m.group(2))
        return key, "", 0
