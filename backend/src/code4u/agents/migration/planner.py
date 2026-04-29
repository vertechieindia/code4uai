"""Migration Plan Model & Planner.

Given a structural intent like "Move UserProfile from models.py to
entities.py", the ``MigrationPlanner`` uses the ``DependencyMap`` to:

  1. Locate the symbol(s) in the source file.
  2. Extract their full source code (including docstrings, decorators).
  3. Identify every file that imports the symbol(s).
  4. Produce a ``MigrationPlan`` describing all operations needed.

The plan is a *pure data structure* — it doesn't touch the filesystem.
Execution is handled by ``MigrationExecutor``.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

logger = structlog.get_logger("migration_planner")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SymbolExtraction:
    """A symbol extracted from its source file."""
    name: str
    kind: str
    source: str
    start_line: int
    end_line: int
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ImportUpdate:
    """A single import statement fix for one file."""
    file_path: str
    old_import: str
    new_import: str
    line_number: int = 0


@dataclass
class MigrationPlan:
    """Complete plan for a multi-file structural migration.

    Contains every operation needed to move symbol(s) from one file
    to another while keeping all imports intact.
    """
    source_file: str
    target_file: str
    symbols_to_move: List[SymbolExtraction] = field(default_factory=list)
    import_updates: List[ImportUpdate] = field(default_factory=list)
    impacted_files: List[str] = field(default_factory=list)
    source_new_content: str = ""
    target_new_content: str = ""
    re_export_stub: str = ""
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = True

    @property
    def symbol_names(self) -> List[str]:
        return [s.name for s in self.symbols_to_move]

    @property
    def total_operations(self) -> int:
        return 2 + len(self.import_updates)  # source + target + import fixes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sourceFile": self.source_file,
            "targetFile": self.target_file,
            "symbolsToMove": [
                {"name": s.name, "kind": s.kind, "lines": f"{s.start_line}-{s.end_line}"}
                for s in self.symbols_to_move
            ],
            "importUpdates": [
                {"file": iu.file_path, "old": iu.old_import, "new": iu.new_import}
                for iu in self.import_updates
            ],
            "impactedFiles": self.impacted_files,
            "totalOperations": self.total_operations,
            "isValid": self.is_valid,
            "validationErrors": self.validation_errors,
        }


# ---------------------------------------------------------------------------
# MigrationPlanner
# ---------------------------------------------------------------------------

class MigrationPlanner:
    """Builds a ``MigrationPlan`` from a structural intent and
    the ``DependencyMap``.
    """

    def __init__(self, dep_map: Any) -> None:
        self._dep_map = dep_map

    def plan_move(
        self,
        source_file: str,
        target_file: str,
        symbol_names: List[str],
    ) -> MigrationPlan:
        """Plan a symbol move from source to target.

        Args:
            source_file: Absolute path to the file containing the symbols.
            target_file: Absolute path to the destination file.
            symbol_names: Names of the symbols to move.

        Returns:
            A fully populated ``MigrationPlan``.
        """
        source_path = Path(source_file).resolve()
        target_path = Path(target_file).resolve()

        plan = MigrationPlan(
            source_file=str(source_path),
            target_file=str(target_path),
        )

        if not source_path.is_file():
            plan.validation_errors.append(f"Source file not found: {source_file}")
            plan.is_valid = False
            return plan

        source_content = source_path.read_text(encoding="utf-8")

        # Step 1: Extract symbols from source
        for sym_name in symbol_names:
            extraction = self._extract_symbol(source_content, sym_name, str(source_path))
            if extraction is None:
                plan.validation_errors.append(f"Symbol '{sym_name}' not found in {source_path.name}")
                plan.is_valid = False
            else:
                plan.symbols_to_move.append(extraction)

        if not plan.is_valid:
            return plan

        # Step 2: Build new source content (with symbols removed)
        plan.source_new_content = self._remove_symbols(source_content, plan.symbols_to_move)

        # Step 3: Build new target content (with symbols inserted)
        existing_target = ""
        if target_path.is_file():
            existing_target = target_path.read_text(encoding="utf-8")
        plan.target_new_content = self._build_target(
            existing_target, plan.symbols_to_move, source_content,
        )

        # Step 4: Build re-export stub for backward compatibility
        source_module = self._file_to_module(str(source_path))
        target_module = self._file_to_module(str(target_path))
        plan.re_export_stub = self._build_re_export(
            plan.symbol_names, target_module,
        )

        # Step 5: Find all impacted files and generate import updates
        all_impacted: Set[str] = set()
        for sym_name in plan.symbol_names:
            dependents = self._dep_map.get_dependents(sym_name)
            for dep in dependents:
                if dep != str(source_path) and dep != str(target_path):
                    all_impacted.add(dep)

        plan.impacted_files = sorted(all_impacted)

        for imp_file in plan.impacted_files:
            updates = self._generate_import_updates(
                imp_file, plan.symbol_names,
                source_module, target_module,
            )
            plan.import_updates.extend(updates)

        # Step 6: Validate the plan
        self._validate_plan(plan)

        logger.info(
            "migration_planned",
            source=source_path.name,
            target=target_path.name,
            symbols=len(plan.symbols_to_move),
            impacted=len(plan.impacted_files),
            operations=plan.total_operations,
            valid=plan.is_valid,
        )

        return plan

    def plan_from_intent(self, intent: str, workspace_path: str) -> Optional[MigrationPlan]:
        """Parse a natural-language move intent and plan it.

        Supported patterns:
          - "Move UserProfile from models.py to entities.py"
          - "Move calculate_total to math_utils.py"
        """
        parsed = self._parse_move_intent(intent)
        if parsed is None:
            return None

        symbol_name, source_hint, target_hint = parsed
        source_file = self._resolve_file(symbol_name, source_hint, workspace_path)
        if source_file is None:
            return None

        target_file = str(Path(workspace_path) / target_hint)
        return self.plan_move(source_file, target_file, [symbol_name])

    # -- Symbol extraction ---------------------------------------------------

    def _extract_symbol(
        self, content: str, symbol_name: str, file_path: str,
    ) -> Optional[SymbolExtraction]:
        """Extract a symbol's source code from a Python file."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return None

        lines = content.splitlines(keepends=True)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == symbol_name:
                    start = node.lineno
                    end = getattr(node, "end_lineno", node.lineno)
                    # Include decorators
                    if node.decorator_list:
                        start = min(d.lineno for d in node.decorator_list)
                    source = "".join(lines[start - 1: end])
                    deps = self._find_symbol_deps(content, node)
                    return SymbolExtraction(
                        name=symbol_name, kind="function",
                        source=source, start_line=start, end_line=end,
                        dependencies=deps,
                    )
            elif isinstance(node, ast.ClassDef):
                if node.name == symbol_name:
                    start = node.lineno
                    end = getattr(node, "end_lineno", node.lineno)
                    if node.decorator_list:
                        start = min(d.lineno for d in node.decorator_list)
                    source = "".join(lines[start - 1: end])
                    deps = self._find_symbol_deps(content, node)
                    return SymbolExtraction(
                        name=symbol_name, kind="class",
                        source=source, start_line=start, end_line=end,
                        dependencies=deps,
                    )
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == symbol_name:
                        start = node.lineno
                        end = getattr(node, "end_lineno", node.lineno)
                        source = "".join(lines[start - 1: end])
                        return SymbolExtraction(
                            name=symbol_name, kind="variable",
                            source=source, start_line=start, end_line=end,
                        )

        return None

    def _find_symbol_deps(self, content: str, node: ast.AST) -> List[str]:
        """Find names used within a symbol that might need importing."""
        source_segment = ast.get_source_segment(content, node) or ""
        names: Set[str] = set()
        try:
            sub_tree = ast.parse(source_segment)
            for child in ast.walk(sub_tree):
                if isinstance(child, ast.Name):
                    names.add(child.id)
        except SyntaxError:
            pass
        # Filter out builtins and the symbol itself
        builtins = {"print", "len", "range", "str", "int", "float", "list",
                     "dict", "set", "tuple", "True", "False", "None", "self",
                     "super", "type", "isinstance", "hasattr", "getattr"}
        return sorted(names - builtins - {node.name if hasattr(node, "name") else ""})

    # -- Content manipulation ------------------------------------------------

    def _remove_symbols(
        self, content: str, symbols: List[SymbolExtraction],
    ) -> str:
        """Remove extracted symbols from the source file content."""
        lines = content.splitlines(keepends=True)
        ranges_to_remove = sorted(
            [(s.start_line - 1, s.end_line) for s in symbols],
            reverse=True,
        )
        for start_idx, end_idx in ranges_to_remove:
            del lines[start_idx:end_idx]

        result = "".join(lines)
        # Clean up multiple blank lines
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def _build_target(
        self,
        existing_content: str,
        symbols: List[SymbolExtraction],
        source_content: str,
    ) -> str:
        """Build the target file content with the moved symbols."""
        parts: List[str] = []

        if existing_content:
            parts.append(existing_content.rstrip())
            parts.append("\n\n")

        # Collect needed imports from the source file
        needed_imports = self._collect_needed_imports(source_content, symbols)
        if needed_imports:
            parts.append("\n".join(needed_imports))
            parts.append("\n\n")

        for sym in symbols:
            parts.append(sym.source.rstrip())
            parts.append("\n\n")

        return "".join(parts).rstrip() + "\n"

    def _collect_needed_imports(
        self, source_content: str, symbols: List[SymbolExtraction],
    ) -> List[str]:
        """Identify import lines from source that the moved symbols need."""
        try:
            tree = ast.parse(source_content)
        except SyntaxError:
            return []

        import_lines: List[str] = []
        all_deps: Set[str] = set()
        for s in symbols:
            all_deps.update(s.dependencies)

        source_lines = source_content.splitlines()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names: Set[str] = set()
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        names.add(alias.asname or alias.name.split(".")[-1])
                else:
                    for alias in node.names:
                        names.add(alias.name)

                if names & all_deps:
                    import_lines.append(source_lines[node.lineno - 1].rstrip())

        return import_lines

    def _build_re_export(self, symbol_names: List[str], target_module: str) -> str:
        """Build a backward-compatible re-export stub.

        Example: ``from entities import UserProfile  # re-exported``
        """
        names = ", ".join(symbol_names)
        return f"from {target_module} import {names}  # re-exported for backward compatibility\n"

    # -- Import updates ------------------------------------------------------

    def _generate_import_updates(
        self,
        imp_file: str,
        symbol_names: List[str],
        source_module: str,
        target_module: str,
    ) -> List[ImportUpdate]:
        """Generate import statement updates for one impacted file."""
        try:
            content = Path(imp_file).read_text(encoding="utf-8")
        except Exception:
            return []

        updates: List[ImportUpdate] = []
        for line_num, line in enumerate(content.splitlines(), 1):
            for sym_name in symbol_names:
                if self._line_imports_symbol(line, sym_name, source_module):
                    new_line = self._rewrite_import_line(
                        line, sym_name, source_module, target_module,
                    )
                    if new_line != line:
                        updates.append(ImportUpdate(
                            file_path=imp_file,
                            old_import=line.rstrip(),
                            new_import=new_line.rstrip(),
                            line_number=line_num,
                        ))
        return updates

    def _line_imports_symbol(
        self, line: str, symbol_name: str, source_module: str,
    ) -> bool:
        """Check if a line imports a specific symbol."""
        stripped = line.strip()
        if not stripped.startswith(("import ", "from ")):
            return False
        return symbol_name in stripped

    def _rewrite_import_line(
        self, line: str, symbol_name: str,
        old_module: str, new_module: str,
    ) -> str:
        """Rewrite an import line to point to the new module."""
        # Handle "from X import A, B" → update module path
        pattern = rf"(from\s+){re.escape(old_module)}(\s+import\s+)"
        if re.search(pattern, line):
            return re.sub(pattern, rf"\g<1>{new_module}\g<2>", line)

        # Handle bare module name in import paths
        if old_module in line:
            return line.replace(old_module, new_module)

        return line

    # -- Validation ----------------------------------------------------------

    def _validate_plan(self, plan: MigrationPlan) -> None:
        """Validate the migration plan for correctness."""
        # Check target syntax
        try:
            ast.parse(plan.target_new_content)
        except SyntaxError as e:
            plan.validation_errors.append(f"Target file has syntax error: {e}")
            plan.is_valid = False

        # Check source syntax (after removal)
        if plan.source_new_content.strip():
            try:
                ast.parse(plan.source_new_content)
            except SyntaxError as e:
                plan.validation_errors.append(f"Source file has syntax error after removal: {e}")
                plan.is_valid = False

        # Check for naming collisions in target
        if Path(plan.target_file).is_file():
            try:
                existing = Path(plan.target_file).read_text(encoding="utf-8")
                existing_tree = ast.parse(existing)
                existing_names = set()
                for node in ast.iter_child_nodes(existing_tree):
                    if hasattr(node, "name"):
                        existing_names.add(node.name)
                for sym in plan.symbols_to_move:
                    if sym.name in existing_names:
                        plan.validation_errors.append(
                            f"Naming collision: '{sym.name}' already exists in target file"
                        )
                        plan.is_valid = False
            except Exception:
                pass

    # -- Helpers -------------------------------------------------------------

    def _file_to_module(self, file_path: str) -> str:
        """Convert a file path to a Python module name (stem only)."""
        return Path(file_path).stem

    def _parse_move_intent(self, intent: str) -> Optional[Tuple[str, str, str]]:
        """Parse: 'Move X from Y to Z' → (symbol, source_hint, target_hint)."""
        patterns = [
            r"(?i)move\s+(\w+)\s+from\s+(\S+)\s+to\s+(\S+)",
            r"(?i)move\s+(\w+)\s+to\s+(\S+)",
        ]
        for pat in patterns:
            m = re.match(pat, intent.strip())
            if m:
                groups = m.groups()
                if len(groups) == 3:
                    sym, src, tgt = groups
                    if not tgt.endswith(".py"):
                        tgt += ".py"
                    return sym, src, tgt
                elif len(groups) == 2:
                    sym, tgt = groups
                    if not tgt.endswith(".py"):
                        tgt += ".py"
                    return sym, "", tgt
        return None

    def _resolve_file(
        self, symbol_name: str, hint: str, workspace: str,
    ) -> Optional[str]:
        """Resolve a symbol to its defining file using the DependencyMap."""
        defs = self._dep_map.get_symbol_defs(symbol_name)
        if not defs:
            return None

        if hint:
            for sd in defs:
                if hint in sd.file_path:
                    return sd.file_path

        return defs[0].file_path
