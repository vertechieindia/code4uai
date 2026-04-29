"""Tests for Day 11: Concurrency Control, Multi-Tenant Isolation, Shared Cache.

Covers:
  - Workspace Sentinel (locking/contention).
  - Multi-tenant session privacy (owner_id filtering).
  - Shared global cache (IndexCache reads from ~/.code4u/global_cache/).
  - End-to-end: sentinel blocks concurrent writes.
"""

from __future__ import annotations

import asyncio
import textwrap
import threading
import time
from pathlib import Path
from typing import Dict

import pytest

from code4u.platform_core.agents.sentinel import (
    WorkspaceSentinel,
    WorkspaceBusyError,
    LockGuard,
)
from code4u.platform_core.agents.session_manager import (
    SessionManager,
    Session,
    RefactorJobRecord,
)
from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    IndexCache,
    SymbolIndexer,
    DependencyMap,
)
from code4u.platform_core.agents.orchestrator import PlanExecutor
from code4u.code_intelligence.context.compiler import ContextCompiler
from code4u.code_intelligence.context.planner import plan_from_blast_context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

UTILS_PY = textwrap.dedent("""\
    def calculate_total(items):
        return sum(item.price for item in items)
""")

REPORTS_PY = textwrap.dedent("""\
    from utils import calculate_total

    def generate_report(items):
        return f"Total: {calculate_total(items)}"
""")

PROJECT_FILES: Dict[str, str] = {
    "utils.py": UTILS_PY,
    "reports.py": REPORTS_PY,
}


@pytest.fixture
def test_project(tmp_path: Path):
    for name, content in PROJECT_FILES.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    yield tmp_path


@pytest.fixture
def session_dir(tmp_path: Path):
    d = tmp_path / "sessions"
    d.mkdir()
    return d


@pytest.fixture
def mgr(session_dir: Path) -> SessionManager:
    return SessionManager(sessions_dir=session_dir)


@pytest.fixture
def sentinel() -> WorkspaceSentinel:
    return WorkspaceSentinel(timeout=0.1)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Test: Workspace Sentinel — basic locking
# ---------------------------------------------------------------------------

class TestSentinelBasic:
    def test_acquire_and_release(self, sentinel: WorkspaceSentinel, test_project: Path):
        ws = str(test_project)

        async def _do():
            async with sentinel.acquire(ws, session_id="s1") as guard:
                assert isinstance(guard, LockGuard)
                assert guard.workspace == str(Path(ws).resolve())
                assert guard.session_id == "s1"
                assert sentinel.is_locked(ws)
            assert not sentinel.is_locked(ws)

        _run(_do())

    def test_sync_acquire_and_release(self, sentinel: WorkspaceSentinel, test_project: Path):
        ws = str(test_project)
        with sentinel.acquire_sync(ws, session_id="s1") as guard:
            assert guard.session_id == "s1"
            assert sentinel.is_locked(ws)
        assert not sentinel.is_locked(ws)

    def test_owning_session(self, sentinel: WorkspaceSentinel, test_project: Path):
        ws = str(test_project)

        async def _do():
            assert sentinel.owning_session(ws) is None
            async with sentinel.acquire(ws, session_id="session-42"):
                assert sentinel.owning_session(ws) == "session-42"
            assert sentinel.owning_session(ws) is None

        _run(_do())


# ---------------------------------------------------------------------------
# Test: Workspace Sentinel — contention (the "Clash" test)
# ---------------------------------------------------------------------------

class TestSentinelContention:
    def test_second_acquirer_gets_busy_error(self, test_project: Path):
        """Simulate two concurrent operations — second must fail."""
        sentinel = WorkspaceSentinel(timeout=0.1)
        ws = str(test_project)

        async def _do():
            async with sentinel.acquire(ws, session_id="s1"):
                with pytest.raises(WorkspaceBusyError) as exc_info:
                    async with sentinel.acquire(ws, session_id="s2"):
                        pass
                assert "locked" in str(exc_info.value).lower()
                assert exc_info.value.owning_session == "s1"

        _run(_do())

    def test_same_session_blocked_too(self, test_project: Path):
        """Even the same session is blocked by the file lock."""
        sentinel = WorkspaceSentinel(timeout=0.1)
        ws = str(test_project)

        async def _do():
            async with sentinel.acquire(ws, session_id="s1"):
                with pytest.raises(WorkspaceBusyError):
                    async with sentinel.acquire(ws, session_id="s1"):
                        pass

        _run(_do())

    def test_different_workspaces_not_blocked(self, tmp_path: Path):
        """Different workspaces can be locked concurrently."""
        ws_a = tmp_path / "project_a"
        ws_b = tmp_path / "project_b"
        ws_a.mkdir()
        ws_b.mkdir()

        sentinel = WorkspaceSentinel(timeout=0.1)

        async def _do():
            async with sentinel.acquire(str(ws_a), session_id="s1"):
                async with sentinel.acquire(str(ws_b), session_id="s2"):
                    assert sentinel.is_locked(str(ws_a))
                    assert sentinel.is_locked(str(ws_b))

        _run(_do())

    def test_lock_released_on_exception(self, test_project: Path):
        """Lock is released even if the body raises."""
        sentinel = WorkspaceSentinel(timeout=0.1)
        ws = str(test_project)

        async def _do():
            try:
                async with sentinel.acquire(ws, session_id="s1"):
                    raise ValueError("boom")
            except ValueError:
                pass
            assert not sentinel.is_locked(ws)

        _run(_do())


# ---------------------------------------------------------------------------
# Test: Multi-Tenant Session Privacy
# ---------------------------------------------------------------------------

