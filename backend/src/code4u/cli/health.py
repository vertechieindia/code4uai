"""code4u health — find unused symbols and dead imports.

Scans the workspace index for:
  1. **Unused exports**: symbols defined with ``is_exported=True`` that
     no other file imports.
  2. **Unused imports**: import statements that bring in names never
     referenced in the importing file's own source.

For each finding, a ``ProposedPlan`` is built with ``FileOperation``
entries that surgically remove the dead code.
"""

from __future__ import annotations

import ast
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    DependencyMap,
    ImportRef,
    SymbolDef,
    SymbolIndexer,
)
from code4u.platform_core.agents.proposed_plan import (
    FileOperation,
    ProposedPlan,
    INTENT_GENERIC,
)


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def _find_unused_exports(dep_map: DependencyMap) -> List[SymbolDef]:
    """Return exported symbols that have zero dependents (no file imports them)."""
    unused: List[SymbolDef] = []
    seen: Set[Tuple[str, str]] = set()

    for name, defs in dep_map._symbols.items():
        dependents = dep_map.get_dependents(name)
        for sym in defs:
            if not sym.is_exported:
                continue
            key = (sym.name, sym.file_path)
            if key in seen:
                continue
            seen.add(key)

            external_deps = [d for d in dependents if d != sym.file_path]
            if not external_deps:
                unused.append(sym)
    return unused


def _find_unused_imports(dep_map: DependencyMap) -> List[Tuple[ImportRef, List[str]]]:
    """Return imports whose imported names are never referenced in the file body.

    Returns a list of ``(ImportRef, [unused_name, ...])`` tuples.
    Only names that appear in the import but are never used in the file
    (beyond the import line itself) are flagged.
    """
    results: List[Tuple[ImportRef, List[str]]] = []

    for file_path, imports in dep_map._imports.items():
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        lines = content.splitlines()

        for imp in imports:
            if imp.is_wildcard:
                continue
            unused_names: List[str] = []
            for name in imp.names:
                pattern = re.compile(r"\b" + re.escape(name) + r"\b")
                found = False
                for i, line in enumerate(lines, 1):
                    if i == imp.line:
                        continue
                    if pattern.search(line):
                        found = True
                        break
                if not found:
                    unused_names.append(name)

            if unused_names:
                results.append((imp, unused_names))

    return results


# ---------------------------------------------------------------------------
# Plan builders
# ---------------------------------------------------------------------------

def _remove_import_names_from_line(
    line: str, names_to_remove: List[str]
) -> Optional[str]:
    """Remove specific names from an import line, returning the updated line.

    Returns ``None`` if the entire import should be deleted.
    """
    for name in names_to_remove:
        line = re.sub(
            r",?\s*\b" + re.escape(name) + r"\b\s*,?",
            ",",
            line,
        )

    line = re.sub(r",\s*,", ",", line)
    line = re.sub(r"import\s*,", "import ", line)
    line = re.sub(r",\s*$", "", line)

    m = re.search(r"import\s+(.*)", line)
    if m:
        remaining = m.group(1).strip().strip(",").strip()
        if not remaining:
            return None
    return line


def _build_unused_import_plan(
    unused_imports: List[Tuple[ImportRef, List[str]]],
) -> ProposedPlan:
    """Build a ProposedPlan that removes unused import names."""
    edits_by_file: Dict[str, Dict[int, List[str]]] = {}

    for imp, names in unused_imports:
        edits_by_file.setdefault(imp.source_file, {}).setdefault(
            imp.line, []
        ).extend(names)

    operations: List[FileOperation] = []
    for file_path, line_edits in edits_by_file.items():
        try:
            original = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        lines = original.splitlines(keepends=True)
        modified_lines = list(lines)
        lines_to_delete: List[int] = []

        for line_no, names in sorted(line_edits.items()):
            idx = line_no - 1
            if idx >= len(modified_lines):
                continue
            updated = _remove_import_names_from_line(
                modified_lines[idx].rstrip("\n"), names
            )
            if updated is None:
                lines_to_delete.append(idx)
            else:
                modified_lines[idx] = updated + "\n"

        for idx in sorted(lines_to_delete, reverse=True):
            del modified_lines[idx]

        new_content = "".join(modified_lines)
        if new_content != original:
            removed = []
            for _, names in sorted(line_edits.items()):
                removed.extend(names)
            operations.append(
                FileOperation(
                    file_path=file_path,
                    action="edit",
                    content=new_content,
                    original_content=original,
                    reason=f"Remove unused import(s): {', '.join(removed)}",
                )
            )

    return ProposedPlan(
        intent="Remove unused imports",
        intent_type=INTENT_GENERIC,
        operations=operations,
        validation_passed=True,
    )


