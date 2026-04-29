"""Profiler API — performance analysis and optimization.

Endpoints:
  - ``POST /profiler/ingest``      — upload a profile and get hot functions.
  - ``POST /profiler/analyze``     — analyze a hot function for smells.
  - ``POST /profiler/scan``        — scan a file for performance smells.
  - ``POST /profiler/profile-file`` — run cProfile on a Python file.
  - ``POST /profiler/workspace``   — scan all files in a workspace for hot spots.
"""

from __future__ import annotations

import ast
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from code4u.agents.performance.parser import PerformanceIngestor
from code4u.agents.performance.optimizer import Optimizer

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    profile: Dict[str, Any] = Field(..., description="Profile data (cProfile, cpuprofile, or generic JSON).")
    top: int = Field(10, description="Number of hot functions to return.")


class AnalyzeRequest(BaseModel):
    functionName: str = Field(..., description="Name of the hot function.")
    filePath: str = Field("", description="Path to the source file.")
    cumulativeTimeMs: float = Field(0, description="Cumulative time in ms.")
    callCount: int = Field(0, description="Number of calls.")
    source: str = Field("", description="Source code of the function.")


class ScanRequest(BaseModel):
    source: str = Field(..., description="Source code to scan.")
    filePath: str = Field("", description="File path for context.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/profiler/ingest")
async def ingest_profile(request: IngestRequest):
    """Upload a profile and return hot functions."""
    ingestor = PerformanceIngestor()
    summary = ingestor.from_json(request.profile)
    hot = summary.hot_functions(top=request.top)
    return {
        "summary": summary.to_dict(),
        "hotFunctions": [f.to_dict() for f in hot],
        "hotFiles": summary.hot_files()[:10],
    }


@router.post("/profiler/analyze")
async def analyze_function(request: AnalyzeRequest):
    """Analyze a hot function for performance smells."""
    from code4u.agents.performance.parser import FunctionProfile

    fn = FunctionProfile(
        name=request.functionName,
        file_path=request.filePath,
        cumulative_time_ms=request.cumulativeTimeMs,
        call_count=request.callCount,
    )
    optimizer = Optimizer()
    plan = optimizer.analyze_hot_path(fn, request.source)
    return plan.to_dict()


@router.post("/profiler/scan")
async def scan_source(request: ScanRequest):
    """Scan source code for performance anti-patterns."""
    optimizer = Optimizer()
    smells = optimizer.scan_source(request.source, request.filePath)
    return {
        "smells": [s.to_dict() for s in smells],
        "count": len(smells),
    }


# ---------------------------------------------------------------------------
# File-level profiling (cProfile)
# ---------------------------------------------------------------------------

class ProfileFileRequest(BaseModel):
    filePath: str = Field(..., description="Absolute path to a Python file to profile.")
    entryFunction: str = Field("", description="Function to profile (empty = whole module).")
    timeout: int = Field(30, description="Max seconds for profiling.")


@router.post("/profiler/profile-file")
async def profile_file(request: ProfileFileRequest):
    """Run cProfile on a Python file and return hot functions."""
    file_path = request.filePath
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    if not file_path.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only Python files supported for cProfile")

    import cProfile
    import pstats
    import io
    import subprocess

    t0 = time.monotonic()

    try:
        proc = subprocess.run(
            [
                "python3", "-m", "cProfile", "-s", "cumulative",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=request.timeout,
            cwd=os.path.dirname(file_path),
        )
        duration_ms = (time.monotonic() - t0) * 1000
        output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "output": "Profiling timed out", "hotFunctions": []}
    except FileNotFoundError:
        return {"status": "error", "output": "python3 not found", "hotFunctions": []}

    hot_functions = _parse_cprofile_output(output, file_path)

    return {
        "status": "completed",
        "filePath": file_path,
        "durationMs": round(duration_ms, 1),
        "hotFunctions": hot_functions[:20],
        "output": output[:5000],
        "totalFunctions": len(hot_functions),
    }


