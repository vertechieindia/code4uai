"""Day 25 — War Room Dashboard test suite.

Tests:
  - Data models: SessionInfo, FileEvent, SwarmTaskView, SwarmView, GraphStats, ROIData, DashboardState.
  - Widget renderers: sessions, file events, swarm DAG, graph stats, hot files, noisy recipes, command bar, ROI ticker, full layout.
  - WarRoomDashboard: state management, command handling, plan lifecycle, swarm events, file events, stats refresh.
  - Data loaders: graph stats, ROI data, swarm view.
  - API integration: swarm plan + dashboard rendering.
"""

from __future__ import annotations

import time
from typing import Dict

import pytest

from code4u.interfaces.cli.dashboard import (
    DashboardState,
    FileEvent,
    GraphStats,
    ROIData,
    SessionInfo,
    SwarmTaskView,
    SwarmView,
    WarRoomDashboard,
    build_layout,
    load_swarm_view_from_graph,
    render_command_bar,
    render_file_events_panel,
    render_graph_stats_panel,
    render_hot_files_panel,
    render_noisy_recipes_panel,
    render_roi_ticker,
    render_sessions_panel,
    render_swarm_panel,
)


# ═══════════════════════════════════════════════════════════════════════════
# Data model tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDataModels:
    def test_session_info_to_dict(self):
        s = SessionInfo(
            session_id="abc",
            display_name="Dev1",
            active_intent="rename",
        )
        d = s.to_dict()
        assert d["sessionId"] == "abc"
        assert d["displayName"] == "Dev1"

    def test_file_event_age(self):
        ev = FileEvent(file_path="test.py", timestamp=time.time() - 30)
        age = ev.age_str()
        assert "s ago" in age

    def test_file_event_age_minutes(self):
        ev = FileEvent(file_path="test.py", timestamp=time.time() - 120)
        age = ev.age_str()
        assert "m ago" in age

    def test_dashboard_state_add_file_event(self):
        state = DashboardState()
        for i in range(25):
            state.add_file_event(FileEvent(file_path=f"file_{i}.py"))
        assert len(state.file_events) == 20  # capped at 20

    def test_dashboard_state_defaults(self):
        state = DashboardState()
        assert state.workspace == ""
        assert state.status_message == "Ready"
        assert state.pending_plan is None

    def test_roi_data_defaults(self):
        roi = ROIData()
        assert roi.hours_saved == 0.0
        assert roi.total_suggestions == 0

    def test_graph_stats_defaults(self):
        gs = GraphStats()
        assert gs.total_files == 0
        assert gs.cycles == 0
        assert gs.hot_files == []


# ═══════════════════════════════════════════════════════════════════════════
# Widget renderer tests
# ═══════════════════════════════════════════════════════════════════════════

class TestWidgetRenderers:
    @pytest.fixture
    def state(self):
        return DashboardState(workspace="/tmp/project")

    def test_render_sessions_empty(self, state):
        panel = render_sessions_panel(state)
        assert panel.title is not None

    def test_render_sessions_with_data(self, state):
        state.sessions = [
            SessionInfo("s1", "Alice", active_intent="rename foo"),
            SessionInfo("s2", "Bob", active_intent="extract"),
        ]
        panel = render_sessions_panel(state)
        assert panel.title is not None

    def test_render_file_events_empty(self, state):
        panel = render_file_events_panel(state)
        assert panel.title is not None

    def test_render_file_events_with_data(self, state):
        state.file_events = [
            FileEvent("src/app.py", "modified"),
            FileEvent("src/utils.py", "created"),
            FileEvent("old.py", "deleted"),
        ]
        panel = render_file_events_panel(state)
        assert panel.title is not None

    def test_render_swarm_empty(self, state):
        panel = render_swarm_panel(state)
        assert panel.title is not None

    def test_render_swarm_with_tasks(self, state):
        state.swarm = SwarmView(
            graph_id="g1",
            goal="Build dashboard",
            progress=0.5,
            tasks=[
                SwarmTaskView("t1", "index", "Index workspace", "completed", 100.0),
                SwarmTaskView("t2", "vision", "Analyze UI", "in_progress", 0, "", ["t1"]),
                SwarmTaskView("t3", "migration", "Create file", "pending", 0, "", ["t2"]),
            ],
        )
        panel = render_swarm_panel(state)
        assert panel.title is not None

    def test_render_swarm_with_failure(self, state):
        state.swarm = SwarmView(
            goal="Broken",
            is_complete=True,
            is_success=False,
            progress=0.5,
            tasks=[
                SwarmTaskView("t1", "index", "Index", "failed", error="crash"),
                SwarmTaskView("t2", "refactor", "Refactor", "skipped", error="upstream"),
            ],
        )
        panel = render_swarm_panel(state)
        assert panel.title is not None

    def test_render_graph_stats(self, state):
        state.graph_stats = GraphStats(
            total_files=150,
            total_symbols=2000,
            total_imports=500,
            cycles=3,
        )
        panel = render_graph_stats_panel(state)
        assert panel.title is not None

    def test_render_hot_files(self, state):
        state.graph_stats.hot_files = ["core/utils.py", "models/user.py"]
        panel = render_hot_files_panel(state)
        assert panel.title is not None

    def test_render_noisy_recipes(self, state):
        state.graph_stats.noisy_recipes = [
            {"id": "pathlib", "count": 42},
            {"id": "fstring", "count": 28},
        ]
        panel = render_noisy_recipes_panel(state)
        assert panel.title is not None

    def test_render_command_bar_ready(self, state):
        panel = render_command_bar(state)
        assert panel.title is not None

    def test_render_command_bar_pending(self, state):
        state.pending_plan = {"goal": "Test plan", "taskCount": 3}
        panel = render_command_bar(state)
        assert panel.title is not None

    def test_render_roi_ticker_empty(self, state):
        panel = render_roi_ticker(state)
        assert panel is not None

    def test_render_roi_ticker_with_data(self, state):
        state.roi = ROIData(
            total_suggestions=100,
            accepted_count=80,
            minutes_saved=870,
            hours_saved=14.5,
            repos_count=4,
            reviews_count=25,
        )
        panel = render_roi_ticker(state)
        assert panel is not None

    def test_build_full_layout(self, state):
        layout = build_layout(state)
        assert layout is not None


