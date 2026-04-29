"""Day 29 — Performance Profiler test suite.

Tests:
  - PerformanceIngestor: cProfile, cpuprofile, generic JSON parsing.
  - FunctionProfile / ProfileSummary: data models, ranking, hot_files.
  - Optimizer: O(n^2), N+1, blocking, manual sort, regex smell detection.
  - OptimizationPlan: smell-to-fix conversion.
  - ChiefArchitect: PROFILER agent detection, PERFORMANCE_TUNING pipeline.
  - TUI: latency badges in hot files panel.
  - API: ingest, analyze, scan endpoints.
"""

from __future__ import annotations

import textwrap

import pytest

from code4u.agents.performance.parser import (
    FunctionProfile,
    PerformanceIngestor,
    ProfileSummary,
)
from code4u.agents.performance.optimizer import (
    Optimization,
    OptimizationPlan,
    Optimizer,
    PerformanceSmell,
)


# ═══════════════════════════════════════════════════════════════════════════
# FunctionProfile tests
# ═══════════════════════════════════════════════════════════════════════════

class TestFunctionProfile:
    def test_defaults(self):
        fp = FunctionProfile(name="test")
        assert fp.cumulative_time_ms == 0
        assert fp.avg_time_ms == 0
        assert not fp.is_hot

    def test_avg_time(self):
        fp = FunctionProfile(name="f", cumulative_time_ms=500, call_count=100)
        assert fp.avg_time_ms == 5.0

    def test_is_hot_by_time(self):
        fp = FunctionProfile(name="f", cumulative_time_ms=200)
        assert fp.is_hot

    def test_is_hot_by_calls(self):
        fp = FunctionProfile(name="f", call_count=2000)
        assert fp.is_hot

    def test_to_dict(self):
        fp = FunctionProfile(name="f", file_path="a.py", cumulative_time_ms=100, call_count=50)
        d = fp.to_dict()
        assert d["name"] == "f"
        assert d["cumulativeTimeMs"] == 100
        assert d["avgTimeMs"] == 2.0
        assert d["isHot"] is False  # 100 < threshold but not > 100 strictly


# ═══════════════════════════════════════════════════════════════════════════
# ProfileSummary tests
# ═══════════════════════════════════════════════════════════════════════════

class TestProfileSummary:
    def test_hot_functions_ranking(self):
        s = ProfileSummary(functions=[
            FunctionProfile("slow", cumulative_time_ms=800),
            FunctionProfile("fast", cumulative_time_ms=10),
            FunctionProfile("medium", cumulative_time_ms=200),
        ])
        top = s.hot_functions(top=2)
        assert len(top) == 2
        assert top[0].name == "slow"
        assert top[1].name == "medium"

    def test_hot_files(self):
        s = ProfileSummary(functions=[
            FunctionProfile("f1", file_path="a.py", cumulative_time_ms=300),
            FunctionProfile("f2", file_path="a.py", cumulative_time_ms=200),
            FunctionProfile("f3", file_path="b.py", cumulative_time_ms=100),
        ])
        hf = s.hot_files()
        assert hf[0]["file"] == "a.py"
        assert hf[0]["totalTimeMs"] == 500

    def test_to_dict(self):
        s = ProfileSummary(functions=[FunctionProfile("f")], total_time_ms=1000)
        d = s.to_dict()
        assert d["totalTimeMs"] == 1000
        assert d["functionCount"] == 1

    def test_empty(self):
        s = ProfileSummary()
        assert s.function_count == 0
        assert s.hot_functions() == []


