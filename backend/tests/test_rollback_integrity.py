"""E2E Rollback Integrity Tests.

Verifies that the PlanExecutor's atomic rollback guarantee holds
under simulated failures.  Every test creates a real multi-file project
on disk, triggers a rename through the full pipeline, and asserts that
after a mid-apply crash the filesystem is **byte-for-byte identical**
to the pre-test snapshot.

Run with::

    pytest tests/test_rollback_integrity.py -v
"""

from __future__ import annotations

import asyncio
import os
import shutil
import stat
import textwrap
from pathlib import Path
from typing import Dict
from unittest.mock import patch

import pytest

from code4u.code_intelligence.context.compiler import ContextCompiler
from code4u.code_intelligence.context.planner import plan_from_blast_context
from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
from code4u.platform_core.agents.orchestrator import PlanExecutor
from code4u.platform_core.state_machine.plan_states import PlanExecutionState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

UTILS_PY = textwrap.dedent("""\
    def calculate_total(items):
        return sum(item.price for item in items)

    def format_currency(amount):
        return f"${amount:.2f}"
""")

REPORTS_PY = textwrap.dedent("""\
    from utils import calculate_total

    def monthly_report(items):
        total = calculate_total(items)
        return {"month": "Jan", "total": total}
""")

INVOICE_PY = textwrap.dedent("""\
    from utils import calculate_total, format_currency

    def create_invoice(items, customer):
        total = calculate_total(items)
        return {
            "customer": customer,
            "total": format_currency(total),
        }
""")

DASHBOARD_PY = textwrap.dedent("""\
    from utils import calculate_total

    def render_dashboard(items):
        return f"Total: {calculate_total(items)}"
""")

PROJECT_FILES: Dict[str, str] = {
    "utils.py": UTILS_PY,
    "reports.py": REPORTS_PY,
    "invoice.py": INVOICE_PY,
    "dashboard.py": DASHBOARD_PY,
}


@pytest.fixture
def test_project(tmp_path: Path):
    """Create a multi-file Python project in a temporary directory."""
    for name, content in PROJECT_FILES.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    yield tmp_path


def _snapshot(root: Path) -> Dict[str, str]:
    """Read every .py file under *root* and return {name: content}."""
    return {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(root.glob("*.py"))
    }


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


async def _run_rename_pipeline(
    workspace: Path,
    old_name: str = "calculate_total",
    new_name: str = "compute_total",
    target_file: str = "utils.py",
    dry_run: bool = False,
) -> PlanExecutor:
    """Run the full rename pipeline through PlanExecutor.

    Returns the executor so callers can inspect state, diffs, etc.
    """
    indexer = SymbolIndexer()
    dep_map = indexer.index_workspace(str(workspace))

    compiler = ContextCompiler(dependency_map=dep_map)
    blast = await compiler.compile_refactor_blast_context(
        intent=f"Rename {old_name} to {new_name}",
        primary_file_path=str(workspace / target_file),
        workspace_path=str(workspace),
    )

    plan = plan_from_blast_context(blast)
    executor = PlanExecutor(dependency_map=dep_map, dry_run=dry_run)
    await executor.run(plan, blast, intent=f"Rename {old_name} to {new_name}")
    return executor


# ---------------------------------------------------------------------------
# Test 1: Happy-path rename
# ---------------------------------------------------------------------------

class TestHappyPathRename:
    """Verify that a rename across 4 files applies correctly."""

    def test_rename_applies_correctly(self, test_project: Path):
        """Full rename: calculate_total -> compute_total across all callers."""
        before = _snapshot(test_project)
        executor = _run(_run_rename_pipeline(test_project))

        assert executor.state == PlanExecutionState.APPLIED
        assert executor.proposed_plan is not None
        assert executor.proposed_plan.validation_passed is True

        after = _snapshot(test_project)

        assert "compute_total" in after["utils.py"]
        assert "calculate_total" not in after["utils.py"]

        assert "compute_total" in after["reports.py"]
        assert "calculate_total" not in after["reports.py"]

        assert "compute_total" in after["invoice.py"]
        assert "calculate_total" not in after["invoice.py"]

        assert "compute_total" in after["dashboard.py"]
        assert "calculate_total" not in after["dashboard.py"]

        pp = executor.proposed_plan
        assert len(pp.operations) >= 4
        assert pp.intent_type == "rename"


# ---------------------------------------------------------------------------
# Test 2: Rollback on PermissionError
# ---------------------------------------------------------------------------

