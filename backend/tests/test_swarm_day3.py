"""Day 3 test suite — Swarm Orchestration & Deterministic Refactoring.

Covers:
  - ChiefArchitect goal decomposition
  - SwarmController task execution lifecycle
  - Swarm API endpoints (plan, execute, list, get)
  - Sentinel API (scan, delta-scan, rules)
  - Compliance API (audit-status)
  - Auth headers on all swarm/sentinel calls
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from code4u.interfaces.api.app import app
from code4u.interfaces.api.deps import _auth_manager
from code4u.agents.orchestrator.models import (
    AgentType,
    HandoffPayload,
    SubTask,
    TaskGraph,
    TaskStatus,
)
from code4u.agents.orchestrator.chief import ChiefArchitect
from code4u.agents.orchestrator.controller import SwarmController

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers() -> dict:
    """Register a test user and return valid Bearer headers."""
    mgr = _auth_manager()
    email = "swarm-test@code4u.ai"
    try:
        mgr.register(email, "testpass", name="SwarmBot")
    except ValueError:
        pass
    token = mgr.authenticate(email, "testpass")
    return {"Authorization": f"Bearer {token}"}


# ===================================================================
# 1. ChiefArchitect — goal decomposition
# ===================================================================

class TestChiefArchitect:
    """Test the keyword-based goal decomposition logic."""

    def test_simple_refactor_creates_tasks(self):
        chief = ChiefArchitect()
        graph = chief.decompose("Rename all variables to camelCase", workspace_path="/tmp/ws")
        assert graph.task_count >= 1
        assert graph.goal == "Rename all variables to camelCase"

    def test_vision_keyword_triggers_vision_agent(self):
        chief = ChiefArchitect()
        graph = chief.decompose("Match this design screenshot", workspace_path="/tmp/ws")
        agent_types = {t.agent_type for t in graph.tasks}
        assert AgentType.VISION in agent_types

    def test_graph_keyword_triggers_graph_agent(self):
        chief = ChiefArchitect()
        graph = chief.decompose("Find where the database schema is defined")
        agent_types = {t.agent_type for t in graph.tasks}
        assert AgentType.GRAPH in agent_types

    def test_migration_keyword_triggers_migration_agent(self):
        chief = ChiefArchitect()
        graph = chief.decompose("Create a new file for the auth module")
        agent_types = {t.agent_type for t in graph.tasks}
        assert AgentType.MIGRATION in agent_types

    def test_heal_keyword_triggers_heal_agent(self):
        chief = ChiefArchitect()
        graph = chief.decompose("Fix the failing test in utils.py")
        agent_types = {t.agent_type for t in graph.tasks}
        assert AgentType.HEAL in agent_types

    def test_profiler_keyword_triggers_profiler_agent(self):
        chief = ChiefArchitect()
        graph = chief.decompose("Optimize the slow bottleneck in the API")
        agent_types = {t.agent_type for t in graph.tasks}
        assert AgentType.PROFILER in agent_types

    def test_multi_agent_goal_creates_jury_review(self):
        chief = ChiefArchitect()
        graph = chief.decompose(
            "Build a contact form based on this image and save data to the DB",
            workspace_path="/tmp/ws",
            image_base64="dummy_base64",
        )
        agent_types = {t.agent_type for t in graph.tasks}
        assert AgentType.JURY in agent_types
        assert graph.task_count >= 3

    def test_workspace_triggers_index_task(self):
        chief = ChiefArchitect()
        graph = chief.decompose("Refactor exports", workspace_path="/tmp/ws")
        first_task = graph.tasks[0]
        assert first_task.agent_type == AgentType.INDEX

    def test_task_dependencies_form_dag(self):
        chief = ChiefArchitect()
        graph = chief.decompose(
            "Build a new page from this screenshot",
            workspace_path="/tmp/ws",
            image_base64="img",
        )
        ids = {t.id for t in graph.tasks}
        for task in graph.tasks:
            for dep in task.dependencies:
                assert dep in ids, f"Dangling dependency {dep}"

    def test_architectural_rules_injected_as_jit_context(self):
        chief = ChiefArchitect()
        graph = chief.decompose(
            "Add a new API route",
            workspace_path="/tmp/ws",
            context={"architectural_rules": "No direct DB in routes"},
        )
        for task in graph.tasks:
            assert task.config.get("architectural_rules") == "No direct DB in routes"

    def test_graph_to_dict_serialization(self):
        chief = ChiefArchitect()
        graph = chief.decompose("Rename function")
        d = graph.to_dict()
        assert "id" in d
        assert "tasks" in d
        assert "progress" in d
        assert d["isComplete"] is False


# ===================================================================
# 2. SwarmController — execution lifecycle
# ===================================================================

class TestSwarmController:
    """Test the task execution engine."""

    def test_execute_simple_graph(self):
        graph = TaskGraph(goal="Test execution")
        graph.add_task(SubTask(
            agent_type=AgentType.REFACTOR,
            description="Simple task",
        ))
        controller = SwarmController()
        result = controller.execute_sync(graph)
        assert result.is_complete
        assert result.is_success
        assert result.completed_count == 1

    def test_dependency_ordering(self):
        graph = TaskGraph(goal="Ordered execution")
        t1 = SubTask(id="a", agent_type=AgentType.INDEX, description="First")
        t2 = SubTask(id="b", agent_type=AgentType.REFACTOR, description="Second", dependencies=["a"])
        graph.add_task(t1)
        graph.add_task(t2)
        controller = SwarmController()
        result = controller.execute_sync(graph)
        assert result.is_complete
        assert result.is_success
        assert t1.completed_at <= t2.started_at

    def test_failed_dependency_skips_downstream(self):
        def failing_agent(task, handoffs):
            raise RuntimeError("Boom")

        graph = TaskGraph(goal="Failure cascade")
        t1 = SubTask(id="fail", agent_type=AgentType.REFACTOR, description="Will fail")
        t2 = SubTask(id="downstream", agent_type=AgentType.REFACTOR, description="Should skip", dependencies=["fail"])
        graph.add_task(t1)
        graph.add_task(t2)

        controller = SwarmController()
        controller.register_agent(AgentType.REFACTOR, failing_agent)
        result = controller.execute_sync(graph)

        assert result.is_complete
        assert not result.is_success
        assert t1.status == TaskStatus.FAILED
        assert t2.status == TaskStatus.SKIPPED

    def test_event_callback_fires(self):
        events = []

        def capture(payload):
            events.append(payload)

        graph = TaskGraph(goal="Event test")
        graph.add_task(SubTask(agent_type=AgentType.REFACTOR, description="Emitter"))

        controller = SwarmController()
        controller.set_event_callback(capture)
        controller.execute_sync(graph)

        event_types = [e["event"] for e in events]
        assert "SWARM_STARTED" in event_types
        assert "TASK_STARTED" in event_types
        assert "TASK_COMPLETED" in event_types
        assert "SWARM_COMPLETED" in event_types

    def test_handoff_payload_passed_to_downstream(self):
        received_handoffs = []

        def capture_agent(task, handoffs):
            received_handoffs.extend(handoffs)
            return HandoffPayload(
                source_task_id=task.id,
                agent_type=task.agent_type,
                data={"captured": True},
            )

        graph = TaskGraph(goal="Handoff test")
        t1 = SubTask(id="producer", agent_type=AgentType.INDEX, description="Producer")
        t2 = SubTask(id="consumer", agent_type=AgentType.REFACTOR, description="Consumer", dependencies=["producer"])
        graph.add_task(t1)
        graph.add_task(t2)

        controller = SwarmController()
        controller.register_agent(AgentType.INDEX, capture_agent)
        controller.register_agent(AgentType.REFACTOR, capture_agent)
        controller.execute_sync(graph)

        assert len(received_handoffs) >= 1
        assert received_handoffs[0].source_task_id == "producer"


# ===================================================================
# 3. Swarm API endpoints
# ===================================================================

class TestSwarmAPI:
    """Test the /swarm/* REST endpoints."""

    def test_swarm_plan_returns_graph(self, auth_headers):
        res = client.post("/api/v1/swarm/plan", json={
            "goal": "Rename all exports",
            "workspacePath": "/tmp",
        }, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "graph" in data
        assert data["graph"]["goal"] == "Rename all exports"

    def test_swarm_execute_returns_completed_graph(self, auth_headers):
        res = client.post("/api/v1/swarm/execute", json={
            "goal": "Simple refactor test",
            "workspacePath": "",
        }, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["graph"]["isComplete"] is True

    def test_swarm_get_graph_by_id(self, auth_headers):
        plan_res = client.post("/api/v1/swarm/plan", json={
            "goal": "Fetch test",
        }, headers=auth_headers)
        graph_id = plan_res.json()["graph"]["id"]

        get_res = client.get(f"/api/v1/swarm/{graph_id}", headers=auth_headers)
        assert get_res.status_code == 200
        assert get_res.json()["graph"]["id"] == graph_id

    def test_swarm_get_unknown_graph_returns_404(self, auth_headers):
        res = client.get("/api/v1/swarm/nonexistent", headers=auth_headers)
        assert res.status_code == 404

    def test_swarm_list_returns_recent_runs(self, auth_headers):
        client.post("/api/v1/swarm/execute", json={
            "goal": "List test run",
        }, headers=auth_headers)

        res = client.get("/api/v1/swarm?limit=5", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "graphs" in data
        assert len(data["graphs"]) >= 1

    def test_swarm_401_without_token(self):
        res = client.post("/api/v1/swarm/execute", json={
            "goal": "Unauthorized attempt",
        })
        assert res.status_code == 401


# ===================================================================
# 4. Sentinel API endpoints
# ===================================================================

class TestSentinelAPI:
    """Test the /sentinel/* REST endpoints."""

    def test_sentinel_scan_on_valid_workspace(self, auth_headers, tmp_path):
        ws = tmp_path / "project"
        ws.mkdir()
        (ws / "app.py").write_text("import os\nprint('hello')\n")

        res = client.post("/api/v1/sentinel/scan", json={
            "workspacePath": str(ws),
        }, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "files_scanned" in data or "filesScan" in data or "clean" in data

    def test_sentinel_rules_list(self, auth_headers):
        res = client.get("/api/v1/sentinel/rules", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "rules" in data

    def test_sentinel_add_custom_rule(self, auth_headers):
        rule = {
            "id": "test-no-eval",
            "name": "No eval() usage",
            "severity": "critical",
            "description": "eval() is forbidden",
            "forbidden_imports": [{"pattern": "eval", "message": "Do not use eval()"}],
        }
        res = client.post("/api/v1/sentinel/rules", json={
            "rule": rule,
        }, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["registered"] == "test-no-eval"


# ===================================================================
# 5. Compliance API
# ===================================================================

class TestComplianceAPI:
    """Test the compliance audit status endpoint."""

    def test_audit_status_returns_data(self, auth_headers):
        res = client.get("/api/v1/compliance/audit-status", headers=auth_headers)
        assert res.status_code == 200

    def test_compliance_controls_list(self, auth_headers):
        res = client.get("/api/v1/compliance/controls", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "controls" in data


# ===================================================================
# 6. TaskGraph model unit tests
# ===================================================================

class TestTaskGraphModel:
    """Unit tests for the TaskGraph data model."""

    def test_progress_calculation(self):
        g = TaskGraph(goal="test")
        g.add_task(SubTask(status=TaskStatus.COMPLETED))
        g.add_task(SubTask(status=TaskStatus.PENDING))
        assert g.progress == 0.5

    def test_empty_graph_progress_is_1(self):
        g = TaskGraph(goal="empty")
        assert g.progress == 1.0

    def test_get_ready_tasks_respects_dependencies(self):
        g = TaskGraph(goal="deps")
        t1 = SubTask(id="a", status=TaskStatus.PENDING)
        t2 = SubTask(id="b", status=TaskStatus.PENDING, dependencies=["a"])
        g.add_task(t1)
        g.add_task(t2)
        ready = g.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "a"

    def test_get_ready_after_dependency_completes(self):
        g = TaskGraph(goal="deps done")
        t1 = SubTask(id="a", status=TaskStatus.COMPLETED)
        t2 = SubTask(id="b", status=TaskStatus.PENDING, dependencies=["a"])
        g.add_task(t1)
        g.add_task(t2)
        ready = g.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "b"

    def test_summary_output(self):
        g = TaskGraph(goal="Summary test")
        g.add_task(SubTask(agent_type=AgentType.REFACTOR, description="Do something"))
        s = g.summary()
        assert "Summary test" in s
        assert "refactor" in s
