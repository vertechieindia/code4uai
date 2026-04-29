"""Test Runner API — execute tests and return structured results.

Endpoints:
  - ``POST /test/run``     — run tests in a workspace and return pass/fail + output.
  - ``POST /test/detect``  — detect the test framework for a workspace.
  - ``POST /test/lint``    — run language-appropriate linters on a workspace.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class TestRunRequest(BaseModel):
    workspacePath: str = Field(..., description="Absolute path to the workspace root.")
    command: str = Field("", description="Test command (auto-detected if empty).")
    extraArgs: List[str] = Field(default_factory=list)
    timeout: int = Field(120, description="Max seconds to wait for tests.")


class TestDetectRequest(BaseModel):
    workspacePath: str = Field(..., description="Absolute path to the workspace root.")


def _detect_test_framework(workspace: str) -> str:
    """Auto-detect the appropriate test runner for a workspace."""
    if os.path.isfile(os.path.join(workspace, "pytest.ini")) or \
       os.path.isfile(os.path.join(workspace, "setup.cfg")) or \
       os.path.isfile(os.path.join(workspace, "pyproject.toml")):
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__", ".venv", "venv")]
            if any(f.startswith("test_") and f.endswith(".py") for f in files):
                return "pytest"

    pkg_json = os.path.join(workspace, "package.json")
    if os.path.isfile(pkg_json):
        try:
            import json
            with open(pkg_json) as f:
                pkg = json.load(f)
            deps = {**pkg.get("devDependencies", {}), **pkg.get("dependencies", {})}
            if "vitest" in deps:
                return "vitest"
            if "jest" in deps:
                return "jest"
            if "test" in pkg.get("scripts", {}):
                return "npm"
        except Exception:
            pass

    if os.path.isfile(os.path.join(workspace, "go.mod")):
        return "go"

    if os.path.isfile(os.path.join(workspace, "Cargo.toml")):
        return "cargo"

    if os.path.isfile(os.path.join(workspace, "pom.xml")) or \
       os.path.isfile(os.path.join(workspace, "build.gradle")):
        return "gradle" if os.path.isfile(os.path.join(workspace, "build.gradle")) else "maven"

    return "pytest"


_VITEST_CMD = ["npx", "vitest", "run", "--reporter=verbose"]


@router.post("/test/run")
async def run_tests(request: TestRunRequest):
    """Run tests in the workspace and return structured results."""
    from code4u.core.executor_ext import TestRunner

    workspace = request.workspacePath
    command = request.command or _detect_test_framework(workspace)

    dep_map = None
    try:
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
        dep_map = SymbolIndexer().index_workspace(workspace, use_cache=True)
    except Exception:
        pass

    runner = TestRunner(dep_map)

    if command in ("vitest", "go", "cargo", "gradle", "maven"):
        cmd_map: Dict[str, List[str]] = {
            "vitest": list(_VITEST_CMD),
            "go": ["go", "test", "-v", "./..."],
            "cargo": ["cargo", "test"],
            "gradle": ["./gradlew", "test"],
            "maven": ["mvn", "test", "-B"],
        }
        cmd_parts = cmd_map.get(command, [command]) + request.extraArgs
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd_parts, cwd=workspace, capture_output=True, text=True,
                timeout=request.timeout,
            )
            duration = (time.monotonic() - t0) * 1000
            passed = proc.returncode == 0
            failed_tests = _extract_failed_tests(proc.stdout + "\n" + proc.stderr)
            return {
                "status": "pass" if passed else "fail",
                "output": proc.stdout + ("\n" + proc.stderr if proc.stderr else ""),
                "returnCode": proc.returncode,
                "durationMs": round(duration, 1),
                "failedTests": failed_tests,
                "command": " ".join(cmd_parts),
                "framework": command,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "fail",
                "output": "Test command timed out",
                "returnCode": -1,
                "durationMs": round((time.monotonic() - t0) * 1000, 1),
                "failedTests": [],
                "command": " ".join(cmd_parts),
                "framework": command,
            }
        except FileNotFoundError:
            return {
                "status": "fail",
                "output": f"Command not found: {cmd_parts[0]}",
                "returnCode": -1,
                "durationMs": 0,
                "failedTests": [],
                "command": " ".join(cmd_parts),
                "framework": command,
            }

    result = runner.run(
        command=command,
        workspace=workspace,
        timeout=request.timeout,
        extra_args=request.extraArgs if request.extraArgs else None,
    )

    failed_tests = _extract_failed_tests(result.stdout + "\n" + result.stderr)

    return {
        "status": "pass" if result.passed else "fail",
        "output": result.stdout + ("\n" + result.stderr if result.stderr else ""),
        "returnCode": result.return_code,
        "durationMs": round(result.duration_ms, 1),
        "failedTests": failed_tests,
        "command": result.command,
        "framework": command,
        "diagnoses": [d.to_dict() for d in result.diagnoses] if not result.passed else [],
    }


@router.post("/test/detect")
async def detect_framework(request: TestDetectRequest):
    """Detect the test framework for a workspace."""
    framework = _detect_test_framework(request.workspacePath)
    return {"framework": framework, "workspacePath": request.workspacePath}


def _extract_failed_tests(output: str) -> list[str]:
    """Extract names of failed tests from test runner output."""
    import re
    failed: list[str] = []

    # pytest: FAILED tests/test_foo.py::test_bar
    for m in re.finditer(r"FAILED\s+(\S+)", output):
        failed.append(m.group(1))

    # jest/vitest: ✕ or × or FAIL followed by test name
    for m in re.finditer(r"[✕×]\s+(.+?)(?:\s+\(\d+\s*m?s\))?$", output, re.MULTILINE):
        name = m.group(1).strip()
        if name and name not in failed:
            failed.append(name)

    # go test: --- FAIL: TestFoo (0.00s)
    for m in re.finditer(r"--- FAIL:\s+(\S+)", output):
        name = m.group(1)
        if name not in failed:
            failed.append(name)

    return failed


# ---------------------------------------------------------------------------
# Polyglot linting
# ---------------------------------------------------------------------------

class LintRequest(BaseModel):
    workspacePath: str = Field(..., description="Workspace root path.")
    languages: List[str] = Field(default_factory=list, description="Languages to lint (auto-detect if empty).")
    timeout: int = Field(60, description="Max seconds per linter.")


def _detect_languages(workspace: str) -> List[str]:
    """Detect which languages are present in a workspace."""
    langs: set[str] = set()
    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}

    if os.path.isfile(os.path.join(workspace, "go.mod")):
        langs.add("go")
    if os.path.isfile(os.path.join(workspace, "package.json")):
        langs.add("typescript")
    if os.path.isfile(os.path.join(workspace, "Cargo.toml")):
        langs.add("rust")
    if os.path.isfile(os.path.join(workspace, "pom.xml")) or \
       os.path.isfile(os.path.join(workspace, "build.gradle")):
        langs.add("java")

    ext_map = {".py": "python", ".ts": "typescript", ".tsx": "typescript",
               ".js": "typescript", ".go": "go", ".java": "java", ".rs": "rust"}

    scanned = 0
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ext_map:
                langs.add(ext_map[ext])
                scanned += 1
            if scanned > 50:
                break
        if scanned > 50:
            break

    return sorted(langs)


_LINTER_COMMANDS: Dict[str, List[List[str]]] = {
    "python": [
        ["python3", "-m", "py_compile"],
        ["python3", "-m", "ruff", "check", "--select=E,W,F", "."],
    ],
    "typescript": [
        ["npx", "eslint", "--format=compact", "."],
    ],
    "go": [
        ["go", "vet", "./..."],
        ["staticcheck", "./..."],
    ],
    "java": [
        ["javac", "-Xlint:all", "-d", "/tmp/code4u-javac"],
    ],
    "rust": [
        ["cargo", "clippy", "--", "-D", "warnings"],
    ],
}


def _run_linter(cmd: List[str], workspace: str, timeout: int) -> Dict[str, Any]:
    """Run a single linter command and return structured results."""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, cwd=workspace, capture_output=True, text=True,
            timeout=timeout,
        )
        duration = (time.monotonic() - t0) * 1000
        return {
            "command": " ".join(cmd),
            "status": "pass" if proc.returncode == 0 else "fail",
            "returnCode": proc.returncode,
            "output": (proc.stdout + "\n" + proc.stderr).strip()[:3000],
            "durationMs": round(duration, 1),
            "issues": _parse_lint_output(proc.stdout + "\n" + proc.stderr),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(cmd),
            "status": "timeout",
            "returnCode": -1,
            "output": "Linter timed out",
            "durationMs": round((time.monotonic() - t0) * 1000, 1),
            "issues": [],
        }
    except FileNotFoundError:
        return {
            "command": " ".join(cmd),
            "status": "skipped",
            "returnCode": -1,
            "output": f"Tool not found: {cmd[0]}",
            "durationMs": 0,
            "issues": [],
        }


def _parse_lint_output(output: str) -> List[Dict[str, str]]:
    """Extract structured lint issues from raw output."""
    import re
    issues: List[Dict[str, str]] = []

    for m in re.finditer(
        r"([^\s:]+):(\d+):(\d+):\s*(.*?)$", output, re.MULTILINE,
    ):
        issues.append({
            "file": m.group(1),
            "line": m.group(2),
            "col": m.group(3),
            "message": m.group(4).strip(),
        })

    for m in re.finditer(
        r"([^\s:]+):(\d+):\s*(.*?)$", output, re.MULTILINE,
    ):
        entry = {"file": m.group(1), "line": m.group(2), "col": "0", "message": m.group(3).strip()}
        if entry not in issues:
            issues.append(entry)

    return issues[:50]


@router.post("/test/lint")
async def run_linters(request: LintRequest):
    """Run language-appropriate linters on a workspace."""
    workspace = request.workspacePath
    if not os.path.isdir(workspace):
        return {"error": "Workspace not found", "results": []}

    languages = request.languages or _detect_languages(workspace)
    results: List[Dict[str, Any]] = []

    for lang in languages:
        cmds = _LINTER_COMMANDS.get(lang, [])
        for cmd in cmds:
            result = _run_linter(cmd, workspace, request.timeout)
            result["language"] = lang
            results.append(result)

    total_issues = sum(len(r.get("issues", [])) for r in results)
    any_fail = any(r["status"] == "fail" for r in results)

    return {
        "status": "fail" if any_fail else "pass",
        "languages": languages,
        "results": results,
        "totalIssues": total_issues,
    }