# ═══════════════════════════════════════════════════════════════════════════
# PerformanceIngestor tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPerformanceIngestor:
    def test_generic_json(self):
        data = {
            "functions": [
                {"name": "slow_func", "file": "app.py", "line": 42,
                 "cumulative_time_ms": 800, "self_time_ms": 600, "call_count": 50},
                {"name": "fast_func", "file": "utils.py", "line": 10,
                 "cumulative_time_ms": 20, "call_count": 1000},
            ],
            "total_time_ms": 1000,
        }
        ingestor = PerformanceIngestor()
        summary = ingestor.from_json(data)
        assert summary.profile_type == "generic"
        assert summary.function_count == 2
        hot = summary.hot_functions(top=1)
        assert hot[0].name == "slow_func"
        assert hot[0].cumulative_time_ms == 800

    def test_cprofile_json(self):
        data = {
            "stats": {
                "app.py:42(process_data)": {
                    "cumulative_time": 1.5,
                    "total_time": 0.8,
                    "call_count": 200,
                    "callers": ["main.py:10(run)"],
                },
                "utils.py:10(helper)": {
                    "cumulative_time": 0.3,
                    "total_time": 0.3,
                    "call_count": 500,
                },
            },
            "total_time": 2.0,
        }
        ingestor = PerformanceIngestor()
        summary = ingestor.from_cprofile(data)
        assert summary.profile_type == "cprofile"
        assert summary.total_time_ms == 2000.0
        hot = summary.hot_functions(top=1)
        assert hot[0].name == "process_data"
        assert hot[0].file_path == "app.py"
        assert hot[0].line_number == 42
        assert hot[0].cumulative_time_ms == 1500.0

    def test_cpuprofile_json(self):
        data = {
            "nodes": [
                {"id": 1, "callFrame": {"functionName": "render", "url": "app.js", "lineNumber": 5}, "hitCount": 100},
                {"id": 2, "callFrame": {"functionName": "compute", "url": "math.js", "lineNumber": 20}, "hitCount": 50},
                {"id": 3, "callFrame": {"functionName": "(idle)", "url": "", "lineNumber": 0}, "hitCount": 10},
            ],
            "samples": [1, 1, 1, 2, 2, 3],
            "startTime": 0,
            "endTime": 6000000,
        }
        ingestor = PerformanceIngestor()
        summary = ingestor.from_cpuprofile(data)
        assert summary.profile_type == "cpuprofile"
        assert summary.function_count == 2  # idle excluded
        hot = summary.hot_functions(top=1)
        assert hot[0].name == "render"

    def test_auto_detect_generic(self):
        data = {"functions": [{"name": "f", "cumulative_time_ms": 100}]}
        ingestor = PerformanceIngestor()
        summary = ingestor.from_json(data)
        assert summary.profile_type == "generic"

    def test_auto_detect_cprofile(self):
        data = {"stats": {"a.py:1(f)": {"cumulative_time": 0.1, "call_count": 1}}}
        ingestor = PerformanceIngestor()
        summary = ingestor.from_json(data)
        assert summary.profile_type == "cprofile"

    def test_auto_detect_cpuprofile(self):
        data = {"nodes": [], "samples": [], "startTime": 0, "endTime": 1000}
        ingestor = PerformanceIngestor()
        summary = ingestor.from_json(data)
        assert summary.profile_type == "cpuprofile"

    def test_bottleneck_identification(self):
        """80% of execution time in one function."""
        data = {
            "functions": [
                {"name": "bottleneck", "cumulative_time_ms": 8000, "call_count": 1},
                {"name": "fast_a", "cumulative_time_ms": 500, "call_count": 100},
                {"name": "fast_b", "cumulative_time_ms": 500, "call_count": 200},
                {"name": "fast_c", "cumulative_time_ms": 1000, "call_count": 50},
            ],
            "total_time_ms": 10000,
        }
        ingestor = PerformanceIngestor()
        summary = ingestor.from_json(data)
        top = summary.hot_functions(top=1)
        assert top[0].name == "bottleneck"
        assert top[0].cumulative_time_ms == 8000


# ═══════════════════════════════════════════════════════════════════════════
# Optimizer tests
# ═══════════════════════════════════════════════════════════════════════════

class TestOptimizer:
    def test_nested_loop_detection(self):
        source = textwrap.dedent("""\
            def find_duplicates(items):
                result = []
                for i in items:
                    for j in items:
                        if i == j:
                            result.append(i)
                return result
        """)
        optimizer = Optimizer()
        fn = FunctionProfile("find_duplicates", cumulative_time_ms=5000)
        plan = optimizer.analyze_hot_path(fn, source)
        assert plan.has_optimizations
        cats = [o.category for o in plan.optimizations]
        assert "O(n^2)" in cats

    def test_bubble_sort_detection(self):
        source = textwrap.dedent("""\
            def bubble_sort(arr):
                n = len(arr)
                for i in range(n):
                    for j in range(0, n - i - 1):
                        if arr[j] > arr[j + 1]:
                            arr[j], arr[j + 1] = arr[j + 1], arr[j]
                return arr
        """)
        optimizer = Optimizer()
        fn = FunctionProfile("bubble_sort", cumulative_time_ms=3000)
        plan = optimizer.analyze_hot_path(fn, source)
        cats = [o.category for o in plan.optimizations]
        assert "manual_sort" in cats or "O(n^2)" in cats

    def test_time_sleep_detection(self):
        source = "import time\ntime.sleep(5)\n"
        optimizer = Optimizer()
        smells = optimizer.scan_source(source)
        cats = [s.category for s in smells]
        assert "blocking" in cats

    def test_list_search_detection(self):
        source = 'if status in ["active", "pending", "closed"]:\n    pass\n'
        optimizer = Optimizer()
        smells = optimizer.scan_source(source)
        cats = [s.category for s in smells]
        assert "inefficient_search" in cats

    def test_readlines_detection(self):
        source = "f.readlines()\n"
        optimizer = Optimizer()
        smells = optimizer.scan_source(source)
        cats = [s.category for s in smells]
        assert "memory" in cats

    def test_clean_code(self):
        source = textwrap.dedent("""\
            def get_users():
                return sorted(users, key=lambda u: u.name)
        """)
        optimizer = Optimizer()
        smells = optimizer.scan_source(source)
        assert len(smells) == 0

    def test_no_source(self):
        optimizer = Optimizer()
        fn = FunctionProfile("f", cumulative_time_ms=5000)
        plan = optimizer.analyze_hot_path(fn, "")
        assert not plan.has_optimizations

    def test_syntax_error_safe(self):
        optimizer = Optimizer()
        smells = optimizer.scan_source("def broken(:")
        # regex patterns may still match, but AST won't crash
        assert isinstance(smells, list)


