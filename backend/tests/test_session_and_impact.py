"""Tests for Day 10: Session Management, Refinement, and Predictive Impact.

Covers:
  - Session creation, persistence, and retrieval.
  - Job recording within sessions.
  - Refinement context building (previous diffs injected into follow-ups).
  - Predictive impact analysis (blast radius tree).
  - Session-aware refactor pipeline (follow-up intents).
"""

from __future__ import annotations

import asyncio
import json
import textwrap
import time
from pathlib import Path
from typing import Dict

import pytest

from code4u.platform_core.agents.session_manager import (
    SessionManager,
    Session,
    RefactorJobRecord,
    DependencySnapshot,
)
from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    DependencyMap,
    SymbolIndexer,
)
from code4u.platform_core.agents.orchestrator import PlanExecutor
from code4u.code_intelligence.context.compiler import ContextCompiler
from code4u.code_intelligence.context.planner import plan_from_blast_context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

UTILS_PY = textwrap.dedent("""\
    def calculate_total(items):
        total = sum(item.price for item in items)
        return total

    def format_currency(amount):
        return f"${amount:.2f}"
""")

REPORTS_PY = textwrap.dedent("""\
    from utils import calculate_total, format_currency

    def generate_report(items):
        total = calculate_total(items)
        return f"Report: {format_currency(total)}"
""")

INVOICE_PY = textwrap.dedent("""\
    from utils import calculate_total

    def create_invoice(items, customer):
        total = calculate_total(items)
        return {"customer": customer, "total": total}
""")

DASHBOARD_PY = textwrap.dedent("""\
    from utils import calculate_total
    from reports import generate_report

    def render_dashboard(items):
        total = calculate_total(items)
        report = generate_report(items)
        return f"Dashboard: total={total}, report={report}"
""")

