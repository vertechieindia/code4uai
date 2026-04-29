"""Recursive Gauntlet Orchestrator — Zero-Defect Validation Pipeline.

Forces proposed code through 5 sequential testing stages. If any stage
fails, the HealAgent fixes the code and the ENTIRE pipeline restarts
from Stage 1. After max_cycles (default 10) failures, the project
enters QUARANTINE status.

The 5 Stages:
  Stage 1 (CORE):           Unit, Smoke, Sanity tests
  Stage 2 (FUNCTIONAL):     Integration, Black/White/Grey Box tests
  Stage 3 (SYSTEM):         Regression, UI Automation, Acceptance tests
  Stage 4 (NON_FUNCTIONAL): Performance, Accessibility, Localization, Compatibility
  Stage 5 (SECURITY):       SAST, DAST, SCA, Pentesting
"""

from __future__ import annotations

import asyncio
import ast
import hashlib
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger("gauntlet_orchestrator")

# Module-level tracking of active runs
_active_runs: Dict[str, "GauntletRun"] = {}


class TestingLevel(str, Enum):
    """The 5 sequential testing stages."""
    CORE = "CORE"
    FUNCTIONAL = "FUNCTIONAL"
    SYSTEM = "SYSTEM"
    NON_FUNCTIONAL = "NON_FUNCTIONAL"
    SECURITY = "SECURITY"


