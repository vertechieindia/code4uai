"""Integration Wrapper — run test commands and capture failures.

Provides ``TestRunner``, a thin wrapper around ``subprocess`` that:
  1. Runs a test command (pytest, jest, go test, etc.).
  2. Captures stdout and stderr.
  3. If the return code is non-zero, feeds the output to the
     ``StackTraceParser`` and ``Diagnoser``.
  4. Returns a ``TestRunResult`` with parsed errors and repair
     suggestions.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from code4u.agents.healing.parser import StackTraceParser, ParsedError
from code4u.agents.healing.diagnoser import Diagnoser, Diagnosis

logger = structlog.get_logger("executor_ext")

# Well-known test commands by language/framework
_DEFAULT_COMMANDS: Dict[str, List[str]] = {
    "pytest": ["python", "-m", "pytest", "--tb=long", "-q"],
    "jest": ["npx", "jest", "--no-coverage"],
    "go": ["go", "test", "./..."],
    "npm": ["npm", "test"],
    "cargo": ["cargo", "test"],
}


@dataclass
class TestRunResult:
    """Outcome of a test runner execution."""
    command: str
    return_code: int
    stdout: str
    stderr: str
    duration_ms: float = 0.0
    errors: List[ParsedError] = field(default_factory=list)
    diagnoses: List[Diagnosis] = field(default_factory=list)
    passed: bool = False

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def fix_count(self) -> int:
        return sum(1 for d in self.diagnoses if d.has_fix)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "returnCode": self.return_code,
            "passed": self.passed,
            "durationMs": round(self.duration_ms, 1),
            "errorCount": self.error_count,
            "fixCount": self.fix_count,
            "errors": [e.to_dict() for e in self.errors],
            "diagnoses": [d.to_dict() for d in self.diagnoses],
        }


class TestRunner:
    """Runs test commands and diagnoses failures.

    Usage::

        runner = TestRunner(dep_map)
        result = runner.run("pytest", workspace="/my/project")
        if not result.passed:
            for d in result.diagnoses:
                print(d.root_cause)
                for s in d.suggestions:
                    print(f"  FIX: {s.description}")
    """

    def __init__(self, dep_map: Any = None) -> None:
        self._dep_map = dep_map
        self._parser = StackTraceParser()

    def run(
        self,
        command: str = "pytest",
        workspace: str = ".",
        timeout: int = 120,
        extra_args: Optional[List[str]] = None,
    ) -> TestRunResult:
        """Run a test command and diagnose any failures.

        Args:
            command: Test runner name or full command string.
            workspace: Working directory for the command.
            timeout: Max seconds to wait.
            extra_args: Additional arguments to pass.

        Returns:
            ``TestRunResult`` with parsed errors and diagnoses.
        """
        cmd_parts = self._resolve_command(command, extra_args)
        cmd_str = " ".join(cmd_parts)

        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd_parts,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired:
            return TestRunResult(
                command=cmd_str,
                return_code=-1,
                stdout="",
                stderr="Test command timed out",
                duration_ms=(time.monotonic() - t0) * 1000,
            )
        except FileNotFoundError:
            return TestRunResult(
                command=cmd_str,
                return_code=-1,
                stdout="",
                stderr=f"Command not found: {cmd_parts[0]}",
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        duration = (time.monotonic() - t0) * 1000

        result = TestRunResult(
            command=cmd_str,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration,
            passed=return_code == 0,
        )

        if return_code != 0:
            combined = stdout + "\n" + stderr
            result.errors = self._parser.parse(combined)

            if self._dep_map and result.errors:
                diagnoser = Diagnoser(self._dep_map)
                result.diagnoses = diagnoser.diagnose_all(result.errors)

        logger.info(
            "test_run_complete",
            command=cmd_str,
            passed=result.passed,
            errors=result.error_count,
            fixes=result.fix_count,
            duration_ms=round(duration, 1),
        )

        return result

    def diagnose_output(self, raw_output: str) -> TestRunResult:
        """Diagnose pre-captured test output without running a command.

        Useful for API endpoints that receive error output directly.
        """
        errors = self._parser.parse(raw_output)
        diagnoses = []
        if self._dep_map and errors:
            diagnoser = Diagnoser(self._dep_map)
            diagnoses = diagnoser.diagnose_all(errors)

        return TestRunResult(
            command="(pre-captured)",
            return_code=1 if errors else 0,
            stdout=raw_output,
            stderr="",
            errors=errors,
            diagnoses=diagnoses,
            passed=not errors,
        )

    def _resolve_command(
        self, command: str, extra_args: Optional[List[str]],
    ) -> List[str]:
        """Resolve a command name to its full invocation."""
        if command in _DEFAULT_COMMANDS:
            parts = list(_DEFAULT_COMMANDS[command])
        else:
            parts = command.split()

        if extra_args:
            parts.extend(extra_args)

        return parts
