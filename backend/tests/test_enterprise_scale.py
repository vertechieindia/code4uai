"""Day 17 — Enterprise Monolith: parallel indexing, multi-root resolution, watcher.

Tests:
  - Parallel indexer: single-root, multi-root, cache integration.
  - Multi-root resolution: find_symbol, find_symbol_across_roots, cross-root rename.
  - File watcher: PartialReindexJob, debounce, force_reindex, start/stop.
  - Standalone parsers: _parse_python, _parse_typescript.
  - Performance: parallel vs. linear comparison.
"""

from __future__ import annotations

import os
import time
import threading
from pathlib import Path
from typing import List
from unittest.mock import patch, MagicMock

import pytest

from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    SymbolIndexer,
    DependencyMap,
    SymbolDef,
    ImportRef,
    ExportRef,
    _parse_python,
    _parse_typescript,
    _parse_file_worker,
)
from code4u.core.watcher import (
    WorkspaceWatcher,
    PartialReindexJob,
)


# ---------------------------------------------------------------------------
# Fixtures — test workspaces
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_project(tmp_path):
    """Create a small Python project (5 files)."""
    (tmp_path / "utils.py").write_text(
        "def calculate_total(items):\n    return sum(items)\n\n"
        "def format_currency(amount):\n    return f'${amount:.2f}'\n"
    )
    (tmp_path / "models.py").write_text(
        "class Order:\n    def __init__(self):\n        self.items = []\n"
    )
    (tmp_path / "reports.py").write_text(
        "from utils import calculate_total\n\n"
        "def generate_report(orders):\n"
        "    totals = [calculate_total(o.items) for o in orders]\n"
        "    return totals\n"
    )
    (tmp_path / "invoice.py").write_text(
        "from utils import calculate_total, format_currency\n\n"
        "def create_invoice(order):\n"
        "    total = calculate_total(order.items)\n"
        "    return format_currency(total)\n"
    )
    (tmp_path / "dashboard.py").write_text(
        "from reports import generate_report\n\n"
        "def show_dashboard(orders):\n    return generate_report(orders)\n"
    )
    return tmp_path


@pytest.fixture
def multi_root_workspace(tmp_path):
    """Create two sibling projects sharing a symbol name."""
    backend = tmp_path / "backend"
    frontend = tmp_path / "frontend"
    shared = tmp_path / "shared"
    backend.mkdir()
    frontend.mkdir()
    shared.mkdir()

    (shared / "types.py").write_text(
        "class UserProfile:\n    name: str\n    email: str\n"
    )
    (backend / "api.py").write_text(
        "from types import UserProfile\n\n"
        "def get_user() -> UserProfile:\n    return UserProfile()\n"
    )
    (frontend / "display.tsx").write_text(
        "import { UserProfile } from '../shared/types'\n\n"
        "export const UserCard = (user: UserProfile) => {\n"
        "  return <div>{user.name}</div>\n}\n"
    )
    (backend / "service.py").write_text(
        "from types import UserProfile\n\n"
        "def update_user(u: UserProfile) -> None:\n    pass\n"
    )

    return {"backend": str(backend), "frontend": str(frontend), "shared": str(shared)}


@pytest.fixture
def large_project(tmp_path):
    """Generate a 200-file project for performance testing."""
    for i in range(200):
        pkg = f"pkg{i // 20}"
        pkg_dir = tmp_path / pkg
        pkg_dir.mkdir(exist_ok=True)
        (pkg_dir / f"module_{i}.py").write_text(
            f"def func_{i}(x):\n    return x + {i}\n\n"
            f"class Class_{i}:\n    pass\n"
        )
    for i in range(0, 200, 10):
        pkg = f"pkg{i // 20}"
        caller = tmp_path / pkg / f"caller_{i}.py"
        caller.write_text(
            f"from module_{i} import func_{i}\n\n"
            f"result = func_{i}(42)\n"
        )
    return tmp_path


# ═══════════════════════════════════════════════════════════════════════════
# Standalone parser tests
# ═══════════════════════════════════════════════════════════════════════════