# ═══════════════════════════════════════════════════════════════════════════
# WarRoomDashboard tests
# ═══════════════════════════════════════════════════════════════════════════

class TestWarRoomDashboard:
    @pytest.fixture
    def dashboard(self):
        return WarRoomDashboard(workspace="/tmp/test")

    def test_initial_state(self, dashboard):
        assert dashboard.state.workspace == "/tmp/test"
        assert dashboard.state.status_message == "Ready"
        assert not dashboard._running

    def test_add_file_event(self, dashboard):
        dashboard.add_file_event("src/app.py", "modified")
        assert len(dashboard.state.file_events) == 1
        assert dashboard.state.file_events[0].file_path == "src/app.py"

    def test_add_session(self, dashboard):
        s = SessionInfo("s1", "Alice")
        dashboard.add_session(s)
        assert len(dashboard.state.sessions) == 1

    def test_update_session(self, dashboard):
        s1 = SessionInfo("s1", "Alice")
        dashboard.add_session(s1)
        s2 = SessionInfo("s1", "Alice (updated)")
        dashboard.add_session(s2)
        assert len(dashboard.state.sessions) == 1
        assert dashboard.state.sessions[0].display_name == "Alice (updated)"

    def test_remove_session(self, dashboard):
        dashboard.add_session(SessionInfo("s1", "Alice"))
        dashboard.add_session(SessionInfo("s2", "Bob"))
        dashboard.remove_session("s1")
        assert len(dashboard.state.sessions) == 1
        assert dashboard.state.sessions[0].session_id == "s2"

    def test_set_pending_plan(self, dashboard):
        plan = {"goal": "Test", "taskCount": 3}
        dashboard.set_pending_plan(plan)
        assert dashboard.state.pending_plan is not None
        assert dashboard.state.pending_plan["taskCount"] == 3

    def test_cancel_plan(self, dashboard):
        dashboard.set_pending_plan({"goal": "Test"})
        dashboard.cancel_plan()
        assert dashboard.state.pending_plan is None
        assert "cancelled" in dashboard.state.status_message.lower()

    def test_handle_command(self, dashboard):
        result = dashboard.handle_command("Refactor the auth module")
        assert result["taskCount"] >= 1
        assert dashboard.state.pending_plan is not None
        assert dashboard.state.swarm.tasks

    def test_execute_plan(self, dashboard):
        dashboard.handle_command("Do a simple refactor")
        result = dashboard.execute_plan()
        assert result["isComplete"]
        assert dashboard.state.pending_plan is None

    def test_execute_no_plan(self, dashboard):
        result = dashboard.execute_plan()
        assert result == {}

    def test_render(self, dashboard):
        layout = dashboard.render()
        assert layout is not None

    def test_stop(self, dashboard):
        dashboard._running = True
        dashboard.stop()
        assert not dashboard._running

    def test_command_history(self, dashboard):
        dashboard.handle_command("First")
        dashboard.handle_command("Second")
        assert len(dashboard.state.command_history) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Swarm event processing tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSwarmEventProcessing:
    @pytest.fixture
    def dashboard(self):
        d = WarRoomDashboard()
        d.state.swarm = SwarmView(
            graph_id="g1",
            goal="Test",
            tasks=[
                SwarmTaskView("t1", "index", "Index", "pending"),
                SwarmTaskView("t2", "refactor", "Refactor", "pending", dependencies=["t1"]),
            ],
        )
        return d

    def test_update_swarm_event_task_started(self, dashboard):
        dashboard.update_swarm_event({
            "event": "TASK_STARTED",
            "progress": 0.0,
            "task": {"id": "t1", "status": "in_progress", "durationMs": 0},
        })
        assert dashboard.state.swarm.tasks[0].status == "in_progress"

    def test_update_swarm_event_task_completed(self, dashboard):
        dashboard.update_swarm_event({
            "event": "TASK_COMPLETED",
            "progress": 0.5,
            "task": {"id": "t1", "status": "completed", "durationMs": 150.0},
        })
        assert dashboard.state.swarm.tasks[0].status == "completed"
        assert dashboard.state.swarm.tasks[0].duration_ms == 150.0

    def test_update_swarm_event_task_failed(self, dashboard):
        dashboard.update_swarm_event({
            "event": "TASK_FAILED",
            "progress": 0.5,
            "task": {"id": "t1", "status": "failed", "durationMs": 50, "error": "boom"},
        })
        assert dashboard.state.swarm.tasks[0].status == "failed"
        assert dashboard.state.swarm.tasks[0].error == "boom"

    def test_update_swarm_completed(self, dashboard):
        dashboard.update_swarm_event({
            "event": "SWARM_COMPLETED",
            "progress": 1.0,
        })
        assert dashboard.state.swarm.is_complete

    def test_progress_tracking(self, dashboard):
        dashboard.update_swarm_event({"event": "TASK_COMPLETED", "progress": 0.5})
        assert dashboard.state.swarm.progress == 0.5

    def test_events_accumulated(self, dashboard):
        dashboard.update_swarm_event({"event": "TASK_STARTED", "progress": 0.0})
        dashboard.update_swarm_event({"event": "TASK_COMPLETED", "progress": 0.5})
        assert len(dashboard.state.swarm.events) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Data loader tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDataLoaders:
    def test_load_swarm_view_from_graph(self):
        graph_dict = {
            "id": "g1",
            "goal": "Build page",
            "progress": 0.75,
            "isComplete": False,
            "isSuccess": False,
            "tasks": [
                {
                    "id": "t1",
                    "agentType": "vision",
                    "description": "Analyze",
                    "status": "completed",
                    "durationMs": 200,
                    "error": "",
                    "dependencies": [],
                },
                {
                    "id": "t2",
                    "agentType": "migration",
                    "description": "Build",
                    "status": "in_progress",
                    "durationMs": 0,
                    "error": "",
                    "dependencies": ["t1"],
                },
            ],
        }
        sv = load_swarm_view_from_graph(graph_dict)
        assert sv.graph_id == "g1"
        assert sv.goal == "Build page"
        assert len(sv.tasks) == 2
        assert sv.tasks[0].status == "completed"
        assert sv.tasks[1].dependencies == ["t1"]

    def test_load_swarm_view_empty(self):
        sv = load_swarm_view_from_graph({})
        assert sv.graph_id == ""
        assert sv.tasks == []

    def test_load_graph_stats_nonexistent(self):
        from code4u.interfaces.cli.dashboard import load_graph_stats
        stats = load_graph_stats("/nonexistent/workspace")
        assert stats.total_files == 0

    def test_load_roi_data(self):
        from code4u.interfaces.cli.dashboard import load_roi_data
        roi = load_roi_data()
        assert isinstance(roi, ROIData)