def _build_unused_export_plan(
    unused_exports: List[SymbolDef],
) -> ProposedPlan:
    """Build a ProposedPlan that removes unused exported symbols.

    Only removes **functions** (kind == 'function') to be conservative.
    Classes and variables are reported but not auto-removed.
    """
    by_file: Dict[str, List[SymbolDef]] = {}
    for sym in unused_exports:
        if sym.kind == "function":
            by_file.setdefault(sym.file_path, []).append(sym)

    operations: List[FileOperation] = []
    for file_path, syms in by_file.items():
        try:
            original = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        content = original
        for sym in sorted(syms, key=lambda s: -s.start_line):
            lines = content.splitlines(keepends=True)
            start = sym.start_line - 1
            end = sym.end_line
            while start > 0 and lines[start - 1].strip() == "":
                start -= 1
            del lines[start:end]
            content = "".join(lines)

        if content != original:
            names = [s.name for s in syms]
            operations.append(
                FileOperation(
                    file_path=file_path,
                    action="edit",
                    content=content,
                    original_content=original,
                    reason=f"Remove unused function(s): {', '.join(names)}",
                )
            )

    return ProposedPlan(
        intent="Remove unused functions",
        intent_type=INTENT_GENERIC,
        operations=operations,
        validation_passed=True,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_python(content: str, file_path: str) -> bool:
    """Return True if content parses as valid Python."""
    if not file_path.endswith(".py"):
        return True
    try:
        ast.parse(content)
        return True
    except SyntaxError:
        return False


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def run_health_check(
    workspace_path: str,
    apply: bool = False,
    console: Optional[Console] = None,
) -> None:
    """Run the full health check and print results."""
    if console is None:
        console = Console()

    indexer = SymbolIndexer()
    t0 = time.monotonic()
    with console.status("[cyan]Indexing workspace...[/cyan]"):
        dep_map = indexer.index_workspace(workspace_path)
    elapsed = (time.monotonic() - t0) * 1000

    console.print(
        f"[dim]Indexed {dep_map.stats['indexed_files']} files "
        f"({dep_map.stats['total_symbols']} symbols) in {elapsed:.0f} ms[/dim]\n"
    )

    # --- Unused imports ---
    with console.status("[cyan]Scanning for unused imports...[/cyan]"):
        unused_imports = _find_unused_imports(dep_map)

    # --- Unused exports ---
    with console.status("[cyan]Scanning for unused exports...[/cyan]"):
        unused_exports = _find_unused_exports(dep_map)

    # --- Report ---
    if not unused_imports and not unused_exports:
        console.print(
            Panel(
                "[bold green]Workspace is clean![/bold green]\n"
                "No unused imports or dead code detected.",
                title="Health Report",
                border_style="green",
            )
        )
        return

    table = Table(title="Health Report", border_style="yellow")
    table.add_column("Type", style="bold")
    table.add_column("Symbol", style="white")
    table.add_column("File", style="dim")
    table.add_column("Line", justify="right")

    for imp, names in unused_imports:
        short = "/".join(Path(imp.source_file).parts[-3:])
        for name in names:
            table.add_row(
                "[yellow]Unused Import[/yellow]",
                name,
                short,
                str(imp.line),
            )

    for sym in unused_exports:
        short = "/".join(Path(sym.file_path).parts[-3:])
        removable = sym.kind == "function"
        label = (
            "[red]Dead Function[/red]"
            if removable
            else f"[dim]Unused {sym.kind}[/dim]"
        )
        table.add_row(label, sym.name, short, str(sym.start_line))

    console.print(table)

    total_issues = len(unused_imports) + len(unused_exports)
    console.print(
        f"\n[bold]Found {total_issues} issue(s).[/bold]"
    )

    # --- Build plans ---
    import_plan = _build_unused_import_plan(unused_imports)
    export_plan = _build_unused_export_plan(unused_exports)

    all_ops = import_plan.operations + export_plan.operations

    if not all_ops:
        console.print(
            "[dim]No auto-fixable issues (only classes/variables flagged).[/dim]"
        )
        return

    # --- Show diffs ---
    console.print(f"\n[bold cyan]Proposed fixes ({len(all_ops)} file(s)):[/bold cyan]\n")
    for op in all_ops:
        short = "/".join(Path(op.file_path).parts[-3:])
        console.print(f"[bold]{short}[/bold]  {op.reason}")

        import difflib

        diff = difflib.unified_diff(
            op.original_content.splitlines(keepends=True),
            op.content.splitlines(keepends=True),
            fromfile=op.file_path,
            tofile=op.file_path,
        )
        diff_text = "".join(diff)
        if diff_text:
            console.print(
                Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
            )
        console.print()

    # --- Apply ---
    if not apply:
        console.print(
            "[bold yellow]Dry run[/bold yellow] — "
            "use [bold]--fix[/bold] or [bold]--apply[/bold] to write changes."
        )
        return

    applied = 0
    skipped = 0
    for op in all_ops:
        if not _validate_python(op.content, op.file_path):
            console.print(
                f"[red]Skipping[/red] {op.file_path} — "
                "proposed content has syntax errors."
            )
            skipped += 1
            continue
        Path(op.file_path).write_text(op.content, encoding="utf-8")
        applied += 1

    console.print(
        f"\n[bold green]Applied {applied} fix(es).[/bold green]"
        + (f"  [yellow]Skipped {skipped}.[/yellow]" if skipped else "")
    )