# ═══════════════════════════════════════════════════════════════════════════
# OptimizationPlan tests
# ═══════════════════════════════════════════════════════════════════════════

class TestOptimizationPlan:
    def test_empty_plan(self):
        plan = OptimizationPlan(function_name="f")
        assert not plan.has_optimizations
        assert plan.top_category == "none"

    def test_with_optimizations(self):
        plan = OptimizationPlan(
            function_name="f",
            optimizations=[
                Optimization("O(n^2)", "Nested loop", "Use set"),
            ],
        )
        assert plan.has_optimizations
        assert plan.top_category == "O(n^2)"

    def test_to_dict(self):
        plan = OptimizationPlan(
            function_name="f", file_path="a.py", cumulative_time_ms=5000,
            smells=[PerformanceSmell("blocking", "sleep found")],
            optimizations=[Optimization("blocking", "sleep", "remove")],
        )
        d = plan.to_dict()
        assert d["functionName"] == "f"
        assert d["hasOptimizations"]
        assert len(d["smells"]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# PerformanceSmell / Optimization serialization
# ═══════════════════════════════════════════════════════════════════════════

class TestSerialization:
    def test_smell_to_dict(self):
        s = PerformanceSmell("O(n^2)", "Nested loop", "a.py", 42, "warning", "PERF-001")
        d = s.to_dict()
        assert d["category"] == "O(n^2)"
        assert d["lineNumber"] == 42

    def test_optimization_to_dict(self):
        o = Optimization("blocking", "sleep", "remove sleep", "100x", "a.py", 5)
        d = o.to_dict()
        assert d["estimatedSpeedup"] == "100x"


# ═══════════════════════════════════════════════════════════════════════════
# ChiefArchitect integration
# ═══════════════════════════════════════════════════════════════════════════

class TestChiefArchitectProfiler:
    def test_detects_profiler_agent(self):
        from code4u.agents.orchestrator.chief import ChiefArchitect
        chief = ChiefArchitect()
        graph = chief.decompose("Optimize the slow database query")
        agent_types = {t.agent_type.value for t in graph.tasks}
        assert "profiler" in agent_types

    def test_performance_keywords(self):
        from code4u.agents.orchestrator.chief import ChiefArchitect
        chief = ChiefArchitect()
        for kw in ["speed up", "bottleneck", "latency", "cpu", "profile"]:
            graph = chief.decompose(f"Fix the {kw} issue")
            agent_types = {t.agent_type.value for t in graph.tasks}
            assert "profiler" in agent_types, f"Keyword '{kw}' did not trigger profiler"

    def test_performance_tuning_pipeline(self):
        from code4u.agents.orchestrator.chief import ChiefArchitect
        chief = ChiefArchitect()
        graph = chief.decompose(
            "Optimize the slow function and review for quality",
            workspace_path="/tmp/proj",
        )
        types = [t.agent_type.value for t in graph.tasks]
        assert "index" in types
        assert "profiler" in types
        assert "jury" in types

    def test_profiler_agent_type_exists(self):
        from code4u.agents.orchestrator.models import AgentType
        assert hasattr(AgentType, "PROFILER")
        assert AgentType.PROFILER.value == "profiler"


# ═══════════════════════════════════════════════════════════════════════════
# TUI heatmap tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTUIHeatmap:
    def test_hot_files_with_latency(self):
        from code4u.interfaces.cli.dashboard import DashboardState, GraphStats, render_hot_files_panel
        state = DashboardState()
        state.graph_stats = GraphStats(
            hot_files=["app.py", "utils.py"],
            perf_hotspots=[
                {"file": "app.py", "totalTimeMs": 5000},
                {"file": "utils.py", "totalTimeMs": 200},
            ],
        )
        panel = render_hot_files_panel(state)
        assert panel is not None

    def test_hot_files_no_latency(self):
        from code4u.interfaces.cli.dashboard import DashboardState, GraphStats, render_hot_files_panel
        state = DashboardState()
        state.graph_stats = GraphStats(hot_files=["a.py"])
        panel = render_hot_files_panel(state)
        assert panel is not None

    def test_only_perf_hotspots(self):
        from code4u.interfaces.cli.dashboard import DashboardState, GraphStats, render_hot_files_panel
        state = DashboardState()
        state.graph_stats = GraphStats(
            perf_hotspots=[{"file": "slow.py", "totalTimeMs": 3000}]
        )
        panel = render_hot_files_panel(state)
        assert panel is not None

    def test_profiler_icon_in_agents(self):
        from code4u.interfaces.cli.dashboard import _AGENT_ICONS
        assert "profiler" in _AGENT_ICONS


# ═══════════════════════════════════════════════════════════════════════════
# API tests
# ═══════════════════════════════════════════════════════════════════════════

class TestProfilerAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        self.client = TestClient(app)
        yield

    def test_ingest_endpoint(self):
        resp = self.client.post("/api/v1/profiler/ingest", json={
            "profile": {
                "functions": [
                    {"name": "slow", "file": "app.py", "cumulative_time_ms": 8000, "call_count": 1},
                    {"name": "fast", "file": "utils.py", "cumulative_time_ms": 100, "call_count": 500},
                ],
                "total_time_ms": 10000,
            },
            "top": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hotFunctions"][0]["name"] == "slow"
        assert len(data["hotFiles"]) >= 1

    def test_analyze_endpoint(self):
        source = textwrap.dedent("""\
            def find_dupes(items):
                for i in items:
                    for j in items:
                        if i == j:
                            pass
        """)
        resp = self.client.post("/api/v1/profiler/analyze", json={
            "functionName": "find_dupes",
            "filePath": "app.py",
            "cumulativeTimeMs": 5000,
            "callCount": 100,
            "source": source,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hasOptimizations"]
        cats = [o["category"] for o in data["optimizations"]]
        assert "O(n^2)" in cats

    def test_scan_endpoint(self):
        resp = self.client.post("/api/v1/profiler/scan", json={
            "source": "import time\ntime.sleep(10)\n",
            "filePath": "slow.py",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        cats = [s["category"] for s in data["smells"]]
        assert "blocking" in cats

    def test_scan_clean_code(self):
        resp = self.client.post("/api/v1/profiler/scan", json={
            "source": "def hello():\n    return 42\n",
        })
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Integration: full profiler pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_ingest_then_analyze(self):
        """Upload profile, identify bottleneck, analyze it."""
        ingestor = PerformanceIngestor()
        summary = ingestor.from_json({
            "functions": [
                {"name": "bottleneck", "file": "core.py", "line": 42,
                 "cumulative_time_ms": 8000, "call_count": 1},
            ],
            "total_time_ms": 10000,
        })
        top = summary.hot_functions(top=1)
        assert top[0].name == "bottleneck"
        assert top[0].cumulative_time_ms == 8000

        source = textwrap.dedent("""\
            def bottleneck(data):
                result = []
                for item in data:
                    for other in data:
                        if item == other:
                            result.append(item)
                return result
        """)
        optimizer = Optimizer()
        plan = optimizer.analyze_hot_path(top[0], source)
        assert plan.has_optimizations
        assert any(o.category == "O(n^2)" for o in plan.optimizations)
        assert plan.optimizations[0].estimated_speedup != ""

    def test_algorithm_swap_suggestion(self):
        """Bubble sort should be detected as O(n^2) or manual_sort."""
        source = textwrap.dedent("""\
            def my_sort(arr):
                n = len(arr)
                for i in range(n):
                    for j in range(0, n - i - 1):
                        if arr[j] > arr[j + 1]:
                            arr[j], arr[j + 1] = arr[j + 1], arr[j]
                return arr
        """)
        optimizer = Optimizer()
        fn = FunctionProfile("my_sort", cumulative_time_ms=3000)
        plan = optimizer.analyze_hot_path(fn, source)
        assert plan.has_optimizations
        cats = {o.category for o in plan.optimizations}
        assert cats & {"O(n^2)", "manual_sort"}, f"Expected O(n^2) or manual_sort, got {cats}"