class TestStandaloneParsers:
    def test_parse_python_function(self, tmp_path):
        code = "def hello(name):\n    return f'Hello {name}'\n"
        syms, imps = _parse_python("/fake/test.py", code)
        assert len(syms) == 1
        assert syms[0].name == "hello"
        assert syms[0].kind == "function"

    def test_parse_python_class(self, tmp_path):
        code = "class MyService:\n    def run(self):\n        pass\n"
        syms, _ = _parse_python("/fake/svc.py", code)
        names = {s.name for s in syms}
        assert "MyService" in names
        assert "run" in names

    def test_parse_python_imports(self):
        code = "from utils import calculate_total, format_currency\nimport os\n"
        _, imps = _parse_python("/fake/app.py", code)
        assert len(imps) == 2
        modules = {i.module for i in imps}
        assert "utils" in modules
        assert "os" in modules

    def test_parse_python_syntax_error(self):
        code = "def broken(:\n    pass"
        syms, imps = _parse_python("/fake/bad.py", code)
        assert syms == []
        assert imps == []

    def test_parse_typescript_function(self):
        code = "export function fetchData(url: string): Promise<any> {\n  return fetch(url)\n}\n"
        syms, _ = _parse_typescript("/fake/api.ts", code)
        assert len(syms) == 1
        assert syms[0].name == "fetchData"
        assert syms[0].is_exported is True

    def test_parse_typescript_imports(self):
        code = "import { useState, useEffect } from 'react'\n"
        _, imps = _parse_typescript("/fake/app.tsx", code)
        assert len(imps) == 1
        assert "useState" in imps[0].names
        assert "useEffect" in imps[0].names

    def test_parse_file_worker_python(self):
        result = _parse_file_worker(
            "/fake/test.py",
            "def greet():\n    pass\n",
            ".py",
        )
        assert result["file_path"] == "/fake/test.py"
        assert len(result["symbols"]) == 1
        assert result["symbols"][0]["name"] == "greet"

    def test_parse_file_worker_typescript(self):
        result = _parse_file_worker(
            "/fake/app.tsx",
            "export const App = () => {\n  return <div />\n}\n",
            ".tsx",
        )
        assert len(result["symbols"]) == 1
        assert result["symbols"][0]["name"] == "App"


# ═══════════════════════════════════════════════════════════════════════════
# Parallel indexer tests
# ═══════════════════════════════════════════════════════════════════════════

class TestParallelIndexer:
    def test_parallel_single_root(self, simple_project):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace_parallel(
            str(simple_project), use_cache=False,
        )
        assert dep_map.stats["indexed_files"] == 5
        assert dep_map.has_symbol("calculate_total")
        assert dep_map.has_symbol("Order")
        assert dep_map.has_symbol("generate_report")

    def test_parallel_matches_linear(self, simple_project):
        """Parallel and linear indexing must produce identical results."""
        indexer = SymbolIndexer()
        linear = indexer.index_workspace(str(simple_project), use_cache=False)
        parallel = indexer.index_workspace_parallel(
            str(simple_project), use_cache=False,
        )
        assert linear.stats["indexed_files"] == parallel.stats["indexed_files"]
        assert linear.stats["unique_symbol_names"] == parallel.stats["unique_symbol_names"]
        assert linear.stats["total_imports"] == parallel.stats["total_imports"]

    def test_parallel_dependents(self, simple_project):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace_parallel(
            str(simple_project), use_cache=False,
        )
        deps = dep_map.get_dependents("calculate_total")
        basenames = {Path(d).name for d in deps}
        assert "reports.py" in basenames
        assert "invoice.py" in basenames

    def test_parallel_with_cache(self, simple_project):
        indexer = SymbolIndexer()
        dm1 = indexer.index_workspace_parallel(
            str(simple_project), use_cache=True,
        )
        dm2 = indexer.index_workspace_parallel(
            str(simple_project), use_cache=True,
        )
        assert dm2.stats["cache_hits"] >= dm1.stats["indexed_files"]

    def test_parallel_not_a_directory(self):
        indexer = SymbolIndexer()
        with pytest.raises(NotADirectoryError):
            indexer.index_workspace_parallel("/nonexistent/path")

    def test_parallel_multi_root(self, multi_root_workspace):
        indexer = SymbolIndexer()
        dep_map = indexer.index_multi_workspace_parallel(
            list(multi_root_workspace.values()),
            use_cache=False,
        )
        assert dep_map.is_multi_root
        assert dep_map.stats["root_count"] == 3
        assert dep_map.has_symbol("UserProfile")
        assert dep_map.has_symbol("get_user")
        assert dep_map.has_symbol("UserCard")

    def test_parallel_multi_root_single(self, simple_project):
        """Single-root falls back to index_workspace_parallel."""
        indexer = SymbolIndexer()
        dep_map = indexer.index_multi_workspace_parallel(
            [str(simple_project)], use_cache=False,
        )
        assert dep_map.stats["indexed_files"] == 5

    def test_parallel_multi_root_empty(self):
        indexer = SymbolIndexer()
        with pytest.raises(ValueError):
            indexer.index_multi_workspace_parallel([])

    def test_collect_files(self, simple_project):
        indexer = SymbolIndexer()
        files = indexer._collect_files(simple_project)
        assert len(files) == 5
        extensions = {ext for _, ext in files}
        assert extensions == {".py"}