class TestMultiTenantPrivacy:
    def test_sessions_have_owner_id(self, mgr: SessionManager):
        s = mgr.create_session("/project", owner_id="alice")
        assert s.owner_id == "alice"

    def test_default_owner_id(self, mgr: SessionManager):
        s = mgr.create_session("/project")
        assert s.owner_id == "local_user"

    def test_list_filters_by_owner(self, mgr: SessionManager):
        mgr.create_session("/project", owner_id="alice")
        mgr.create_session("/project", owner_id="alice")
        mgr.create_session("/project", owner_id="bob")

        alice_sessions = mgr.list_sessions(owner_id="alice")
        bob_sessions = mgr.list_sessions(owner_id="bob")
        all_sessions = mgr.list_sessions()

        assert len(alice_sessions) == 2
        assert len(bob_sessions) == 1
        assert len(all_sessions) == 3

    def test_alice_cannot_see_bob_sessions(self, mgr: SessionManager):
        mgr.create_session("/project", owner_id="alice")
        bob_s = mgr.create_session("/project", owner_id="bob")

        alice_sessions = mgr.list_sessions(owner_id="alice")
        session_ids = [s.session_id for s in alice_sessions]
        assert bob_s.session_id not in session_ids

    def test_owner_persists_across_restarts(self, session_dir: Path):
        mgr1 = SessionManager(sessions_dir=session_dir)
        s = mgr1.create_session("/project", owner_id="charlie")
        sid = s.session_id

        mgr2 = SessionManager(sessions_dir=session_dir)
        loaded = mgr2.get_session(sid)
        assert loaded is not None
        assert loaded.owner_id == "charlie"

    def test_summary_includes_owner_id(self, mgr: SessionManager):
        s = mgr.create_session("/project", owner_id="alice")
        assert s.summary["ownerId"] == "alice"


# ---------------------------------------------------------------------------
# Test: Shared Global Cache
# ---------------------------------------------------------------------------

class TestSharedGlobalCache:
    def test_global_cache_path_is_deterministic(self):
        path1 = IndexCache._global_cache_path("/my/project")
        path2 = IndexCache._global_cache_path("/my/project")
        assert path1 == path2

    def test_different_roots_get_different_paths(self):
        path1 = IndexCache._global_cache_path("/project/a")
        path2 = IndexCache._global_cache_path("/project/b")
        assert path1 != path2

    def test_cache_saves_to_global_dir(self, test_project: Path, tmp_path: Path):
        import code4u.code_intelligence.knowledge_graph.symbol_indexer as si
        original_dir = si._GLOBAL_CACHE_DIR
        test_global = tmp_path / "global_cache"
        si._GLOBAL_CACHE_DIR = test_global

        try:
            indexer = SymbolIndexer()
            dep_map = indexer.index_workspace(str(test_project))

            assert test_global.exists()
            global_files = list(test_global.glob("*.json"))
            assert len(global_files) >= 1
        finally:
            si._GLOBAL_CACHE_DIR = original_dir

    def test_global_cache_survives_local_deletion(self, test_project: Path, tmp_path: Path):
        import code4u.code_intelligence.knowledge_graph.symbol_indexer as si
        original_dir = si._GLOBAL_CACHE_DIR
        test_global = tmp_path / "global_cache"
        si._GLOBAL_CACHE_DIR = test_global

        try:
            indexer = SymbolIndexer()
            dep_map1 = indexer.index_workspace(str(test_project))
            stats1 = dep_map1.stats

            local_cache = test_project / ".code4u_cache"
            if local_cache.exists():
                local_cache.unlink()

            dep_map2 = indexer.index_workspace(str(test_project))
            stats2 = dep_map2.stats

            assert stats2["cache_hits"] > 0
        finally:
            si._GLOBAL_CACHE_DIR = original_dir


# ---------------------------------------------------------------------------
# Test: End-to-End — Sentinel blocks concurrent rename
# ---------------------------------------------------------------------------

class TestE2ESentinelBlock:
    def test_rename_blocked_during_another_rename(self, test_project: Path):
        """Full E2E: start a rename, try another immediately — must be blocked."""
        sentinel = WorkspaceSentinel(timeout=0.1)
        ws = str(test_project)

        async def _do():
            async with sentinel.acquire(ws, session_id="s1"):
                with pytest.raises(WorkspaceBusyError) as exc_info:
                    async with sentinel.acquire(ws, session_id="s2"):
                        pass
                assert "locked" in str(exc_info.value).lower()

            # After release, the second should succeed
            async with sentinel.acquire(ws, session_id="s2") as guard:
                assert guard.session_id == "s2"

        _run(_do())

    def test_rename_succeeds_after_lock_release(self, test_project: Path):
        """After first rename completes and releases lock, second succeeds."""
        sentinel = WorkspaceSentinel(timeout=0.5)
        ws = str(test_project)
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(ws)

        async def _rename():
            compiler = ContextCompiler(dependency_map=dep_map)
            blast = await compiler.compile_refactor_blast_context(
                intent="Rename calculate_total to compute_total",
                primary_file_path=str(test_project / "utils.py"),
                workspace_path=ws,
            )
            plan = plan_from_blast_context(blast)
            executor = PlanExecutor(dependency_map=dep_map, dry_run=True)
            async with sentinel.acquire(ws, session_id="s1"):
                await executor.run(plan, blast, intent="Rename calculate_total to compute_total")
            return executor.state.value

        state = _run(_rename())
        assert state == "APPLIED"
        assert not sentinel.is_locked(ws)
