from __future__ import annotations
"""Agent orchestrator for code4u.ai.

Provides two orchestration paths:
  1. PlanExecutor  — Runs a locked ExecutionPlan through a strict state machine.
     Used by the refactor API (Golden Path).
  2. AgentOrchestrator — Legacy multi-agent pipeline (planner → verifier).
     Not used by the refactor API today.

Day 3 additions:
  - ProposedPlan simulation: GENERATE_CODE now builds a structured
    ``ProposedPlan`` (edits / creates / deletes) *before* anything
    touches disk.
  - Complex intent handling: "Extract to file" and "Convert to class"
    are recognised and handled via DependencyMap + AST.
  - Dry-run validation: every proposed file is syntax-checked in memory
    (``ast.parse`` for Python, brace-balance for JS/TS) before APPLY.
"""

import ast
import asyncio
import difflib
import re
import textwrap
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from code4u.platform_core.agents.base import (
    Agent,
    AgentContext,
    AgentResult,
    AgentStatus,
)
from code4u.platform_core.agents.errors import PipelineIncompleteError
from code4u.platform_core.agents.proposed_plan import (
    FileOperation,
    ProposedPlan,
    INTENT_RENAME,
    INTENT_EXTRACT,
    INTENT_CONVERT_TO_CLASS,
    INTENT_UI_LAYOUT,
    INTENT_OPTIMIZE,
    INTENT_UPGRADE_LIBRARY,
    INTENT_DEPLOY,
    INTENT_GENERIC,
)
from code4u.platform_core.state_machine.plan_states import (
    PlanExecutionState,
    PlanStateViolation,
    can_transition,
)
from code4u.code_intelligence.context.compiler import (
    RefactorContext,
    RefactorBlastContext,
)
from code4u.code_intelligence.context.planner import (
    plan_refactor,
    ExecutionPlan,
    ExecutionStep,
)
from code4u.ai_engine.llm.executor import LLMExecutor


# ---------------------------------------------------------------------------
# Mapping: step kind → next PlanExecutionState
# ---------------------------------------------------------------------------

_KIND_TO_NEXT_STATE: Dict[str, PlanExecutionState] = {
    "GENERATE_CODE": PlanExecutionState.CODE_GENERATED,
    "VALIDATE_CODE": PlanExecutionState.CODE_VALIDATED,
    "PREVIEW_DIFF": PlanExecutionState.DIFF_PREVIEWED,
    "APPLY_DIFF": PlanExecutionState.APPLIED,
}


# ---------------------------------------------------------------------------
# StateHistoryEntry — immutable record of a single transition
# ---------------------------------------------------------------------------