PROJECT_FILES: Dict[str, str] = {
    "utils.py": UTILS_PY,
    "reports.py": REPORTS_PY,
    "invoice.py": INVOICE_PY,
    "dashboard.py": DASHBOARD_PY,
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


@pytest.fixture
def session_dir(tmp_path: Path):
    d = tmp_path / "sessions"
    d.mkdir()
    return d


@pytest.fixture
def mgr(session_dir: Path) -> SessionManager:
    return SessionManager(sessions_dir=session_dir)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Test: Session lifecycle
# ---------------------------------------------------------------------------

class TestSessionLifecycle:
    def test_create_session(self, mgr: SessionManager):
        session = mgr.create_session("/my/project")
        assert session.session_id
        assert session.workspace_path == "/my/project"
        assert session.job_count == 0
        assert session.created_at > 0

    def test_get_session(self, mgr: SessionManager):
        session = mgr.create_session("/my/project")
        retrieved = mgr.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_nonexistent_session(self, mgr: SessionManager):
        assert mgr.get_session("nonexistent") is None

    def test_list_sessions(self, mgr: SessionManager):
        mgr.create_session("/project/a")
        mgr.create_session("/project/b")
        mgr.create_session("/project/c")
        sessions = mgr.list_sessions()
        assert len(sessions) == 3

    def test_delete_session(self, mgr: SessionManager):
        session = mgr.create_session("/my/project")
        assert mgr.delete_session(session.session_id)
        assert mgr.get_session(session.session_id) is None

    def test_delete_nonexistent(self, mgr: SessionManager):
        assert mgr.delete_session("nonexistent") is False

    def test_get_or_create_existing(self, mgr: SessionManager):
        original = mgr.create_session("/my/project")
        retrieved = mgr.get_or_create_session(
            "/my/project", session_id=original.session_id
        )
        assert retrieved.session_id == original.session_id

    def test_get_or_create_new(self, mgr: SessionManager):
        session = mgr.get_or_create_session("/my/project")
        assert session.session_id
        assert session.workspace_path == "/my/project"


# ---------------------------------------------------------------------------
# Test: Session persistence (survives restart)
# ---------------------------------------------------------------------------

class TestSessionPersistence:
    def test_session_persists_to_disk(self, session_dir: Path):
        mgr1 = SessionManager(sessions_dir=session_dir)
        session = mgr1.create_session("/my/project")
        sid = session.session_id

        fp = session_dir / f"{sid}.json"
        assert fp.exists()

        mgr2 = SessionManager(sessions_dir=session_dir)
        loaded = mgr2.get_session(sid)
        assert loaded is not None
        assert loaded.workspace_path == "/my/project"

    def test_jobs_persist_across_restarts(self, session_dir: Path):
        mgr1 = SessionManager(sessions_dir=session_dir)
        session = mgr1.create_session("/my/project")
        sid = session.session_id

        job = RefactorJobRecord(
            job_id="j1",
            intent="Rename foo to bar",
            intent_type="rename",
            file_path="/my/project/utils.py",
            affected_files=["/my/project/utils.py", "/my/project/reports.py"],
            diffs={"/my/project/utils.py": "--- a\n+++ b\n-foo\n+bar"},
            state="APPLIED",
            success=True,
        )
        mgr1.add_job(sid, job)

        mgr2 = SessionManager(sessions_dir=session_dir)
        loaded = mgr2.get_session(sid)
        assert loaded is not None
        assert loaded.job_count == 1
        assert loaded.last_job.intent == "Rename foo to bar"
        assert loaded.last_job.success


# ---------------------------------------------------------------------------
# Test: Job recording and session context
# ---------------------------------------------------------------------------

class TestJobRecording:
    def test_add_job(self, mgr: SessionManager):
        session = mgr.create_session("/my/project")
        job = RefactorJobRecord(
            job_id="j1",
            intent="Rename foo to bar",
            intent_type="rename",
            file_path="/utils.py",
            success=True,
            state="APPLIED",
        )
        updated = mgr.add_job(session.session_id, job)
        assert updated is not None
        assert updated.job_count == 1
        assert updated.last_job.intent == "Rename foo to bar"

    def test_multiple_jobs(self, mgr: SessionManager):
        session = mgr.create_session("/my/project")

        for i in range(3):
            mgr.add_job(session.session_id, RefactorJobRecord(
                job_id=f"j{i}",
                intent=f"intent_{i}",
                intent_type="rename",
                file_path="/utils.py",
                success=True,
                state="APPLIED",
            ))

        session = mgr.get_session(session.session_id)
        assert session.job_count == 3
        assert session.previous_intents == ["intent_0", "intent_1", "intent_2"]

    def test_last_successful_job_skips_failures(self, mgr: SessionManager):
        session = mgr.create_session("/my/project")

        mgr.add_job(session.session_id, RefactorJobRecord(
            job_id="j1", intent="good", intent_type="rename",
            file_path="/a.py", success=True, state="APPLIED",
        ))
        mgr.add_job(session.session_id, RefactorJobRecord(
            job_id="j2", intent="bad", intent_type="rename",
            file_path="/a.py", success=False, state="FAILED", error="boom",
        ))

        session = mgr.get_session(session.session_id)
        assert session.last_successful_job.intent == "good"
        assert session.last_job.intent == "bad"


# ---------------------------------------------------------------------------
# Test: Refinement context
# ---------------------------------------------------------------------------

class TestRefinementContext:
    def test_empty_session_returns_empty(self, mgr: SessionManager):
        assert mgr.build_refinement_context("nonexistent") == {}

    def test_context_includes_previous_diffs(self, mgr: SessionManager):
        session = mgr.create_session("/my/project")
        mgr.add_job(session.session_id, RefactorJobRecord(
            job_id="j1",
            intent="Rename calculate_total to compute_total",
            intent_type="rename",
            file_path="/utils.py",
            diffs={"/utils.py": "--- a\n+++ b\n-calculate_total\n+compute_total"},
            success=True,
            state="APPLIED",
        ))

        ctx = mgr.build_refinement_context(session.session_id)
        assert ctx["lastIntent"] == "Rename calculate_total to compute_total"
        assert "/utils.py" in ctx["lastDiffs"]
        assert ctx["jobCount"] == 1

    def test_context_tracks_all_intents(self, mgr: SessionManager):
        session = mgr.create_session("/my/project")
        for i, intent in enumerate(["first", "second", "third"]):
            mgr.add_job(session.session_id, RefactorJobRecord(
                job_id=f"j{i}", intent=intent, intent_type="rename",
                file_path="/a.py", success=True, state="APPLIED",
            ))

        ctx = mgr.build_refinement_context(session.session_id)
        assert ctx["previousIntents"] == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# Test: Predictive Impact (blast radius)
# ---------------------------------------------------------------------------

class TestPredictiveImpact:
    def test_calculate_total_has_dependents(self, dep_map: DependencyMap):
        dependents = dep_map.get_dependents("calculate_total")
        assert len(dependents) >= 3

    def test_transitive_dependents(self, dep_map: DependencyMap, test_project: Path):
        defs = dep_map.get_symbol_defs("calculate_total")
        assert defs
        defining_file = defs[0].file_path

        transitive = dep_map.get_transitive_dependents(
            "calculate_total", defining_file, max_depth=5
        )
        assert len(transitive) >= 3

    def test_format_currency_dependents(self, dep_map: DependencyMap):
        dependents = dep_map.get_dependents("format_currency")
        assert len(dependents) >= 1

    def test_leaf_function_no_dependents(self, dep_map: DependencyMap):
        dependents = dep_map.get_dependents("render_dashboard")
        assert len(dependents) == 0


# ---------------------------------------------------------------------------
# Test: Session-aware rename pipeline
# ---------------------------------------------------------------------------

class TestSessionAwareRename:
    def test_rename_within_session(self, test_project: Path, mgr: SessionManager):
        """Full test: rename within a session, then verify follow-up context."""
        workspace = str(test_project)
        session = mgr.create_session(workspace)

        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(workspace)

        async def _do_rename():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=workspace,
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(dependency_map=dep_map, dry_run=False)
            state = await executor.run(
                plan, blast, intent="Rename calculate_total to compute_total"
            )
            return executor, state

        executor, state = _run(_do_rename())

        assert state.value == "APPLIED"

        job = RefactorJobRecord(
            job_id="j1",
            intent="Rename calculate_total to compute_total",
            intent_type="rename",
            file_path=str(test_project / "utils.py"),
            affected_files=list(executor.proposed_plan.all_files),
            diffs=executor.diffs,
            plan_summary=executor.proposed_plan.summary,
            state=executor.state.value,
            execution_id=executor.execution_id,
            success=True,
        )
        mgr.add_job(session.session_id, job)

        ctx = mgr.build_refinement_context(session.session_id)
        assert ctx["lastIntent"] == "Rename calculate_total to compute_total"
        assert ctx["lastDiffs"]
        assert ctx["jobCount"] == 1
        assert ctx["lastIntentType"] == "rename"

    def test_follow_up_intent_building(self):
        """Verify that _build_refinement_intent produces the right format."""
        from code4u.interfaces.api.routes.refactor import _build_refinement_intent

        ctx = {
            "lastIntent": "Rename foo to bar",
            "lastDiffs": {
                "/a/utils.py": "--- a\n+++ b\n-foo\n+bar\n-foo\n+bar",
            },
        }
        result = _build_refinement_intent("Actually, use camelCase", ctx)
        assert "[Follow-up]" in result
        assert "Rename foo to bar" in result
        assert "Actually, use camelCase" in result
        assert "utils.py" in result


# ---------------------------------------------------------------------------
# Test: DependencySnapshot
# ---------------------------------------------------------------------------

class TestDependencySnapshot:
    def test_snapshot_roundtrip(self):
        snap = DependencySnapshot(
            indexed_files=50,
            total_symbols=200,
            total_imports=80,
            timestamp=time.time(),
        )
        data = snap.to_dict()
        restored = DependencySnapshot.from_dict(data)
        assert restored.indexed_files == 50
        assert restored.total_symbols == 200

    def test_session_with_snapshot(self, mgr: SessionManager):
        snap = DependencySnapshot(indexed_files=10, total_symbols=42)
        session = mgr.create_session("/project", dep_snapshot=snap)
        assert session.dep_snapshot is not None
        assert session.dep_snapshot.total_symbols == 42


# ---------------------------------------------------------------------------
# Test: Session summary
# ---------------------------------------------------------------------------

class TestSessionSummary:
    def test_summary_structure(self, mgr: SessionManager):
        session = mgr.create_session("/my/project")
        summary = session.summary
        assert "sessionId" in summary
        assert "workspacePath" in summary
        assert "jobCount" in summary
        assert summary["jobCount"] == 0
        assert summary["lastIntent"] is None

    def test_summary_after_job(self, mgr: SessionManager):
        session = mgr.create_session("/my/project")
        mgr.add_job(session.session_id, RefactorJobRecord(
            job_id="j1", intent="Rename x to y", intent_type="rename",
            file_path="/a.py", success=True, state="APPLIED",
        ))
        session = mgr.get_session(session.session_id)
        summary = session.summary
        assert summary["jobCount"] == 1
        assert summary["lastIntent"] == "Rename x to y"
        assert summary["lastState"] == "APPLIED"