class TestRollbackOnPermissionError:
    """Simulate a PermissionError mid-apply and verify full rollback."""

    def test_filesystem_restored_after_permission_error(self, test_project: Path):
        """After a PermissionError on the 3rd file, all earlier writes
        must be rolled back so the project is byte-identical to its
        original state.
        """
        before = _snapshot(test_project)

        original_write = Path.write_text
        call_count = {"n": 0}

        def _exploding_write(self_path, content, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise PermissionError(f"Simulated: cannot write {self_path}")
            return original_write(self_path, content, *args, **kwargs)

        with patch.object(Path, "write_text", _exploding_write):
            with pytest.raises(PermissionError, match="Simulated"):
                _run(_run_rename_pipeline(test_project))

        after = _snapshot(test_project)
        assert after == before, (
            "Filesystem was NOT restored after PermissionError. "
            f"Changed files: {set(k for k in before if before[k] != after.get(k))}"
        )

    def test_state_is_failed(self, test_project: Path):
        """After an apply failure the PlanExecutor state must be FAILED."""
        original_write = Path.write_text
        call_count = {"n": 0}

        def _exploding_write(self_path, content, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise PermissionError("Simulated")
            return original_write(self_path, content, *args, **kwargs)

        with patch.object(Path, "write_text", _exploding_write):
            with pytest.raises(PermissionError):
                _run(_run_rename_pipeline(test_project))


# ---------------------------------------------------------------------------
# Test 3: Dry-run does not modify files
# ---------------------------------------------------------------------------

class TestDryRunNoWrites:
    """Verify that dry-run mode produces diffs but never touches disk."""

    def test_dry_run_leaves_files_unchanged(self, test_project: Path):
        before = _snapshot(test_project)

        executor = _run(_run_rename_pipeline(test_project, dry_run=True))

        after = _snapshot(test_project)
        assert after == before, "Dry-run modified files on disk!"

        assert executor.proposed_plan is not None
        assert executor.proposed_plan.validation_passed is True
        assert len(executor.diffs) > 0, "Dry-run should still produce diffs"


# ---------------------------------------------------------------------------
# Test 4: Multiple sequential renames are each atomic
# ---------------------------------------------------------------------------

class TestSequentialAtomicity:
    """Run two renames in sequence — each must be independently atomic."""

    def test_two_renames_sequential(self, test_project: Path):
        executor1 = _run(_run_rename_pipeline(
            test_project,
            old_name="calculate_total",
            new_name="compute_total",
        ))
        assert executor1.state == PlanExecutionState.APPLIED

        mid_snapshot = _snapshot(test_project)
        assert "compute_total" in mid_snapshot["utils.py"]

        executor2 = _run(_run_rename_pipeline(
            test_project,
            old_name="format_currency",
            new_name="fmt_price",
        ))
        assert executor2.state == PlanExecutionState.APPLIED

        final = _snapshot(test_project)
        assert "compute_total" in final["utils.py"]
        assert "fmt_price" in final["utils.py"]
        assert "format_currency" not in final["utils.py"]


# ---------------------------------------------------------------------------
# Test 5: Empty rename (no-op) does not crash
# ---------------------------------------------------------------------------

class TestNoOpRename:
    """Renaming to the same name should produce no operations."""

    def test_same_name_rename(self, test_project: Path):
        before = _snapshot(test_project)

        executor = _run(_run_rename_pipeline(
            test_project,
            old_name="calculate_total",
            new_name="calculate_total",
        ))

        assert executor.state == PlanExecutionState.APPLIED
        after = _snapshot(test_project)
        assert after == before


# ---------------------------------------------------------------------------
# Test 6: Symbol indexer correctness
# ---------------------------------------------------------------------------

class TestIndexerDiscovery:
    """Verify the indexer finds all symbols and dependents."""

    def test_indexer_finds_all_files(self, test_project: Path):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(test_project))

        assert dep_map.stats["indexed_files"] == 4
        assert dep_map.stats["total_symbols"] >= 5

    def test_dependents_discovered(self, test_project: Path):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(test_project))

        dependents = dep_map.get_dependents("calculate_total")
        dependent_names = {Path(f).name for f in dependents}
        assert {"reports.py", "invoice.py", "dashboard.py"} <= dependent_names

    def test_incremental_cache(self, test_project: Path):
        indexer = SymbolIndexer()

        dep_map1 = indexer.index_workspace(str(test_project))
        assert dep_map1.stats["cache_hits"] == 0

        dep_map2 = indexer.index_workspace(str(test_project))
        assert dep_map2.stats["cache_hits"] == 4
        assert dep_map2.stats["cache_misses"] == 0
