"""Tests for Day 12: Real-Time Streaming & Observability.

Covers:
  - PlanExecutor status_callback emits events at each pipeline stage.
  - SSE event queue creation, pushing, and cleanup.
  - make_status_callback wires correctly.
  - Events emitted for generate, validate, diff, apply phases.
  - Streaming continues through full pipeline.
  - Error events emitted on pipeline failure.
"""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path
from typing import Any, Dict, List

import pytest

from code4u.platform_core.agents.orchestrator import PlanExecutor
from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    SymbolIndexer,
    DependencyMap,
)
from code4u.code_intelligence.context.compiler import ContextCompiler
from code4u.code_intelligence.context.planner import plan_from_blast_context
from code4u.interfaces.api.routes.events import (
    get_or_create_queue,
    push_event,
    cleanup_queue,
    make_status_callback,
    _event_queues,
)


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
    from utils import calculate_total, format_currency

    def generate_report(items):
        total = calculate_total(items)
        return f"Total: {format_currency(total)}"
""")

INVOICE_PY = textwrap.dedent("""\
    from utils import calculate_total

    def create_invoice(items, customer):
        total = calculate_total(items)
        return {"customer": customer, "total": total}
""")

PROJECT_FILES: Dict[str, str] = {
    "utils.py": UTILS_PY,
    "reports.py": REPORTS_PY,
    "invoice.py": INVOICE_PY,
}


@pytest.fixture
def test_project(tmp_path: Path):
    for name, content in PROJECT_FILES.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    yield tmp_path


@pytest.fixture
def dep_map(test_project: Path) -> DependencyMap:
    indexer = SymbolIndexer()
    return indexer.index_workspace(str(test_project))


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Test: Event Queue Management
# ---------------------------------------------------------------------------

class TestEventQueueManagement:
    def test_get_or_create_queue(self):
        q = get_or_create_queue("test-job-1")
        assert q is not None
        assert "test-job-1" in _event_queues
        cleanup_queue("test-job-1")

    def test_push_event_to_queue(self):
        q = get_or_create_queue("test-job-2")
        push_event("test-job-2", {"type": "test", "message": "hello"})
        assert not q.empty()
        event = q.get_nowait()
        assert event["type"] == "test"
        assert event["message"] == "hello"
        cleanup_queue("test-job-2")

    def test_push_event_no_queue_is_safe(self):
        push_event("nonexistent-job", {"type": "test"})

    def test_cleanup_removes_queue(self):
        get_or_create_queue("test-job-3")
        cleanup_queue("test-job-3")
        assert "test-job-3" not in _event_queues

    def test_make_status_callback(self):
        cb = make_status_callback("test-job-4")
        assert callable(cb)
        q = _event_queues.get("test-job-4")
        assert q is not None
        cb({"type": "test", "message": "via callback"})
        event = q.get_nowait()
        assert event["message"] == "via callback"
        cleanup_queue("test-job-4")


# ---------------------------------------------------------------------------
# Test: PlanExecutor emits status events
# ---------------------------------------------------------------------------

class TestStatusCallback:
    def test_callback_receives_pipeline_events(self, test_project: Path, dep_map: DependencyMap):
        """Full rename pipeline emits events at every milestone."""
        events: List[Dict[str, Any]] = []

        def collect(event: Dict[str, Any]):
            events.append(event)

        async def _do():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=str(test_project),
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(
                dependency_map=dep_map,
                dry_run=True,
                status_callback=collect,
            )
            await executor.run(plan, blast, intent="Rename calculate_total to compute_total")
            return executor

        executor = _run(_do())

        event_types = [e["type"] for e in events]
        assert "pipeline_start" in event_types
        assert "step_start" in event_types
        assert "generate" in event_types
        assert "generate_complete" in event_types
        assert "validate" in event_types
        assert "step_complete" in event_types
        assert "pipeline_complete" in event_types

    def test_generate_complete_includes_affected_files(self, test_project: Path, dep_map: DependencyMap):
        events: List[Dict[str, Any]] = []

        async def _do():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=str(test_project),
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(
                dependency_map=dep_map,
                dry_run=True,
                status_callback=lambda e: events.append(e),
            )
            await executor.run(plan, blast, intent="Rename calculate_total to compute_total")

        _run(_do())

        gen_complete = [e for e in events if e["type"] == "generate_complete"]
        assert len(gen_complete) == 1
        assert "affectedFiles" in gen_complete[0]
        assert len(gen_complete[0]["affectedFiles"]) >= 3

    def test_validate_emits_per_file(self, test_project: Path, dep_map: DependencyMap):
        events: List[Dict[str, Any]] = []

        async def _do():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=str(test_project),
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(
                dependency_map=dep_map,
                dry_run=True,
                status_callback=lambda e: events.append(e),
            )
            await executor.run(plan, blast, intent="Rename calculate_total to compute_total")

        _run(_do())

        validate_events = [e for e in events if e["type"] == "validate"]
        assert len(validate_events) >= 3
        for ve in validate_events:
            assert "file" in ve
            assert "validatedSoFar" in ve

    def test_diff_emits_per_file(self, test_project: Path, dep_map: DependencyMap):
        events: List[Dict[str, Any]] = []

        async def _do():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=str(test_project),
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(
                dependency_map=dep_map,
                dry_run=True,
                status_callback=lambda e: events.append(e),
            )
            await executor.run(plan, blast, intent="Rename calculate_total to compute_total")

        _run(_do())

        diff_events = [e for e in events if e["type"] == "diff"]
        assert len(diff_events) >= 3
        for de in diff_events:
            assert "file" in de
            assert "action" in de
            assert "diffIndex" in de

    def test_apply_emits_per_file(self, test_project: Path, dep_map: DependencyMap):
        """Non-dry-run apply emits per-file events."""
        events: List[Dict[str, Any]] = []

        async def _do():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=str(test_project),
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(
                dependency_map=dep_map,
                dry_run=False,
                status_callback=lambda e: events.append(e),
            )
            await executor.run(plan, blast, intent="Rename calculate_total to compute_total")

        _run(_do())

        apply_events = [e for e in events if e["type"] == "apply"]
        assert len(apply_events) >= 3
        for ae in apply_events:
            assert "file" in ae
            assert "action" in ae
            assert ae["action"] == "edit"

    def test_pipeline_complete_has_duration(self, test_project: Path, dep_map: DependencyMap):
        events: List[Dict[str, Any]] = []

        async def _do():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=str(test_project),
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(
                dependency_map=dep_map,
                dry_run=True,
                status_callback=lambda e: events.append(e),
            )
            await executor.run(plan, blast, intent="Rename calculate_total to compute_total")

        _run(_do())

        complete = [e for e in events if e["type"] == "pipeline_complete"]
        assert len(complete) == 1
        assert "durationMs" in complete[0]
        assert complete[0]["durationMs"] >= 0

    def test_no_callback_means_no_crash(self, test_project: Path, dep_map: DependencyMap):
        """PlanExecutor works perfectly fine without a callback."""

        async def _do():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=str(test_project),
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(dependency_map=dep_map, dry_run=True)
            await executor.run(plan, blast, intent="Rename calculate_total to compute_total")
            return executor.state.value

        state = _run(_do())
        assert state == "APPLIED"


# ---------------------------------------------------------------------------
# Test: Error events
# ---------------------------------------------------------------------------

class TestErrorEvents:
    def test_pipeline_error_event_emitted(self, test_project: Path, dep_map: DependencyMap):
        """If the pipeline fails, a pipeline_error event is emitted."""
        events: List[Dict[str, Any]] = []

        async def _do():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=str(test_project),
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(
                dependency_map=dep_map,
                dry_run=False,
                status_callback=lambda e: events.append(e),
            )
            # Sabotage: make a file read-only to trigger a write failure
            import os
            target = test_project / "utils.py"
            os.chmod(str(target), 0o444)
            try:
                await executor.run(plan, blast, intent="Rename calculate_total to compute_total")
            except Exception:
                pass
            finally:
                os.chmod(str(target), 0o644)

        _run(_do())

        error_events = [e for e in events if e["type"] == "pipeline_error"]
        assert len(error_events) == 1
        assert "error" in error_events[0]


# ---------------------------------------------------------------------------
# Test: SSE callback via make_status_callback
# ---------------------------------------------------------------------------

class TestMakeStatusCallback:
    def test_callback_pushes_to_queue(self):
        cb = make_status_callback("stream-test-1")
        cb({"type": "step_start", "message": "GENERATE_CODE"})
        cb({"type": "step_complete", "message": "done"})

        q = _event_queues["stream-test-1"]
        events = []
        while not q.empty():
            events.append(q.get_nowait())

        assert len(events) == 2
        assert events[0]["type"] == "step_start"
        assert events[1]["type"] == "step_complete"
        cleanup_queue("stream-test-1")

    def test_full_pipeline_with_queue_callback(self, test_project: Path, dep_map: DependencyMap):
        """Full pipeline wired through make_status_callback pushes all events to queue."""
        cb = make_status_callback("stream-test-2")

        async def _do():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename format_currency to fmt_money",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=str(test_project),
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(
                dependency_map=dep_map,
                dry_run=True,
                status_callback=cb,
            )
            await executor.run(plan, blast, intent="Rename format_currency to fmt_money")

        _run(_do())

        q = _event_queues["stream-test-2"]
        events = []
        while not q.empty():
            events.append(q.get_nowait())

        event_types = {e["type"] for e in events}
        assert "pipeline_start" in event_types
        assert "generate_complete" in event_types
        assert "pipeline_complete" in event_types
        assert len(events) >= 10
        cleanup_queue("stream-test-2")


# ---------------------------------------------------------------------------
# Test: Progress fractions
# ---------------------------------------------------------------------------

class TestProgressFractions:
    def test_step_start_has_progress(self, test_project: Path, dep_map: DependencyMap):
        events: List[Dict[str, Any]] = []

        async def _do():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=str(test_project),
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(
                dependency_map=dep_map,
                dry_run=True,
                status_callback=lambda e: events.append(e),
            )
            await executor.run(plan, blast, intent="Rename calculate_total to compute_total")

        _run(_do())

        step_starts = [e for e in events if e["type"] == "step_start"]
        assert len(step_starts) >= 3
        for ss in step_starts:
            assert "progress" in ss
            assert 0 < ss["progress"] <= 1.0