# ═══════════════════════════════════════════════════════════════════════════
# Integration: swarm plan → dashboard rendering
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_plan_and_render(self):
        dashboard = WarRoomDashboard(workspace="/tmp/test")
        dashboard.handle_command("Match this design screenshot and create component")
        layout = dashboard.render()
        assert layout is not None
        assert dashboard.state.swarm.tasks

    def test_full_lifecycle(self):
        dashboard = WarRoomDashboard()
        dashboard.add_session(SessionInfo("s1", "Dev"))
        dashboard.add_file_event("app.py", "modified")

        # Plan
        dashboard.handle_command("Simple refactor")
        assert dashboard.state.pending_plan is not None

        # Render with plan pending
        layout1 = dashboard.render()
        assert layout1 is not None

        # Execute
        result = dashboard.execute_plan()
        assert result["isComplete"]

        # Render after execution
        layout2 = dashboard.render()
        assert layout2 is not None

    def test_cancel_lifecycle(self):
        dashboard = WarRoomDashboard()
        dashboard.handle_command("Something dangerous")
        assert dashboard.state.pending_plan is not None
        dashboard.cancel_plan()
        assert dashboard.state.pending_plan is None
        assert dashboard.state.swarm.tasks == []

    def test_run_limited_iterations(self):
        """Dashboard.run() with max_iterations should exit cleanly."""
        dashboard = WarRoomDashboard(refresh_rate=0.05)
        dashboard.run(max_iterations=2)
        assert not dashboard._running