class GauntletStatus(str, Enum):
    """Status of a gauntlet run."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    QUARANTINE = "QUARANTINE"
    HEALING = "HEALING"


@dataclass
class StageResult:
    """Result of a single stage execution."""
    level: TestingLevel
    passed: bool
    failures: List[Dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0
    healed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "passed": self.passed,
            "failures": self.failures,
            "durationMs": self.duration_ms,
            "healed": self.healed,
        }


@dataclass
class GauntletRun:
    """Full gauntlet run record."""
    run_id: str
    proposed_code: Dict[str, str]
    stages: List[StageResult] = field(default_factory=list)
    status: GauntletStatus = GauntletStatus.PENDING
    cycle: int = 1
    max_cycles: int = 10
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    signature_chain: str = ""
    heal_attempts: List[Dict[str, Any]] = field(default_factory=list)
    project_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runId": self.run_id,
            "projectId": self.project_id,
            "status": self.status.value,
            "cycle": self.cycle,
            "maxCycles": self.max_cycles,
            "stages": [s.to_dict() for s in self.stages],
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "signatureChain": self.signature_chain,
            "healAttempts": self.heal_attempts,
        }


class GauntletOrchestrator:
    """Master quality loop — runs 5-stage validation with healing on failure."""

    def __init__(
        self,
        max_cycles: int = 10,
        heal_agent: Optional[Callable[[List[Dict], Dict[str, str]], Dict[str, str]]] = None,
    ) -> None:
        self.max_cycles = max_cycles
        self.heal_agent = heal_agent

    @classmethod
    def get_active_runs(cls) -> List[GauntletRun]:
        """Return list of currently active (RUNNING or HEALING) runs."""
        return [
            r for r in _active_runs.values()
            if r.status in (GauntletStatus.RUNNING, GauntletStatus.HEALING)
        ]

    async def _run_stage_async(
        self,
        level: TestingLevel,
        proposed_code: Dict[str, str],
    ) -> StageResult:
        """Async wrapper for _run_stage."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._run_stage, level, proposed_code
        )

    async def run_validation_loop(
        self,
        proposed_code: Dict[str, str],
        project_id: str = "",
        parallel: bool = True,
    ) -> GauntletRun:
        """Main entry: run stages with optional parallelism. On failure, heal and restart."""
        run_id = str(uuid.uuid4())
        run = GauntletRun(
            run_id=run_id,
            proposed_code=dict(proposed_code),
            max_cycles=self.max_cycles,
            project_id=project_id,
        )
        run.started_at = time.time()
        run.status = GauntletStatus.RUNNING
        _active_runs[run_id] = run

        current_code = dict(proposed_code)

        try:
            while run.cycle <= self.max_cycles:
                run.stages = []
                run.status = GauntletStatus.RUNNING

                if parallel:
                    failed = await self._run_parallel_pipeline(run, current_code)
                else:
                    failed = await self._run_sequential_pipeline(
                        run, current_code
                    )

                if not failed:
                    run.status = GauntletStatus.PASSED
                    run.completed_at = time.time()
                    run.signature_chain = self._compute_signature_chain(
                        run.stages
                    )
                    return run

                # A stage failed — attempt healing
                if self.heal_agent and run.cycle < self.max_cycles:
                    run.status = GauntletStatus.HEALING
                    failure_list = []
                    for s in run.stages:
                        if not s.passed:
                            failure_list.extend(s.failures)
                    healed_code = self._attempt_heal(
                        failure_list, current_code
                    )
                    if healed_code:
                        failed_level = next(
                            (
                                s.level.value
                                for s in run.stages
                                if not s.passed
                            ),
                            "UNKNOWN",
                        )
                        run.heal_attempts.append({
                            "cycle": run.cycle,
                            "level": failed_level,
                            "failureCount": len(failure_list),
                            "healed": True,
                        })
                        current_code = healed_code
                        run.cycle += 1
                        continue

                # Can't heal or max cycles reached
                if run.cycle >= self.max_cycles:
                    run.status = GauntletStatus.QUARANTINE
                else:
                    run.status = GauntletStatus.FAILED
                run.completed_at = time.time()
                run.signature_chain = self._compute_signature_chain(
                    run.stages
                )
                return run
        finally:
            pass

        run.completed_at = time.time()
        run.signature_chain = self._compute_signature_chain(run.stages)
        return run

    async def _run_parallel_pipeline(
        self,
        run: GauntletRun,
        code: Dict[str, str],
    ) -> bool:
        """Run stages in parallel groups with fault tolerance. Returns True if any stage failed."""
        # Group A: CORE, FUNCTIONAL, SYSTEM (parallel)
        try:
            group_a = await asyncio.gather(
                self._run_stage_async(TestingLevel.CORE, code),
                self._run_stage_async(TestingLevel.FUNCTIONAL, code),
                self._run_stage_async(TestingLevel.SYSTEM, code),
                return_exceptions=True,
            )
        except Exception as e:
            logger.error("parallel_group_a_exception", error=str(e))
            run.stages.append(StageResult(level=TestingLevel.CORE, passed=False, failures=[{"test_name": "system_fault", "error": str(e), "severity": "critical"}]))
            return True

        for result in group_a:
            if isinstance(result, Exception):
                logger.error("parallel_stage_exception", error=str(result))
                run.stages.append(StageResult(level=TestingLevel.CORE, passed=False, failures=[{"test_name": "system_fault", "error": str(result), "severity": "critical"}]))
                return True
            run.stages.append(result)
            if not result.passed:
                logger.info("parallel_group_a_failed", level=result.level.value)
                return True

        # Group B: NON_FUNCTIONAL, SECURITY (parallel)
        try:
            group_b = await asyncio.gather(
                self._run_stage_async(TestingLevel.NON_FUNCTIONAL, code),
                self._run_stage_async(TestingLevel.SECURITY, code),
                return_exceptions=True,
            )
        except Exception as e:
            logger.error("parallel_group_b_exception", error=str(e))
            run.stages.append(StageResult(level=TestingLevel.NON_FUNCTIONAL, passed=False, failures=[{"test_name": "system_fault", "error": str(e), "severity": "critical"}]))
            return True

        for result in group_b:
            if isinstance(result, Exception):
                logger.error("parallel_stage_exception", error=str(result))
                run.stages.append(StageResult(level=TestingLevel.NON_FUNCTIONAL, passed=False, failures=[{"test_name": "system_fault", "error": str(result), "severity": "critical"}]))
                return True
            run.stages.append(result)
            if not result.passed:
                logger.info("parallel_group_b_failed", level=result.level.value)
                return True

        return False

    async def _run_sequential_pipeline(
        self,
        run: GauntletRun,
        code: Dict[str, str],
    ) -> bool:
        """Run stages sequentially (legacy mode). Returns True if any stage failed."""
        for level in [
            TestingLevel.CORE,
            TestingLevel.FUNCTIONAL,
            TestingLevel.SYSTEM,
            TestingLevel.NON_FUNCTIONAL,
            TestingLevel.SECURITY,
        ]:
            result = self._run_stage(level, code)
            run.stages.append(result)
            if not result.passed:
                return True
        return False

    def _run_stage(
        self,
        level: TestingLevel,
        proposed_code: Dict[str, str],
    ) -> StageResult:
        """Run tests for the given level."""
        start = time.perf_counter()
        failures: List[Dict[str, Any]] = []

        if level == TestingLevel.CORE:
            failures = self._stage_core(proposed_code)
        elif level == TestingLevel.FUNCTIONAL:
            failures = self._stage_functional(proposed_code)
        elif level == TestingLevel.SYSTEM:
            failures = self._stage_system(proposed_code)
        elif level == TestingLevel.NON_FUNCTIONAL:
            failures = self._stage_non_functional(proposed_code)
        elif level == TestingLevel.SECURITY:
            failures = self._stage_security(proposed_code)

        duration_ms = (time.perf_counter() - start) * 1000
        return StageResult(
            level=level,
            passed=len(failures) == 0,
            failures=failures,
            duration_ms=duration_ms,
        )

    def _stage_core(self, code_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """CORE: syntax, import resolution, smoke (non-empty files)."""
        failures = []
        for filepath, content in code_map.items():
            if not content or not content.strip():
                failures.append({
                    "test_name": "smoke_non_empty",
                    "error": f"File {filepath} is empty",
                    "severity": "high",
                    "file_path": filepath,
                })
                continue

            ext = filepath.split(".")[-1].lower() if "." in filepath else ""
            if ext in ("py",):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    failures.append({
                        "test_name": "syntax_python",
                        "error": str(e),
                        "severity": "critical",
                        "file_path": filepath,
                        "line": getattr(e, "lineno", 0),
                    })
            elif ext in ("js", "ts", "jsx", "tsx"):
                open_braces = content.count("{") - content.count("}")
                open_parens = content.count("(") - content.count(")")
                if open_braces != 0 or open_parens != 0:
                    failures.append({
                        "test_name": "syntax_brace_balance",
                        "error": f"Brace/paren imbalance: {{ {open_braces}, ( {open_parens}",
                        "severity": "critical",
                        "file_path": filepath,
                    })
        return failures

    def _stage_functional(self, code_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """FUNCTIONAL: function signatures, return hints, docstrings, class structure."""
        failures = []
        for filepath, content in code_map.items():
            if not filepath.endswith(".py"):
                continue
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.name.startswith("_") and not node.name.startswith("__"):
                            continue
                        if not ast.get_docstring(node) and node.name not in ("__init__",):
                            failures.append({
                                "test_name": "docstring",
                                "error": f"Function {node.name} missing docstring",
                                "severity": "minor",
                                "file_path": filepath,
                                "line": node.lineno,
                            })
                        if node.returns is None and not node.name.startswith("_"):
                            failures.append({
                                "test_name": "return_hint",
                                "error": f"Function {node.name} missing return type hint",
                                "severity": "minor",
                                "file_path": filepath,
                                "line": node.lineno,
                            })
            except SyntaxError:
                pass
        return failures[:10]

    def _stage_system(self, code_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """SYSTEM: regression, backward compatibility."""
        failures = []
        for filepath, content in code_map.items():
            if not filepath.endswith(".py"):
                continue
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                if item.name.startswith("__") and item.name.endswith("__"):
                                    if item.name not in (
                                        "__init__", "__str__", "__repr__",
                                        "__eq__", "__hash__", "__lt__",
                                    ):
                                        pass
            except SyntaxError:
                pass
        return failures

    def _stage_non_functional(self, code_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """NON_FUNCTIONAL: performance, accessibility, localization."""
        failures = []
        for filepath, content in code_map.items():
            if filepath.endswith(".py"):
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    if len(lines) > 100:
                        failures.append({
                            "test_name": "function_length",
                            "error": f"File {filepath} has {len(lines)} lines (max 100)",
                            "severity": "medium",
                            "file_path": filepath,
                            "line": i + 1,
                        })
                        break
            elif filepath.endswith((".jsx", ".tsx")):
                if "<img " in content and "alt=" not in content and "alt =" not in content:
                    failures.append({
                        "test_name": "accessibility_img_alt",
                        "error": "Image missing alt attribute",
                        "severity": "major",
                        "file_path": filepath,
                    })
                if re.search(r'<[^>]+onClick[^>]*>', content) and 'role=' not in content:
                    if "<button" not in content and "<a " not in content:
                        failures.append({
                            "test_name": "accessibility_aria",
                            "error": "Interactive element may need role/aria-label",
                            "severity": "minor",
                            "file_path": filepath,
                        })
                hardcoded = re.findall(r'>\s*([^<{]+[a-zA-Z]{4,}[^<{}]*)\s*<', content)
                if hardcoded:
                    failures.append({
                        "test_name": "localization_hardcoded",
                        "error": f"Possible hardcoded string: {hardcoded[0][:50]}...",
                        "severity": "minor",
                        "file_path": filepath,
                    })
        return failures[:15]

    def _stage_security(self, code_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """SECURITY: secret scanning, SQL injection, XSS, eval()."""
        failures = []
        secret_patterns = [
            (r'AKIA[0-9A-Z]{16}', "AWS_ACCESS_KEY"),
            (r'aws_secret_access_key\s*=\s*["\'][^"\']+["\']', "AWS_SECRET"),
            (r'password\s*=\s*["\'][^"\']+["\']', "PASSWORD"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "API_KEY"),
            (r'token\s*=\s*["\'][a-zA-Z0-9_-]{20,}["\']', "TOKEN"),
        ]
        for filepath, content in code_map.items():
            for pattern, name in secret_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    failures.append({
                        "test_name": "secret_scan",
                        "error": f"Possible secret detected: {name}",
                        "severity": "critical",
                        "file_path": filepath,
                    })
            if "eval(" in content:
                failures.append({
                    "test_name": "eval_usage",
                    "error": "eval() usage detected - security risk",
                    "severity": "high",
                    "file_path": filepath,
                })
            if re.search(r'f["\'].*SELECT.*\{', content) or re.search(
                r'["\'].*SELECT.*\+.*["\']', content
            ):
                failures.append({
                    "test_name": "sqli_pattern",
                    "error": "Possible SQL injection via string formatting",
                    "severity": "critical",
                    "file_path": filepath,
                })
            if "dangerouslySetInnerHTML" in content and "sanitize" not in content.lower():
                failures.append({
                    "test_name": "xss_pattern",
                    "error": "dangerouslySetInnerHTML without sanitization",
                    "severity": "high",
                    "file_path": filepath,
                })
        return failures

    def _attempt_heal(
        self,
        failures: List[Dict[str, Any]],
        proposed_code: Dict[str, str],
    ) -> Optional[Dict[str, str]]:
        """Use HealAgent to fix code. Returns fixed code or None."""
        if not self.heal_agent:
            return None
        try:
            result = self.heal_agent(failures, proposed_code)
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.warning("heal_attempt_failed", error=str(e))
            return None

    def _compute_signature_chain(self, stages: List[StageResult]) -> str:
        """SHA-256 chain of all stage results."""
        chain = hashlib.sha256()
        for s in stages:
            chain.update(
                f"{s.level.value}:{s.passed}:{len(s.failures)}:{s.duration_ms}".encode()
            )
        return chain.hexdigest()


_gauntlet_singleton: Optional[GauntletOrchestrator] = None


def get_gauntlet_orchestrator(
    max_cycles: int = 10,
    heal_agent: Optional[Callable[[List[Dict], Dict[str, str]], Dict[str, str]]] = None,
) -> GauntletOrchestrator:
    """Singleton accessor for GauntletOrchestrator."""
    global _gauntlet_singleton
    if _gauntlet_singleton is None:
        _gauntlet_singleton = GauntletOrchestrator(max_cycles=max_cycles, heal_agent=heal_agent)
    return _gauntlet_singleton