def _parse_cprofile_output(output: str, file_path: str) -> List[Dict[str, Any]]:
    """Parse cProfile text output into structured hot functions."""
    import re
    functions: List[Dict[str, Any]] = []
    in_table = False

    for line in output.splitlines():
        if "ncalls" in line and "tottime" in line and "cumtime" in line:
            in_table = True
            continue

        if not in_table:
            continue

        parts = line.split(None, 5)
        if len(parts) < 6:
            continue

        try:
            ncalls = parts[0]
            tottime = float(parts[1])
            percall1 = float(parts[2])
            cumtime = float(parts[3])
            percall2 = float(parts[4])
            fn_info = parts[5]
        except (ValueError, IndexError):
            continue

        if cumtime < 0.001 and tottime < 0.001:
            continue

        m = re.match(r"(.+):(\d+)\((.+)\)", fn_info)
        fn_file = m.group(1) if m else ""
        fn_line = int(m.group(2)) if m else 0
        fn_name = m.group(3) if m else fn_info

        if fn_name.startswith("<") and fn_name not in ("<module>",):
            continue

        functions.append({
            "name": fn_name,
            "filePath": fn_file,
            "line": fn_line,
            "calls": ncalls,
            "totalTimeSec": tottime,
            "cumulativeTimeSec": cumtime,
            "cumulativeTimeMs": round(cumtime * 1000, 2),
            "perCallMs": round(percall2 * 1000, 4),
        })

    functions.sort(key=lambda f: f["cumulativeTimeSec"], reverse=True)
    return functions


# ---------------------------------------------------------------------------
# Workspace-wide performance scan
# ---------------------------------------------------------------------------

class WorkspaceScanRequest(BaseModel):
    workspacePath: str = Field(..., description="Absolute path to workspace.")
    maxFiles: int = Field(30, description="Max files to scan.")


@router.post("/profiler/workspace")
async def scan_workspace(request: WorkspaceScanRequest):
    """Scan all Python/TS files in a workspace for performance issues."""
    workspace = request.workspacePath
    if not os.path.isdir(workspace):
        raise HTTPException(status_code=404, detail="Workspace not found")

    optimizer = Optimizer()
    all_results: List[Dict[str, Any]] = []
    scanned = 0
    skip_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}

    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in (".py", ".ts", ".tsx", ".js", ".jsx"):
                continue
            if scanned >= request.maxFiles:
                break

            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, workspace)

            try:
                with open(fpath, "r", errors="ignore") as f:
                    source = f.read()
            except Exception:
                continue

            if not source.strip() or len(source) < 20:
                continue

            scanned += 1
            smells = optimizer.scan_source(source, rel_path)
            complexity = _file_complexity(source, ext)

            if smells or complexity.get("maxComplexity", 0) > 5:
                all_results.append({
                    "filePath": rel_path,
                    "smells": [s.to_dict() for s in smells],
                    "smellCount": len(smells),
                    **complexity,
                })
        if scanned >= request.maxFiles:
            break

    all_results.sort(key=lambda r: r.get("smellCount", 0) + r.get("maxComplexity", 0), reverse=True)

    return {
        "files": all_results,
        "scannedFiles": scanned,
        "totalIssues": sum(r["smellCount"] for r in all_results),
    }


def _file_complexity(source: str, ext: str) -> Dict[str, Any]:
    """Compute complexity metrics for a single file."""
    if ext != ".py":
        lines = source.count("\n") + 1
        return {"lines": lines, "maxComplexity": 0, "avgComplexity": 0, "functions": 0}

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"lines": source.count("\n") + 1, "maxComplexity": 0, "avgComplexity": 0, "functions": 0}

    complexities: List[int] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cc = 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                    cc += 1
                elif isinstance(child, ast.BoolOp):
                    cc += len(child.values) - 1
            complexities.append(cc)

    lines = source.count("\n") + 1
    max_cc = max(complexities) if complexities else 0
    avg_cc = round(sum(complexities) / len(complexities), 1) if complexities else 0

    return {
        "lines": lines,
        "maxComplexity": max_cc,
        "avgComplexity": avg_cc,
        "functions": len(complexities),
    }