# ═══════════════════════════════════════════════════════════════════════════
# Multi-root resolution tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMultiRootResolution:
    def test_find_symbol_basic(self, simple_project):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)
        results = dep_map.find_symbol("calculate_total")
        assert len(results) == 1
        assert results[0].name == "calculate_total"

    def test_find_symbol_not_found(self, simple_project):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)
        assert dep_map.find_symbol("nonexistent") == []

    def test_find_symbol_preferred_root(self, multi_root_workspace):
        indexer = SymbolIndexer()
        dep_map = indexer.index_multi_workspace(
            list(multi_root_workspace.values()), use_cache=False,
        )
        shared_root = multi_root_workspace["shared"]
        results = dep_map.find_symbol("UserProfile", preferred_root=shared_root)
        assert len(results) >= 1
        assert Path(results[0].file_path).parent == Path(shared_root)

    def test_find_symbol_across_roots(self, multi_root_workspace):
        indexer = SymbolIndexer()
        dep_map = indexer.index_multi_workspace(
            list(multi_root_workspace.values()), use_cache=False,
        )
        grouped = dep_map.find_symbol_across_roots("UserProfile")
        shared_root = multi_root_workspace["shared"]
        assert shared_root in grouped
        assert len(grouped[shared_root]) == 1

    def test_cross_root_rename_detection(self, multi_root_workspace):
        """Renaming a symbol in shared/ should affect both backend/ and frontend/."""
        indexer = SymbolIndexer()
        dep_map = indexer.index_multi_workspace(
            list(multi_root_workspace.values()), use_cache=False,
        )
        deps = dep_map.get_dependents("UserProfile")
        roots_hit = set()
        for dep in deps:
            root = dep_map.get_root_for_file(dep)
            if root:
                roots_hit.add(root)
        assert len(roots_hit) >= 2

    def test_all_files_property(self, simple_project):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)
        all_f = dep_map.all_files
        assert len(all_f) == 5
        assert all_f == sorted(all_f)

    def test_sibling_root_search(self, tmp_path):
        """Rename in Folder A finds callers in Folder B."""
        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        repo_a.mkdir()
        repo_b.mkdir()

        (repo_a / "core.py").write_text(
            "def shared_function():\n    return 42\n"
        )
        (repo_b / "consumer.py").write_text(
            "from core import shared_function\n\n"
            "result = shared_function()\n"
        )

        indexer = SymbolIndexer()
        dep_map = indexer.index_multi_workspace(
            [str(repo_a), str(repo_b)], use_cache=False,
        )

        affected = dep_map.get_affected_files(
            "shared_function",
            str(repo_a / "core.py"),
        )
        basenames = {Path(f).name for f in affected}
        assert "core.py" in basenames
        assert "consumer.py" in basenames

    def test_cross_root_dependents_grouped(self, multi_root_workspace):
        indexer = SymbolIndexer()
        dep_map = indexer.index_multi_workspace(
            list(multi_root_workspace.values()), use_cache=False,
        )
        shared_types = str(Path(multi_root_workspace["shared"]) / "types.py")
        grouped = dep_map.get_cross_root_dependents("UserProfile", shared_types)
        assert len(grouped) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# File watcher tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPartialReindexJob:
    def test_job_creation(self):
        job = PartialReindexJob(
            file_path="/tmp/test.py",
            event_type="modified",
            root_path="/tmp",
        )
        assert job.file_path == "/tmp/test.py"
        assert job.event_type == "modified"
        assert job.duration_ms == 0.0

    def test_job_to_dict(self):
        job = PartialReindexJob(
            file_path="/tmp/test.py",
            event_type="created",
            root_path="/tmp",
        )
        job.duration_ms = 1.5
        d = job.to_dict()
        assert d["filePath"] == "/tmp/test.py"
        assert d["eventType"] == "created"
        assert d["durationMs"] == 1.5