class StateHistoryEntry:
    """Single entry in the execution state history timeline."""

    __slots__ = ("from_state", "to_state", "step_kind", "timestamp_ms")

    def __init__(
        self,
        from_state: str,
        to_state: str,
        step_kind: Optional[str],
        timestamp_ms: float,
    ) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.step_kind = step_kind
        self.timestamp_ms = timestamp_ms

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for JSON responses."""
        return {
            "from": self.from_state,
            "to": self.to_state,
            "stepKind": self.step_kind,
            "timestampMs": self.timestamp_ms,
        }


# ---------------------------------------------------------------------------
# PlanExecutor — the Golden-Path execution engine
# ---------------------------------------------------------------------------

class PlanExecutor:
    """Execute an ``ExecutionPlan`` through a locked state machine.

    Lifecycle (happy path)::

        INIT → PLAN_READY → CODE_GENERATED → CODE_VALIDATED
             → DIFF_PREVIEWED → APPLIED

    On any failure the state transitions to ``FAILED`` and the original
    exception is re-raised.  The ``APPLY_DIFF`` handler backs up every
    target file *before* writing; on a write failure it restores **only**
    the files that were actually modified.

    Day 3: the GENERATE_CODE step now produces a ``ProposedPlan`` that
    describes every file operation (edit / create / delete) in advance.
    VALIDATE_CODE syntax-checks all proposed content in memory.
    APPLY_DIFF handles file creation and deletion with full rollback.

    Attributes:
        execution_id: Unique identifier for this execution run.
        state: Current ``PlanExecutionState``.
        state_history: Ordered list of ``StateHistoryEntry`` objects.
        diffs: Mapping ``file_path → unified-diff`` (populated by PREVIEW_DIFF).
        proposed_plan: The ``ProposedPlan`` (populated after GENERATE_CODE).
        last_error: The exception that caused ``FAILED``, if any.
    """

    def __init__(
        self,
        llm_executor: Optional[LLMExecutor] = None,
        dependency_map: Optional[Any] = None,
        dry_run: bool = False,
        status_callback: Optional[Any] = None,
    ) -> None:
        self._state: PlanExecutionState = PlanExecutionState.INIT
        self._last_error: Optional[BaseException] = None
        self._plan: Optional[ExecutionPlan] = None
        self._context: Optional[RefactorBlastContext] = None
        self._intent: str = ""
        self._generated_code: Dict[str, str] = {}
        self._diffs: Dict[str, str] = {}
        self._original_code: Dict[str, str] = {}
        self._state_history: List[StateHistoryEntry] = []
        self._current_step_kind: Optional[str] = None
        self._execution_id: str = ""
        self._llm: LLMExecutor = llm_executor or LLMExecutor()
        self._dep_map = dependency_map
        self._dry_run: bool = dry_run
        self._proposed_plan: Optional[ProposedPlan] = None
        self._status_callback = status_callback
        self.logger = __import__("structlog").get_logger("plan_executor")

    def _emit(self, event_type: str, message: str, **extra: Any) -> None:
        """Push a progress event to the status callback, if one is set."""
        if self._status_callback is None:
            return
        payload = {
            "type": event_type,
            "message": message,
            "state": self._state.value,
            "executionId": self._execution_id,
            **extra,
        }
        try:
            self._status_callback(payload)
        except Exception:
            pass

    # -- public read-only accessors ----------------------------------------

    @property
    def execution_id(self) -> str:
        """Unique identifier for the current (or last) execution run."""
        return self._execution_id

    @property
    def state(self) -> PlanExecutionState:
        """Current state machine position."""
        return self._state

    @property
    def state_history(self) -> List[StateHistoryEntry]:
        """Ordered list of every state transition that occurred."""
        return list(self._state_history)

    @property
    def diffs(self) -> Dict[str, str]:
        """File-path → unified-diff mapping (populated after PREVIEW_DIFF)."""
        return dict(self._diffs)

    @property
    def last_error(self) -> Optional[BaseException]:
        """The exception that caused FAILED, or ``None``."""
        return self._last_error

    @property
    def proposed_plan(self) -> Optional[ProposedPlan]:
        """The ``ProposedPlan`` built during GENERATE_CODE, or ``None``."""
        return self._proposed_plan

    @property
    def is_dry_run(self) -> bool:
        """Whether this executor is in dry-run mode (no disk writes)."""
        return self._dry_run

    # -- state machine helpers ---------------------------------------------

    def _transition(self, to: PlanExecutionState) -> None:
        """Advance the state machine and record the transition.

        Args:
            to: Target state.

        Raises:
            PlanStateViolation: If the transition is not allowed.
        """
        if not can_transition(self._state, to):
            raise PlanStateViolation(self._state, to)
        entry = StateHistoryEntry(
            from_state=self._state.value,
            to_state=to.value,
            step_kind=self._current_step_kind,
            timestamp_ms=time.time() * 1000,
        )
        self._state_history.append(entry)
        self._state = to

    # -- file I/O helpers --------------------------------------------------

    def _read_file_from_disk(self, file_path: str) -> str:
        """Read UTF-8 file content from *file_path*.

        Args:
            file_path: Absolute or relative path.

        Returns:
            The file contents as a string.

        Raises:
            FileNotFoundError: If *file_path* does not exist.
            ValueError: If *file_path* is not a regular file.
        """
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not p.is_file():
            raise ValueError(f"Not a file: {file_path}")
        return p.read_text(encoding="utf-8")

    def _write_file_to_disk(self, file_path: str, content: str) -> None:
        """Write *content* to *file_path* as UTF-8.

        Args:
            file_path: Target path on disk.
            content: Full file content to write.

        Raises:
            OSError: On any write failure.
        """
        Path(file_path).write_text(content, encoding="utf-8")

    # -- Intent detection ----------------------------------------------------

    @staticmethod
    def _parse_rename_intent(intent: str) -> Optional[Tuple[str, str]]:
        """Extract (old_name, new_name) from a rename intent string.

        Supports formats like ``"Rename foo to bar"`` (case-insensitive).
        Returns ``None`` if the intent is not a rename.
        """
        match = re.match(
            r"(?i)rename\s+(\w+)\s+to\s+(\w+)", intent.strip()
        )
        if match:
            return match.group(1), match.group(2)
        return None

    @staticmethod
    def _parse_extract_intent(intent: str) -> Optional[Tuple[str, str]]:
        """Extract (symbol_name, target_file) from an extract intent.

        Supported patterns::

            "Extract calculate_total to math_utils.py"
            "Extract calculate_total into math_utils.py"
            "Move calculate_total to a new file math_utils.py"
            "Extract calculate_total to a new file called math_utils.py"

        Returns ``None`` if the intent is not an extract.
        """
        patterns = [
            r"(?i)(?:extract|move)\s+(\w+)\s+(?:to|into)\s+(?:a\s+)?(?:new\s+)?(?:file\s+)?(?:called\s+)?(\S+\.(?:py|ts|tsx|js|jsx))",
            r"(?i)(?:extract|move)\s+(\w+)\s+(?:to|into)\s+(\w+)",
        ]
        for pattern in patterns:
            m = re.match(pattern, intent.strip())
            if m:
                symbol = m.group(1)
                target = m.group(2)
                if not target.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                    target += ".py"
                return symbol, target
        return None

    @staticmethod
    def _parse_convert_to_class_intent(intent: str) -> Optional[str]:
        """Extract symbol_name from a convert-to-class intent.

        Supported patterns::

            "Convert calculate_total to a class"
            "Convert calculate_total to class-based structure"
            "Turn calculate_total into a class"

        Returns ``None`` if the intent is not a convert-to-class.
        """
        patterns = [
            r"(?i)(?:convert|turn|change|transform)\s+(\w+)\s+(?:to|into)\s+(?:a\s+)?class",
        ]
        for pattern in patterns:
            m = re.match(pattern, intent.strip())
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _is_ui_layout_intent(intent: str) -> bool:
        """Detect if the intent is a UI/layout change."""
        lower = intent.lower()
        if lower.startswith("[ui layout]"):
            return True
        ui_patterns = [
            r"(?i)(?:move|shift|rearrange|reposition)\s+(?:the\s+)?(?:sidebar|header|footer|navbar|nav|menu|panel|layout)",
            r"(?i)(?:make\s+it\s+look|redesign|restyle|change\s+the\s+layout)",
            r"(?i)(?:css|style|layout)\s+(?:change|update|fix|refactor)",
            r"(?i)(?:swap|flip|mirror)\s+(?:the\s+)?(?:left|right|top|bottom)",
        ]
        return any(re.search(p, intent) for p in ui_patterns)

    def _classify_intent(self, intent: str) -> str:
        """Classify the user intent into one of the known types."""
        if self._parse_rename_intent(intent) is not None:
            return INTENT_RENAME
        if self._parse_extract_intent(intent) is not None:
            return INTENT_EXTRACT
        if self._parse_convert_to_class_intent(intent) is not None:
            return INTENT_CONVERT_TO_CLASS
        if self._is_ui_layout_intent(intent):
            return INTENT_UI_LAYOUT
        if self._is_optimize_intent(intent):
            return INTENT_OPTIMIZE
        if self._is_upgrade_library_intent(intent):
            return INTENT_UPGRADE_LIBRARY
        if self._is_deploy_intent(intent):
            return INTENT_DEPLOY
        return INTENT_GENERIC

    def _is_upgrade_library_intent(self, intent: str) -> bool:
        """Check if the intent is about library/dependency upgrades."""
        patterns = [
            r"upgrade[\s-]?librar",
            r"update[\s-]?(?:dependenc|package|module)",
            r"migrat",
            r"bump\s+version",
            r"upgrade\s+\w+\s+(?:to|from)",
            r"update\s+\w+\s+(?:to|from)",
            r"upgrade-library",
            r"replace\s+\w+\s+with",
        ]
        return any(re.search(p, intent, re.IGNORECASE) for p in patterns)

    def _is_optimize_intent(self, intent: str) -> bool:
        """Check if the intent is about performance optimization."""
        optimize_patterns = [
            r"optimi[zs]e",
            r"speed\s*up",
            r"faster",
            r"performance",
            r"profil",
            r"bottleneck",
            r"slow",
            r"O\(n",
            r"complexity",
            r"n\+1",
            r"memoiz",
            r"cach",
        ]
        return any(re.search(p, intent, re.IGNORECASE) for p in optimize_patterns)

    def _is_deploy_intent(self, intent: str) -> bool:
        """Check if the intent is about deployment or CI/CD pipeline generation."""
        deploy_patterns = [
            r"deploy",
            r"ci/?cd",
            r"pipeline",
            r"github\s*action",
            r"gitlab[\s-]?ci",
            r"ship\s+to",
            r"push\s+to\s+(?:staging|production|prod)",
            r"release",
            r"publish",
            r"continuous\s+(?:integration|delivery|deployment)",
        ]
        return any(re.search(p, intent, re.IGNORECASE) for p in deploy_patterns)

    def _apply_mechanical_rename(
        self, content: str, old_name: str, new_name: str
    ) -> str:
        r"""Replace all whole-word occurrences of *old_name* with *new_name*.

        Uses ``\b`` word boundaries so partial matches inside longer
        identifiers are not replaced.
        """
        return re.sub(rf"\b{re.escape(old_name)}\b", new_name, content)

    # -- GENERATE_CODE -----------------------------------------------------

    def _build_generate_code_prompt(
        self, file_path: str, original_content: str
    ) -> str:
        """Build the LLM instruction for a single file."""
        symbol_name = self._context.symbol.name if self._context else ""
        return (
            f"Refactor symbol '{symbol_name}'. "
            "Return the complete file content only, no explanation."
        )

    def _build_convert_to_class_prompt(
        self, symbol_name: str, file_path: str, original_content: str
    ) -> str:
        """Build LLM instruction for converting a function to a class."""
        return (
            f"Convert the function '{symbol_name}' in this file into a "
            f"class-based structure. The class should be named "
            f"'{symbol_name.title().replace('_', '')}' with the original "
            f"function logic in a method. Update any internal references. "
            f"Return the complete file content only, no explanation."
        )

    # -- Extract-to-file (mechanical, no LLM) --------------------------------

    def _extract_function_source(
        self, content: str, symbol_name: str
    ) -> Tuple[str, int, int, List[str]]:
        """Extract a function's source, line range, and its imports from a Python file.

        Returns (function_source, start_line, end_line, needed_imports)
        where needed_imports are the import lines found in the file.
        """
        tree = ast.parse(content)
        lines = content.splitlines(keepends=True)

        func_node: Optional[ast.AST] = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == symbol_name:
                    func_node = node
                    break

        if func_node is None:
            raise ValueError(
                f"Function '{symbol_name}' not found in file"
            )

        start = func_node.lineno - 1
        end = getattr(func_node, "end_lineno", func_node.lineno)
        func_lines = lines[start:end]
        func_source = "".join(func_lines)

        import_lines: List[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imp_start = node.lineno - 1
                imp_end = getattr(node, "end_lineno", node.lineno)
                import_lines.append("".join(lines[imp_start:imp_end]))

        return func_source, start + 1, end, import_lines

    def _remove_function_from_source(
        self, content: str, symbol_name: str
    ) -> str:
        """Remove a function definition from Python source code."""
        tree = ast.parse(content)
        lines = content.splitlines(keepends=True)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == symbol_name:
                    start = node.lineno - 1
                    end = getattr(node, "end_lineno", node.lineno)
                    # Remove blank lines before the function (decorators, etc.)
                    while start > 0 and lines[start - 1].strip() == "":
                        start -= 1
                    del lines[start:end]
                    break

        return "".join(lines)

    def _update_import_in_caller(
        self,
        content: str,
        symbol_name: str,
        old_module: str,
        new_module: str,
    ) -> str:
        """Rewrite ``from old_module import symbol_name`` to use new_module."""
        pattern = re.compile(
            rf"^(from\s+){re.escape(old_module)}(\s+import\s+.*\b{re.escape(symbol_name)}\b.*)$",
            re.MULTILINE,
        )

        def _rewrite(m: re.Match) -> str:
            full_line = m.group(0)
            import_part = m.group(2)
            names = [
                n.strip()
                for n in import_part.split("import", 1)[1].split(",")
            ]
            remaining = [n for n in names if n != symbol_name]

            new_import = f"from {new_module} import {symbol_name}"
            if remaining:
                old_import = f"from {old_module} import {', '.join(remaining)}"
                return f"{old_import}\n{new_import}"
            return new_import

        return pattern.sub(_rewrite, content)

    def _infer_module_name(self, file_path: str) -> str:
        """Infer a Python module name from a file path (stem only)."""
        return Path(file_path).stem

    async def _build_extract_plan(
        self, symbol_name: str, target_file_name: str, step: ExecutionStep
    ) -> ProposedPlan:
        """Build a ProposedPlan for extracting a symbol to a new file."""
        assert self._context is not None
        defining_file = self._context.defining_file
        original_content = self._read_file_from_disk(defining_file)

        func_source, _start, _end, import_lines = self._extract_function_source(
            original_content, symbol_name
        )

        # Build new file content
        target_dir = str(Path(defining_file).parent)
        target_path = str(Path(target_dir) / target_file_name)
        new_module = self._infer_module_name(target_path)
        old_module = self._infer_module_name(defining_file)

        new_file_parts: List[str] = []
        if import_lines:
            new_file_parts.extend(import_lines)
            if not import_lines[-1].endswith("\n"):
                new_file_parts.append("\n")
            new_file_parts.append("\n")
        new_file_parts.append(func_source)
        if not func_source.endswith("\n"):
            new_file_parts.append("\n")
        new_file_content = "".join(new_file_parts)

        # Update defining file: remove function, add import from new module
        updated_source = self._remove_function_from_source(
            original_content, symbol_name
        )
        re_import_line = f"from {new_module} import {symbol_name}\n"
        if re_import_line.strip() not in updated_source:
            insert_pos = 0
            src_lines = updated_source.splitlines(keepends=True)
            for i, line in enumerate(src_lines):
                if line.startswith(("import ", "from ")):
                    insert_pos = i + 1
            src_lines.insert(insert_pos, re_import_line)
            updated_source = "".join(src_lines)

        operations: List[FileOperation] = [
            FileOperation(
                file_path=target_path,
                action="create",
                content=new_file_content,
                original_content="",
                reason=f"New file with extracted function '{symbol_name}'",
            ),
            FileOperation(
                file_path=defining_file,
                action="edit",
                content=updated_source,
                original_content=original_content,
                reason=f"Remove '{symbol_name}' (moved to {target_file_name})",
            ),
        ]

        # Update callers
        for file_path in step.files:
            if file_path == defining_file:
                continue
            caller_content = self._read_file_from_disk(file_path)
            updated_caller = self._update_import_in_caller(
                caller_content, symbol_name, old_module, new_module
            )
            if updated_caller != caller_content:
                operations.append(FileOperation(
                    file_path=file_path,
                    action="edit",
                    content=updated_caller,
                    original_content=caller_content,
                    reason=f"Update import: '{symbol_name}' now in {target_file_name}",
                ))

        return ProposedPlan(
            intent=self._intent,
            intent_type=INTENT_EXTRACT,
            operations=operations,
        )

    # -- Convert-to-class (LLM-assisted) ------------------------------------

    async def _build_convert_to_class_plan(
        self, symbol_name: str, step: ExecutionStep
    ) -> ProposedPlan:
        """Build a ProposedPlan for converting a function to a class."""
        assert self._context is not None
        defining_file = self._context.defining_file
        original_content = self._read_file_from_disk(defining_file)

        instruction = self._build_convert_to_class_prompt(
            symbol_name, defining_file, original_content
        )
        generated = await self._llm.execute_refactor_simple(
            original_content, instruction
        )
        if not isinstance(generated, str) or not generated.strip():
            raise ValueError(
                f"LLM returned empty content for convert-to-class on {defining_file!r}"
            )

        operations: List[FileOperation] = [
            FileOperation(
                file_path=defining_file,
                action="edit",
                content=generated,
                original_content=original_content,
                reason=f"Convert '{symbol_name}' to class-based structure",
            ),
        ]

        # For callers, the LLM needs to update how they call the symbol.
        # Use a second LLM call per caller, or mechanical update.
        class_name = symbol_name.title().replace("_", "")
        for file_path in step.files:
            if file_path == defining_file:
                continue
            caller_content = self._read_file_from_disk(file_path)
            caller_instruction = (
                f"The function '{symbol_name}' has been converted to a class "
                f"named '{class_name}'. Update this file's imports and usage. "
                f"Return the complete file content only, no explanation."
            )
            updated = await self._llm.execute_refactor_simple(
                caller_content, caller_instruction
            )
            if isinstance(updated, str) and updated.strip():
                operations.append(FileOperation(
                    file_path=file_path,
                    action="edit",
                    content=updated,
                    original_content=caller_content,
                    reason=f"Update usage: '{symbol_name}' is now class '{class_name}'",
                ))

        return ProposedPlan(
            intent=self._intent,
            intent_type=INTENT_CONVERT_TO_CLASS,
            operations=operations,
        )

    # -- Rename plan (mechanical) -------------------------------------------

    def _build_rename_plan(
        self, old_name: str, new_name: str, step: ExecutionStep
    ) -> ProposedPlan:
        """Build a ProposedPlan for a mechanical rename."""
        operations: List[FileOperation] = []
        for file_path in step.files:
            original = self._read_file_from_disk(file_path)
            updated = self._apply_mechanical_rename(original, old_name, new_name)
            operations.append(FileOperation(
                file_path=file_path,
                action="edit",
                content=updated,
                original_content=original,
                reason=f"Rename '{old_name}' → '{new_name}'",
            ))
        return ProposedPlan(
            intent=self._intent,
            intent_type=INTENT_RENAME,
            operations=operations,
        )

    # -- Generic plan (LLM with context-aware hunk editing) -----------------

    async def _build_generic_plan(self, step: ExecutionStep) -> ProposedPlan:
        """Build a ProposedPlan using context-aware LLM refactoring.

        For the defining file, this uses hunk-based editing:
          1. The context builder sends the target symbol + its callers
             (from DependencyMap) to the LLM.
          2. The LLM returns specific code hunks (line ranges + replacement).
          3. The hunk parser merges them into the original file in memory.

        For caller files, changes are only made if the LLM explicitly
        says the callers need updating (rare for logic-only changes).
        """
        assert self._context is not None
        defining_file = self._context.defining_file
        symbol_name = self._context.symbol.name
        language = self._context.symbol.language

        caller_files = [
            f for f in step.files if f != defining_file
        ]

        if self._dep_map is not None:
            dep_callers = self._dep_map.get_dependents(symbol_name)
            for cf in dep_callers:
                if cf not in caller_files and cf != defining_file:
                    caller_files.append(cf)

        original = self._read_file_from_disk(defining_file)

        hunk_result = await self._llm.execute_refactor_with_context(
            intent=self._intent,
            file_path=defining_file,
            file_content=original,
            symbol_name=symbol_name,
            language=language,
            caller_files=caller_files,
        )

        if not hunk_result.success:
            raise ValueError(
                f"LLM hunk parsing failed for {defining_file!r}: "
                f"{hunk_result.error}"
            )

        operations: List[FileOperation] = []

        if hunk_result.merged_content != original:
            explanations = [h.explanation for h in hunk_result.hunks if h.explanation]
            reason = "; ".join(explanations) if explanations else f"Refactor per intent: {self._intent}"
            operations.append(FileOperation(
                file_path=defining_file,
                action="edit",
                content=hunk_result.merged_content,
                original_content=original,
                reason=reason,
            ))

        self.logger.info(
            "generic_plan_built",
            symbol=symbol_name,
            hunks_applied=len(hunk_result.hunks),
            callers_in_context=len(caller_files),
            operations=len(operations),
            provider=getattr(self._llm, "client", None) and getattr(self._llm.client, "provider", "unknown"),
        )

        return ProposedPlan(
            intent=self._intent,
            intent_type=INTENT_GENERIC,
            operations=operations,
        )

    # -- UI Layout plan (LLM-assisted, prioritises .tsx/.jsx/.css) ----------

    _UI_FILE_EXTENSIONS = frozenset({".tsx", ".jsx", ".css", ".scss", ".vue", ".svelte", ".html"})

    async def _build_ui_layout_plan(self, step: ExecutionStep) -> ProposedPlan:
        """Build a ProposedPlan for a UI layout change.

        Filters affected files to those with UI-related extensions and
        delegates to the LLM with a layout-specific instruction.
        """
        assert self._context is not None
        defining_file = self._context.defining_file
        symbol_name = self._context.symbol.name
        language = self._context.symbol.language

        intent_clean = re.sub(r"^\[UI Layout\]\s*", "", self._intent, flags=re.IGNORECASE)

        ui_files = [
            f for f in step.files
            if Path(f).suffix.lower() in self._UI_FILE_EXTENSIONS
        ]
        if not ui_files:
            ui_files = list(step.files)

        if defining_file not in ui_files:
            ui_files.insert(0, defining_file)

        operations: List[FileOperation] = []

        for file_path in ui_files:
            try:
                original = self._read_file_from_disk(file_path)
            except FileNotFoundError:
                continue

            instruction = (
                f"Apply this UI layout change: '{intent_clean}'. "
                f"Focus on layout, styling, and component structure. "
                f"Return the complete file content only, no explanation."
            )

            generated = await self._llm.execute_refactor_simple(
                original, instruction
            )

            if isinstance(generated, str) and generated.strip() and generated != original:
                operations.append(FileOperation(
                    file_path=file_path,
                    action="edit",
                    content=generated,
                    original_content=original,
                    reason=f"UI layout change: {intent_clean[:80]}",
                ))

        self.logger.info(
            "ui_layout_plan_built",
            ui_files=len(ui_files),
            operations=len(operations),
        )

        return ProposedPlan(
            intent=self._intent,
            intent_type=INTENT_UI_LAYOUT,
            operations=operations,
        )

    # -- Main GENERATE_CODE handler -----------------------------------------

    async def _handle_generate_code(self, step: ExecutionStep) -> None:
        """Generate a ``ProposedPlan`` for the refactoring operation.

        Classifies the intent and delegates to the appropriate plan builder:
          - Rename → mechanical word-boundary replacement.
          - Extract → AST-based function extraction + caller update.
          - Convert-to-class → LLM-assisted conversion.
          - Generic → LLM per file.

        The resulting ``ProposedPlan`` is stored in ``self._proposed_plan``
        and individual file contents are mirrored to ``self._generated_code``
        for backward compatibility.
        """
        assert step.kind == "GENERATE_CODE", f"Expected GENERATE_CODE, got {step.kind!r}"
        assert self._context is not None, "context is required"
        assert self._context.is_complete is True, "context.is_complete must be True"

        intent_type = self._classify_intent(self._intent)
        self.logger.info("intent_classified", intent_type=intent_type, intent=self._intent)
        self._emit("generate", f"Intent classified as '{intent_type}'", intentType=intent_type)

        if intent_type == INTENT_RENAME:
            rename_pair = self._parse_rename_intent(self._intent)
            assert rename_pair is not None
            plan = self._build_rename_plan(rename_pair[0], rename_pair[1], step)

        elif intent_type == INTENT_EXTRACT:
            extract_pair = self._parse_extract_intent(self._intent)
            assert extract_pair is not None
            symbol_name, target_file = extract_pair
            plan = await self._build_extract_plan(symbol_name, target_file, step)

        elif intent_type == INTENT_CONVERT_TO_CLASS:
            symbol_name = self._parse_convert_to_class_intent(self._intent)
            assert symbol_name is not None
            plan = await self._build_convert_to_class_plan(symbol_name, step)

        elif intent_type == INTENT_UI_LAYOUT:
            plan = await self._build_ui_layout_plan(step)

        else:
            plan = await self._build_generic_plan(step)

        self._proposed_plan = plan
        self._generated_code = {
            op.file_path: op.content
            for op in plan.operations
            if op.action in ("edit", "create")
        }
        affected = [op.file_path for op in plan.operations]
        self._emit(
            "generate_complete",
            f"Plan generated: {len(plan.operations)} operation(s) across {len(affected)} file(s)",
            fileCount=len(affected),
            affectedFiles=affected,
        )

        self.logger.info(
            "proposed_plan_built",
            intent_type=intent_type,
            operations=len(plan.operations),
            edits=len(plan.files_to_edit),
            creates=len(plan.files_to_create),
            deletes=len(plan.files_to_delete),
        )

    # -- Healing constants --------------------------------------------------

    MAX_HEALING_ATTEMPTS = 2

    # -- VALIDATE_CODE -----------------------------------------------------

    def _language_for_path(self, file_path: str) -> str:
        """Infer language from file extension.

        Args:
            file_path: File path to inspect.

        Returns:
            Language identifier string.
        """
        suffix = Path(file_path).suffix.lower()
        if suffix == ".py":
            return "python"
        if suffix in (".ts", ".tsx", ".js", ".jsx"):
            return "javascript"
        if suffix == ".go":
            return "go"
        if suffix == ".java":
            return "java"
        if suffix == ".rs":
            return "rust"
        return "unknown"

    def _validate_balanced_braces(self, content: str) -> None:
        """Raise if curly braces or parentheses are unbalanced.

        Args:
            content: Source code to check.

        Raises:
            ValueError: On unbalanced delimiters.
        """
        depth_curly = 0
        depth_paren = 0
        for ch in content:
            if ch == "{":
                depth_curly += 1
            elif ch == "}":
                depth_curly -= 1
                if depth_curly < 0:
                    raise ValueError("Unbalanced braces: extra '}'")
            elif ch == "(":
                depth_paren += 1
            elif ch == ")":
                depth_paren -= 1
                if depth_paren < 0:
                    raise ValueError("Unbalanced parentheses: extra ')'")
        if depth_curly != 0:
            raise ValueError("Unbalanced braces: unclosed '{' or extra '}'")
        if depth_paren != 0:
            raise ValueError("Unbalanced parentheses: unclosed '(' or extra ')'")

    async def _handle_validate_code(self, step: ExecutionStep) -> None:
        """Dry-run validation with self-healing: syntax-check every proposed
        file in memory and auto-fix failures up to ``MAX_HEALING_ATTEMPTS``.

        Validates ALL operations in ``self._proposed_plan`` (not just
        ``step.files``), including new files that don't exist on disk yet.

        Python files are parsed with ``ast.parse``; JS/TS files are checked
        for balanced braces/parentheses; all other files must be non-empty.

        **Day 5 — Healing Loop:** If a file fails validation, the executor
        invokes the LLM to fix the syntax error and re-validates.  This
        is capped at ``MAX_HEALING_ATTEMPTS`` per execution to prevent
        infinite loops.

        If validation passes, ``proposed_plan.validation_passed`` is set
        to ``True``.  On any failure (after exhausting healing) the plan
        is marked invalid and the exception propagates.
        """
        assert step.kind == "VALIDATE_CODE", f"Expected VALIDATE_CODE, got {step.kind!r}"
        if not self._generated_code and not self._proposed_plan:
            raise ValueError("No proposed plan or generated code; run GENERATE_CODE first")

        healing_attempts = 0
        last_error: Optional[Exception] = None

        while True:
            try:
                self._run_validation_pass(step)
                break
            except (SyntaxError, ValueError) as exc:
                healing_attempts += 1
                last_error = exc

                if healing_attempts > self.MAX_HEALING_ATTEMPTS:
                    self.logger.warning(
                        "healing_exhausted",
                        attempts=healing_attempts - 1,
                        error=str(exc)[:300],
                    )
                    self._emit(
                        "heal_exhausted",
                        f"Healing failed after {healing_attempts - 1} attempt(s): {str(exc)[:200]}",
                        healAttempts=healing_attempts - 1,
                    )
                    raise

                self.logger.info(
                    "healing_attempt",
                    attempt=healing_attempts,
                    max=self.MAX_HEALING_ATTEMPTS,
                    error=str(exc)[:300],
                )
                self._emit(
                    "healing",
                    f"Healing in progress... (attempt {healing_attempts}/{self.MAX_HEALING_ATTEMPTS})",
                    healAttempt=healing_attempts,
                    maxAttempts=self.MAX_HEALING_ATTEMPTS,
                    error=str(exc)[:200],
                )

                healed = await self._attempt_heal(exc)
                if not healed:
                    self._emit(
                        "heal_failed",
                        f"Heal Agent could not fix: {str(exc)[:200]}",
                        healAttempt=healing_attempts,
                    )
                    raise

                self._emit(
                    "heal_applied",
                    f"Heal Agent applied a fix (attempt {healing_attempts}), re-validating...",
                    healAttempt=healing_attempts,
                )

    def _run_validation_pass(self, step: ExecutionStep) -> None:
        """Execute a single validation pass over all proposed files."""
        operations_to_validate = (
            self._proposed_plan.operations
            if self._proposed_plan
            else []
        )

        validated_paths: set[str] = set()
        total_ops = len([o for o in operations_to_validate if o.action != "delete"])

        # Security scan: check all proposed content for secrets/vulnerabilities
        proposed_contents = {
            op.file_path: op.content
            for op in operations_to_validate
            if op.action != "delete" and op.content
        }
        if proposed_contents:
            self._run_security_scan(proposed_contents)

        for idx, op in enumerate(operations_to_validate):
            if op.action == "delete":
                continue
            validated_paths.add(op.file_path)
            self._emit(
                "validate",
                f"Validating syntax: {Path(op.file_path).name} ({idx + 1}/{total_ops})",
                file=op.file_path,
                validatedSoFar=idx + 1,
                totalFiles=total_ops,
            )
            self._validate_single_file(op.file_path, op.content)

        for file_path in step.files:
            if file_path in validated_paths:
                continue
            if file_path in self._generated_code:
                self._validate_single_file(
                    file_path, self._generated_code[file_path]
                )
            elif not self._proposed_plan:
                raise ValueError(f"Generated code missing for file: {file_path!r}")

        if self._proposed_plan:
            self._proposed_plan.validation_passed = True
            self.logger.info(
                "dry_run_validation_passed",
                files_validated=len(validated_paths) + len(
                    [f for f in step.files if f not in validated_paths]
                ),
            )

    async def _attempt_heal(self, error: Exception) -> bool:
        """Use the LLM to fix a validation error in the proposed code.

        Parses the error message to find the failing file, then asks the
        LLM to fix the syntax issue.  Updates ``_proposed_plan`` and
        ``_generated_code`` in place if successful.

        Returns ``True`` if a fix was applied, ``False`` otherwise.
        """
        import re as _re

        error_msg = str(error)

        failing_file: Optional[str] = None
        for pattern in [
            r"(?:in|for)\s+(.+?)(?::\s|$)",
            r"^(.+\.(?:py|ts|tsx|js|jsx))",
        ]:
            m = _re.search(pattern, error_msg)
            if m:
                candidate = m.group(1).strip().strip("'\"")
                if candidate in self._generated_code:
                    failing_file = candidate
                    break

        if not failing_file and self._proposed_plan:
            for op in self._proposed_plan.operations:
                if op.action != "delete" and op.file_path in self._generated_code:
                    try:
                        self._validate_single_file(op.file_path, op.content)
                    except Exception:
                        failing_file = op.file_path
                        break

        if not failing_file:
            return False

        broken_code = self._generated_code.get(failing_file, "")
        if not broken_code:
            return False

        heal_instruction = (
            f"The following code has a syntax error:\n"
            f"Error: {error_msg}\n\n"
            f"Fix the syntax error and return the complete corrected file. "
            f"Return ONLY the file content, no explanation."
        )

        try:
            fixed = await self._llm.execute_refactor_simple(
                broken_code, heal_instruction
            )
        except Exception:
            return False

        if not isinstance(fixed, str) or not fixed.strip():
            return False

        self._generated_code[failing_file] = fixed

        if self._proposed_plan:
            for op in self._proposed_plan.operations:
                if op.file_path == failing_file:
                    op.content = fixed
                    break
            self._proposed_plan.validation_passed = False

        self.logger.info(
            "heal_code_replaced",
            file=failing_file,
            original_len=len(broken_code),
            fixed_len=len(fixed),
        )
        return True

    def _run_security_scan(self, file_contents: dict[str, str]) -> None:
        """Run the Security Sentinel scan on all proposed code changes.

        Blocks the pipeline if critical secrets are detected.
        """
        try:
            from code4u.security_compliance.security.sentinel_agent import (
                scan_proposed_changes,
                SecurityViolationError,
            )
        except ImportError:
            return

        findings, blocked = scan_proposed_changes(file_contents, block_on_secrets=True)

        if findings:
            secret_count = sum(1 for f in findings if f.get("type") == "secret")
            vuln_count = sum(1 for f in findings if f.get("type") == "vulnerability")

            self._emit(
                "security_scan",
                f"Security scan: {secret_count} secret(s), {vuln_count} vulnerability(ies) detected",
                secretCount=secret_count,
                vulnCount=vuln_count,
                blocked=blocked,
            )

            if blocked:
                raise SecurityViolationError(
                    findings=[f for f in findings if f.get("severity") == "critical"],
                    message=f"Blocked: {secret_count} critical secret(s) detected in proposed changes",
                )

    def _validate_single_file(self, file_path: str, content: str) -> None:
        """Run language-appropriate syntax validation on one file's content."""
        lang = self._language_for_path(file_path)

        if lang == "python":
            try:
                ast.parse(content)
            except SyntaxError as exc:
                raise SyntaxError(
                    f"Python syntax error in {file_path}: {exc}"
                ) from exc
        elif lang == "javascript":
            if not content or not isinstance(content, str):
                raise ValueError(
                    f"Generated content for {file_path!r} must be non-empty string"
                )
            self._validate_balanced_braces(content)
        elif lang == "go":
            if not content or not isinstance(content, str):
                raise ValueError(
                    f"Generated content for {file_path!r} must be non-empty string"
                )
            self._validate_balanced_braces(content)
            if "package " not in content:
                raise ValueError(
                    f"Go file {file_path!r} missing 'package' declaration"
                )
        elif lang == "java":
            if not content or not isinstance(content, str):
                raise ValueError(
                    f"Generated content for {file_path!r} must be non-empty string"
                )
            self._validate_balanced_braces(content)
        else:
            if not content or not isinstance(content, str) or not content.strip():
                raise ValueError(
                    f"Generated content for {file_path!r} must be non-empty string"
                )

    # -- PREVIEW_DIFF ------------------------------------------------------

    def _make_unified_diff(
        self,
        file_path: str,
        original_content: str,
        generated_content: str,
    ) -> str:
        """Produce a deterministic unified diff between two strings.

        Args:
            file_path: Used as ``fromfile`` / ``tofile`` in headers.
            original_content: Content currently on disk.
            generated_content: Proposed new content.

        Returns:
            A unified-diff string (may be empty-ish if contents are equal).
        """
        a = original_content.splitlines(keepends=True)
        b = generated_content.splitlines(keepends=True)
        if not a and not b:
            a, b = [""], [""]
        elif not a:
            a = [""]
        elif not b:
            b = [""]
        lines = list(
            difflib.unified_diff(
                a, b, fromfile=file_path, tofile=file_path, lineterm=""
            )
        )
        return "\n".join(lines) + ("\n" if lines else "")

    async def _handle_preview_diff(self, step: ExecutionStep) -> None:
        """Generate unified diffs for all proposed operations.

        Handles new files (original is empty string) and edits
        (original read from disk or from the ProposedPlan).
        """
        assert step.kind == "PREVIEW_DIFF", f"Expected PREVIEW_DIFF, got {step.kind!r}"
        if not self._generated_code and not self._proposed_plan:
            raise ValueError("No generated code or proposed plan; run GENERATE_CODE first")

        diffs: Dict[str, str] = {}

        if self._proposed_plan:
            op_count = len(self._proposed_plan.operations)
            for idx, op in enumerate(self._proposed_plan.operations):
                self._emit(
                    "diff",
                    f"Building diff {idx + 1}/{op_count}: {Path(op.file_path).name}",
                    file=op.file_path,
                    action=op.action,
                    diffIndex=idx + 1,
                    totalDiffs=op_count,
                )
                if op.action == "delete":
                    diffs[op.file_path] = self._make_unified_diff(
                        op.file_path, op.original_content, ""
                    )
                elif op.action == "create":
                    diffs[op.file_path] = self._make_unified_diff(
                        op.file_path, "", op.content
                    )
                else:
                    diffs[op.file_path] = self._make_unified_diff(
                        op.file_path, op.original_content, op.content
                    )

        # Also diff step.files not already covered by the plan
        for file_path in step.files:
            if file_path in diffs:
                continue
            if file_path in self._generated_code:
                original_content = self._read_file_from_disk(file_path)
                diffs[file_path] = self._make_unified_diff(
                    file_path, original_content, self._generated_code[file_path]
                )

        self._diffs = diffs

    # -- APPLY_DIFF --------------------------------------------------------

    def _rollback_files(self, files_to_restore: Dict[str, str]) -> None:
        """Restore files from backup.  Best-effort: writes every file.

        Args:
            files_to_restore: Mapping ``file_path → original_content``.

        Raises:
            OSError: If any single restore fails.
        """
        for path, content in files_to_restore.items():
            Path(path).write_text(content, encoding="utf-8")

    async def _handle_apply_diff(self, step: ExecutionStep) -> None:
        """Apply all proposed operations to disk transactionally.

        In **dry-run mode** this step is skipped entirely — the executor
        stops after DIFF_PREVIEWED with full diffs available for inspection.

        For non-dry-run, the strategy handles three operation types:

          - **edit**: backup → write → rollback on failure.
          - **create**: write new file → delete on rollback.
          - **delete**: backup content → delete file → restore on rollback.

        Only files that were *actually* modified/created/deleted are
        rolled back on failure, ensuring precise recovery.
        """
        assert step.kind == "APPLY_DIFF", f"Expected APPLY_DIFF, got {step.kind!r}"

        if self._dry_run:
            self.logger.info("dry_run_skip_apply", reason="dry_run mode active")
            return

        if not self._generated_code and not self._proposed_plan:
            raise ValueError("No generated code or proposed plan; run GENERATE_CODE first")

        # No-op when plan has zero operations (LLM decided no change needed)
        if self._proposed_plan and not self._proposed_plan.operations:
            self.logger.info("apply_skip_no_ops", reason="ProposedPlan has 0 operations")
            return

        if not self._diffs:
            raise ValueError("_diffs is empty; run PREVIEW_DIFF first")

        # Decide operations list
        if self._proposed_plan:
            ops = self._proposed_plan.operations
        else:
            ops = [
                FileOperation(
                    file_path=fp,
                    action="edit",
                    content=self._generated_code[fp],
                    original_content=self._read_file_from_disk(fp),
                    reason="legacy path",
                )
                for fp in step.files
                if fp in self._generated_code
            ]

        # Track what we've done for precise rollback
        edited_backups: Dict[str, str] = {}
        created_files: List[str] = []
        deleted_backups: Dict[str, str] = {}

        try:
            total_ops = len(ops)
            for idx, op in enumerate(ops):
                self._emit(
                    "apply",
                    f"Applying {op.action} {idx + 1}/{total_ops}: {Path(op.file_path).name}",
                    file=op.file_path,
                    action=op.action,
                    applyIndex=idx + 1,
                    totalOps=total_ops,
                )
                if op.action == "edit":
                    backup = self._read_file_from_disk(op.file_path)
                    self._write_file_to_disk(op.file_path, op.content)
                    edited_backups[op.file_path] = backup

                elif op.action == "create":
                    parent = Path(op.file_path).parent
                    parent.mkdir(parents=True, exist_ok=True)
                    self._write_file_to_disk(op.file_path, op.content)
                    created_files.append(op.file_path)

                elif op.action == "delete":
                    backup = self._read_file_from_disk(op.file_path)
                    Path(op.file_path).unlink()
                    deleted_backups[op.file_path] = backup

        except Exception as apply_error:
            try:
                self._rollback_operations(
                    edited_backups, created_files, deleted_backups
                )
            except Exception as rollback_error:
                raise RuntimeError(
                    f"Rollback failed after apply error: {rollback_error!s}"
                ) from apply_error
            raise apply_error

        self._original_code = {}

    def _rollback_operations(
        self,
        edited_backups: Dict[str, str],
        created_files: List[str],
        deleted_backups: Dict[str, str],
    ) -> None:
        """Undo all completed operations. Best-effort."""
        for path, content in edited_backups.items():
            Path(path).write_text(content, encoding="utf-8")
        for path in created_files:
            try:
                Path(path).unlink()
            except FileNotFoundError:
                pass
        for path, content in deleted_backups.items():
            Path(path).write_text(content, encoding="utf-8")

    # -- dispatcher --------------------------------------------------------

    async def _dispatch(self, step: ExecutionStep) -> None:
        """Route a step to the correct handler.

        Args:
            step: The ``ExecutionStep`` to execute.

        Raises:
            ValueError: If ``step.kind`` is unknown.
        """
        self._current_step_kind = step.kind
        handlers = {
            "GENERATE_CODE": self._handle_generate_code,
            "VALIDATE_CODE": self._handle_validate_code,
            "PREVIEW_DIFF": self._handle_preview_diff,
            "APPLY_DIFF": self._handle_apply_diff,
        }
        handler = handlers.get(step.kind)
        if handler is None:
            raise ValueError(f"Unknown step kind: {step.kind!r}")
        await handler(step)

    # -- main entry point --------------------------------------------------

    async def run(
        self,
        plan: ExecutionPlan,
        context: RefactorBlastContext,
        intent: str = "",
    ) -> PlanExecutionState:
        """Execute *plan* end-to-end through the locked state machine.

        On success the final state is ``APPLIED``.  On any exception the
        state transitions to ``FAILED`` and the exception is re-raised so
        the caller can surface it.

        Args:
            plan: Ordered execution plan (from ``plan_from_blast_context``).
            context: Immutable blast-radius context.
            intent: Original user intent string (used for rename detection).

        Returns:
            The terminal ``PlanExecutionState`` (always ``APPLIED`` when
            this method returns normally).

        Raises:
            ValueError: If *plan* or *context* is ``None``.
            Exception: Any exception raised by a step handler.
        """
        if plan is None:
            raise ValueError("plan is required")
        if context is None:
            raise ValueError("context is required")

        self._plan = plan
        self._context = context
        self._intent = intent
        self._state = PlanExecutionState.INIT
        self._last_error = None
        self._generated_code = {}
        self._diffs = {}
        self._original_code = {}
        self._proposed_plan = None
        self._state_history = []
        self._current_step_kind = None
        self._execution_id = str(uuid.uuid4())

        self._transition(PlanExecutionState.PLAN_READY)
        self._emit("pipeline_start", "Pipeline started", intent=intent)

        t0 = time.time()
        error_msg: Optional[str] = None

        total_steps = len(plan.steps)
        for step_idx, step in enumerate(plan.steps, 1):
            try:
                self._emit(
                    "step_start",
                    f"Step {step_idx}/{total_steps}: {step.kind}",
                    step=step.kind,
                    progress=step_idx / total_steps,
                )
                await self._dispatch(step)
                next_state = _KIND_TO_NEXT_STATE.get(step.kind)
                if next_state is None:
                    raise ValueError(
                        f"No next state for step kind: {step.kind!r}"
                    )
                self._transition(next_state)
                self._emit(
                    "step_complete",
                    f"{step.kind} complete",
                    step=step.kind,
                    progress=step_idx / total_steps,
                )
            except Exception as exc:
                self._last_error = exc
                error_msg = str(exc)[:500]
                self._transition(PlanExecutionState.FAILED)
                self._emit("pipeline_error", f"Failed: {error_msg}", error=error_msg)
                self._record_history(t0, error_msg)
                raise

        elapsed_ms = (time.time() - t0) * 1000
        self._emit(
            "pipeline_complete",
            "Pipeline finished successfully",
            durationMs=round(elapsed_ms, 1),
        )
        self._record_history(t0, None)
        return self._state

    def _record_history(self, start_time: float, error: Optional[str]) -> None:
        """Write a summary record to ``~/.code4u/history.jsonl``."""
        try:
            from code4u.cli.history import record_job

            pp = self._proposed_plan
            record_job(
                execution_id=self._execution_id,
                intent=self._intent,
                intent_type=pp.intent_type if pp else "unknown",
                file_count=len(pp.operations) if pp else 0,
                duration_ms=(time.time() - start_time) * 1000,
                outcome=self._state.value,
                validation_passed=pp.validation_passed if pp else False,
                error=error,
                dry_run=self._dry_run,
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Legacy RefactorOrchestrator (Day-2, not used by refactor API)
# ---------------------------------------------------------------------------

class RefactorOrchestratorState:
    INIT = "init"
    CONTEXT_READY = "context_ready"
    PLAN_READY = "plan_ready"
    LLM_INVOKED = "llm_invoked"


class RefactorOrchestrator:
    """Day-2 refactor orchestrator (legacy).

    Uses ``RefactorContext`` (not ``RefactorBlastContext``) and always
    raises ``PipelineIncompleteError`` after the LLM call because diff
    generation was never implemented here.  Superseded by ``PlanExecutor``.
    """

    def __init__(self, llm_executor: Optional[LLMExecutor] = None) -> None:
        self.logger = __import__("structlog").get_logger("orchestrator")
        self._state = RefactorOrchestratorState.INIT
        self._llm: LLMExecutor = llm_executor or LLMExecutor()

    def _validate_context(self, context: RefactorContext) -> None:
        """Validate a legacy ``RefactorContext``."""
        if not getattr(context, "target_file", None) or not str(context.target_file).strip():
            raise ValueError("RefactorContext.target_file is required")
        if not hasattr(context, "language"):
            raise ValueError("RefactorContext.language is required")
        if getattr(context, "file_content", None) is not None and not isinstance(context.file_content, str):
            raise ValueError("RefactorContext.file_content must be str")
        if not getattr(context, "intent", None) or not str(context.intent).strip():
            raise ValueError("RefactorContext.intent is required")

    async def execute_plan(self, context: RefactorContext) -> Dict[str, Any]:
        """Run legacy pipeline.  Always raises ``PipelineIncompleteError``."""
        self._validate_context(context)
        self._state = RefactorOrchestratorState.CONTEXT_READY
        return await self._execute(context)

    async def _execute(self, context: RefactorContext) -> Dict[str, Any]:
        plan = plan_refactor(context)
        self._state = RefactorOrchestratorState.PLAN_READY
        instruction = context.intent
        if context.target_symbol:
            instruction = f"{context.intent} (target symbol: {context.target_symbol})"
        await self._llm.execute_refactor_simple(context.file_content, instruction)
        self._state = RefactorOrchestratorState.LLM_INVOKED
        raise PipelineIncompleteError("Diff generation not implemented")


# ---------------------------------------------------------------------------
# Legacy AgentOrchestrator
# ---------------------------------------------------------------------------

class AgentOrchestrator:
    """Multi-agent pipeline orchestrator (legacy).

    Executes agents in a fixed order: planner → contract → frontend →
    backend → verifier.  Not used by the refactor API.
    """

    PIPELINE: List[str] = ["planner", "contract", "frontend", "backend", "verifier"]

    def __init__(self) -> None:
        self._agents: Dict[str, Agent] = {}
        self.logger = __import__("structlog").get_logger("orchestrator")

    def register(self, agent: Agent) -> None:
        """Register an agent under ``agent.name``."""
        self._agents[agent.name] = agent

    async def execute(self, context: AgentContext) -> List[AgentResult]:
        """Run the pipeline sequentially, stopping on the first failure."""
        results: List[AgentResult] = []
        for agent_name in self.PIPELINE:
            agent = self._agents.get(agent_name)
            if not agent:
                continue
            context.previous_results = results
            start = time.perf_counter()
            try:
                result = await agent.execute(context)
                result.execution_time_ms = (time.perf_counter() - start) * 1000
                if result.status == AgentStatus.FAILED:
                    self.logger.error(
                        "agent_failed", agent=agent_name, errors=result.errors
                    )
                    results.append(result)
                    break
                results.append(result)
            except Exception as exc:
                results.append(
                    AgentResult(
                        status=AgentStatus.FAILED,
                        output={},
                        errors=[str(exc)],
                    )
                )
                break
        return results