class TestWorkspaceWatcher:
    def test_watcher_creation(self, simple_project):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)
        watcher = WorkspaceWatcher(
            workspace_path=str(simple_project),
            dep_map=dep_map,
        )
        assert not watcher.is_running
        assert watcher.recent_jobs == []

    def test_watcher_start_stop(self, simple_project):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)
        watcher = WorkspaceWatcher(
            workspace_path=str(simple_project),
            dep_map=dep_map,
        )
        watcher.start()
        assert watcher.is_running
        watcher.stop()
        assert not watcher.is_running

    def test_watcher_double_start(self, simple_project):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)
        watcher = WorkspaceWatcher(
            workspace_path=str(simple_project),
            dep_map=dep_map,
        )
        watcher.start()
        watcher.start()
        assert watcher.is_running
        watcher.stop()

    def test_watcher_double_stop(self, simple_project):
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)
        watcher = WorkspaceWatcher(
            workspace_path=str(simple_project),
            dep_map=dep_map,
        )
        watcher.stop()
        assert not watcher.is_running

    def test_force_reindex_modified(self, simple_project):
        """Modifying a file and forcing reindex updates the DependencyMap."""
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)
        watcher = WorkspaceWatcher(
            workspace_path=str(simple_project),
            dep_map=dep_map,
        )

        assert dep_map.has_symbol("calculate_total")

        utils = simple_project / "utils.py"
        utils.write_text(
            "def compute_grand_total(items):\n    return sum(items)\n"
        )

        job = watcher.force_reindex(str(utils))
        assert job.event_type == "modified"
        assert job.duration_ms >= 0

        assert dep_map.has_symbol("compute_grand_total")
        assert not dep_map.has_symbol("calculate_total")

    def test_force_reindex_deleted(self, simple_project):
        """Deleting a file and forcing reindex removes its symbols."""
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)
        watcher = WorkspaceWatcher(
            workspace_path=str(simple_project),
            dep_map=dep_map,
        )

        assert dep_map.has_symbol("show_dashboard")

        dashboard = simple_project / "dashboard.py"
        dashboard.unlink()

        job = watcher.force_reindex(str(dashboard))
        assert job.event_type == "deleted"
        assert not dep_map.has_symbol("show_dashboard")

    def test_force_reindex_new_file(self, simple_project):
        """Adding a new file and forcing reindex adds its symbols."""
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)
        watcher = WorkspaceWatcher(
            workspace_path=str(simple_project),
            dep_map=dep_map,
        )

        new_file = simple_project / "analytics.py"
        new_file.write_text(
            "def track_event(name):\n    pass\n"
        )

        job = watcher.force_reindex(str(new_file))
        assert dep_map.has_symbol("track_event")
        assert len(watcher.recent_jobs) == 1

    def test_on_reindex_callback(self, simple_project):
        """Callback is invoked after force reindex."""
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(simple_project), use_cache=False)

        callback_results = []

        def on_cb(job):
            callback_results.append(job)

        watcher = WorkspaceWatcher(
            workspace_path=str(simple_project),
            dep_map=dep_map,
            on_reindex=on_cb,
        )

        utils = simple_project / "utils.py"
        utils.write_text("def new_func():\n    pass\n")
        watcher.force_reindex(str(utils))

        assert len(callback_results) == 1
        assert callback_results[0].file_path == str(utils.resolve())

    def test_watcher_live_detection(self, tmp_path):
        """The watcher detects a file modification within ~2s."""
        target = tmp_path / "watched"
        target.mkdir()
        (target / "app.py").write_text("def original():\n    pass\n")

        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(target), use_cache=False)
        assert dep_map.has_symbol("original")

        detected_files: list = []

        def on_cb(job):
            detected_files.append(job.file_path)

        watcher = WorkspaceWatcher(
            workspace_path=str(target),
            dep_map=dep_map,
            debounce_ms=100,
            on_reindex=on_cb,
        )
        watcher.start()

        try:
            time.sleep(0.3)
            app_file = target / "app.py"
            app_file.write_text("def live_update():\n    return True\n")

            deadline = time.time() + 3.0
            while time.time() < deadline:
                resolved = str(app_file.resolve())
                if resolved in detected_files and dep_map.has_symbol("live_update"):
                    break
                time.sleep(0.1)

            assert dep_map.has_symbol("live_update"), (
                f"Watcher did not update symbol. Detected files: {detected_files}"
            )
        finally:
            watcher.stop()

    def test_watcher_ignores_non_code_files(self, tmp_path):
        """Non-code file extensions are filtered at the handler level."""
        (tmp_path / "only.py").write_text("x = 1\n")

        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(str(tmp_path), use_cache=False)

        watcher = WorkspaceWatcher(
            workspace_path=str(tmp_path),
            dep_map=dep_map,
        )
        # Directly test the filter logic — .txt should not enqueue
        watcher._on_file_event(str(tmp_path / "notes.txt"), "created")
        assert len(watcher._pending) == 0

        # .py should enqueue
        watcher._on_file_event(str(tmp_path / "only.py"), "modified")
        assert len(watcher._pending) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Performance comparison tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPerformance:
    def test_large_project_parallel(self, large_project):
        """Parallel indexer handles 200+ files correctly."""
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace_parallel(
            str(large_project), use_cache=False,
        )
        assert dep_map.stats["indexed_files"] >= 200
        assert dep_map.has_symbol("func_0")
        assert dep_map.has_symbol("func_199")
        assert dep_map.has_symbol("Class_50")

    def test_parallel_vs_linear_correctness(self, large_project):
        """Parallel and linear produce identical symbol sets."""
        indexer = SymbolIndexer()
        linear = indexer.index_workspace(str(large_project), use_cache=False)
        parallel = indexer.index_workspace_parallel(
            str(large_project), use_cache=False,
        )

        assert linear.stats["indexed_files"] == parallel.stats["indexed_files"]
        assert linear.stats["unique_symbol_names"] == parallel.stats["unique_symbol_names"]
        assert linear.stats["total_imports"] == parallel.stats["total_imports"]

    def test_cache_second_scan_fast(self, large_project):
        """Second parallel scan with cache should be significantly faster."""
        indexer = SymbolIndexer()
        dm1 = indexer.index_workspace_parallel(
            str(large_project), use_cache=True,
        )
        t1 = dm1.stats["index_time_ms"]

        dm2 = indexer.index_workspace_parallel(
            str(large_project), use_cache=True,
        )
        t2 = dm2.stats["index_time_ms"]

        assert dm2.stats["cache_hits"] > 0
        assert t2 < t1 or t2 < 50  # cached scan should be fast


# ═══════════════════════════════════════════════════════════════════════════
# API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════

class TestWatcherAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        self.client = TestClient(app)
        yield
        self.client.post("/api/v1/watcher/stop")

    def test_status_not_running(self):
        resp = self.client.get("/api/v1/watcher/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is False

    def test_reindex_without_watcher(self):
        resp = self.client.post(
            "/api/v1/watcher/reindex",
            json={"filePath": "/tmp/test.py"},
        )
        assert resp.status_code == 409

    def test_start_and_status(self, simple_project):
        resp = self.client.post(
            "/api/v1/watcher/start",
            json={"workspacePath": str(simple_project)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["indexedFiles"] == 5

        resp = self.client.get("/api/v1/watcher/status")
        assert resp.json()["running"] is True

    def test_stop(self, simple_project):
        self.client.post(
            "/api/v1/watcher/start",
            json={"workspacePath": str(simple_project)},
        )
        resp = self.client.post("/api/v1/watcher/stop")
        assert resp.json()["status"] == "stopped"
