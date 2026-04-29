"""Day 24 — Autonomous Swarm Orchestrator test suite.

Tests:
  - Models: SubTask, TaskGraph, HandoffPayload, AgentType, TaskStatus.
  - ChiefArchitect: goal decomposition, keyword detection, JSON parsing.
  - SwarmController: execution, handoffs, parallelism, failure cascading.
  - Events: SWARM_STARTED, TASK_STARTED/COMPLETED/FAILED, SWARM_COMPLETED.
  - API endpoints: plan, execute, get, list.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List

import pytest

from code4u.agents.orchestrator.models import (
    AgentType,
    HandoffPayload,
    SubTask,
    TaskGraph,
    TaskStatus,
)
from code4u.agents.orchestrator.chief import ChiefArchitect
from code4u.agents.orchestrator.controller import SwarmController


# ═══════════════════════════════════════════════════════════════════════════
# Model tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSubTask:
    def test_default_values(self):
        t = SubTask()
        assert t.agent_type == AgentType.REFACTOR
        assert t.status == TaskStatus.PENDING
        assert t.is_ready
        assert not t.is_terminal
        assert t.duration_ms == 0.0

    def test_completed_is_terminal(self):
        t = SubTask(status=TaskStatus.COMPLETED)
        assert t.is_terminal
        assert not t.is_ready

    def test_failed_is_terminal(self):
        t = SubTask(status=TaskStatus.FAILED)
        assert t.is_terminal

    def test_skipped_is_terminal(self):
        t = SubTask(status=TaskStatus.SKIPPED)
        assert t.is_terminal

    def test_duration_ms(self):
        t = SubTask(started_at=100.0, completed_at=100.5)
        assert t.duration_ms == 500.0

    def test_to_dict(self):
        t = SubTask(
            agent_type=AgentType.VISION,
            description="Analyze UI",
            priority=2,
        )
        d = t.to_dict()
        assert d["agentType"] == "vision"
        assert d["description"] == "Analyze UI"
        assert d["status"] == "pending"
        assert d["priority"] == 2

    def test_to_dict_with_result(self):
        payload = HandoffPayload(
            source_task_id="t1",
            agent_type=AgentType.VISION,
            data={"key": "value"},
        )
        t = SubTask(result=payload)
        d = t.to_dict()
        assert d["result"]["agentType"] == "vision"
        assert d["result"]["data"]["key"] == "value"


class TestHandoffPayload:
    def test_to_dict(self):
        p = HandoffPayload(
            source_task_id="abc",
            agent_type=AgentType.GRAPH,
            data={"files": ["a.py"]},
        )
        d = p.to_dict()
        assert d["sourceTaskId"] == "abc"
        assert d["agentType"] == "graph"
        assert d["data"]["files"] == ["a.py"]


class TestTaskGraph:
    def test_empty_graph(self):
        g = TaskGraph(goal="test")
        assert g.task_count == 0
        assert g.is_complete
        assert g.is_success
        assert g.progress == 1.0

    def test_add_task(self):
        g = TaskGraph(goal="test")
        g.add_task(SubTask(agent_type=AgentType.VISION))
        assert g.task_count == 1
        assert not g.is_complete
        assert g.progress == 0.0

    def test_progress(self):
        g = TaskGraph(goal="test")
        g.add_task(SubTask(id="a", status=TaskStatus.COMPLETED))
        g.add_task(SubTask(id="b", status=TaskStatus.PENDING))
        assert g.progress == 0.5

    def test_is_complete(self):
        g = TaskGraph(goal="test")
        g.add_task(SubTask(id="a", status=TaskStatus.COMPLETED))
        g.add_task(SubTask(id="b", status=TaskStatus.COMPLETED))
        assert g.is_complete
        assert g.is_success

    def test_failed_not_success(self):
        g = TaskGraph(goal="test")
        g.add_task(SubTask(id="a", status=TaskStatus.COMPLETED))
        g.add_task(SubTask(id="b", status=TaskStatus.FAILED))
        assert g.is_complete
        assert not g.is_success
        assert g.failed_count == 1

    def test_get_task(self):
        g = TaskGraph(goal="test")
        t = SubTask(id="xyz")
        g.add_task(t)
        assert g.get_task("xyz") is t
        assert g.get_task("nope") is None

    def test_get_ready_tasks(self):
        g = TaskGraph(goal="test")
        t1 = SubTask(id="a", status=TaskStatus.COMPLETED)
        t2 = SubTask(id="b", dependencies=["a"])
        t3 = SubTask(id="c", dependencies=["b"])
        g.add_task(t1)
        g.add_task(t2)
        g.add_task(t3)

        ready = g.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "b"

    def test_get_ready_parallel(self):
        g = TaskGraph(goal="test")
        t1 = SubTask(id="a", status=TaskStatus.COMPLETED)
        t2 = SubTask(id="b", dependencies=["a"])
        t3 = SubTask(id="c", dependencies=["a"])
        g.add_task(t1)
        g.add_task(t2)
        g.add_task(t3)

        ready = g.get_ready_tasks()
        assert len(ready) == 2

    def test_get_handoffs(self):
        g = TaskGraph(goal="test")
        payload = HandoffPayload("a", AgentType.VISION, {"manifest": {}})
        t1 = SubTask(id="a", status=TaskStatus.COMPLETED, result=payload)
        t2 = SubTask(id="b", dependencies=["a"])
        g.add_task(t1)
        g.add_task(t2)

        handoffs = g.get_handoffs_for(t2)
        assert len(handoffs) == 1
        assert handoffs[0].agent_type == AgentType.VISION

    def test_to_dict(self):
        g = TaskGraph(goal="Build page")
        g.add_task(SubTask(agent_type=AgentType.VISION))
        d = g.to_dict()
        assert d["goal"] == "Build page"
        assert d["taskCount"] == 1
        assert "progress" in d

    def test_summary(self):
        g = TaskGraph(goal="Build form")
        g.add_task(SubTask(agent_type=AgentType.VISION, description="Analyze UI"))
        g.add_task(SubTask(agent_type=AgentType.MIGRATION, description="Create file", dependencies=["x"]))
        s = g.summary()
        assert "Build form" in s
        assert "vision" in s
        assert "migration" in s

    def test_duration(self):
        g = TaskGraph(created_at=100.0, completed_at=100.8)
        assert abs(g.duration_ms - 800.0) < 0.1


# ═══════════════════════════════════════════════════════════════════════════
# ChiefArchitect tests
# ═══════════════════════════════════════════════════════════════════════════

class TestChiefArchitect:
    @pytest.fixture
    def chief(self):
        return ChiefArchitect()

    def test_vision_detection(self, chief):
        graph = chief.decompose("Match this design screenshot")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.VISION in agents

    def test_graph_detection(self, chief):
        graph = chief.decompose("Find where the database schema is used")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.GRAPH in agents

    def test_migration_detection(self, chief):
        graph = chief.decompose("Create a new user profile component")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.MIGRATION in agents

    def test_heal_detection(self, chief):
        graph = chief.decompose("Fix the failing test in auth module")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.HEAL in agents

    def test_recipe_detection(self, chief):
        graph = chief.decompose("Standardize all string formatting")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.RECIPE in agents

    def test_jury_detection(self, chief):
        graph = chief.decompose("Review this code for security issues")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.JURY in agents

    def test_image_triggers_vision(self, chief):
        graph = chief.decompose("Build this", image_base64="abc123")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.VISION in agents

    def test_multi_agent_goal(self, chief):
        graph = chief.decompose(
            "Build a contact form based on this image and save data to the DB"
        )
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.VISION in agents or AgentType.MIGRATION in agents

    def test_dependencies_ordered(self, chief):
        graph = chief.decompose(
            "Match this design screenshot and create the component",
            workspace_path="/tmp/proj",
        )
        vision_tasks = [t for t in graph.tasks if t.agent_type == AgentType.VISION]
        migration_tasks = [t for t in graph.tasks if t.agent_type == AgentType.MIGRATION]

        if vision_tasks and migration_tasks:
            assert vision_tasks[0].id in migration_tasks[0].dependencies

    def test_jury_always_last(self, chief):
        graph = chief.decompose(
            "Build a secure form and review it for security",
            workspace_path="/tmp/proj",
        )
        jury_tasks = [t for t in graph.tasks if t.agent_type == AgentType.JURY]
        if jury_tasks:
            jury = jury_tasks[0]
            assert jury.priority >= 10

    def test_index_added_with_workspace(self, chief):
        graph = chief.decompose("Refactor this", workspace_path="/tmp/proj")
        index_tasks = [t for t in graph.tasks if t.agent_type == AgentType.INDEX]
        assert len(index_tasks) == 1

    def test_no_index_without_workspace(self, chief):
        graph = chief.decompose("Refactor this")
        index_tasks = [t for t in graph.tasks if t.agent_type == AgentType.INDEX]
        assert len(index_tasks) == 0

    def test_fallback_refactor(self, chief):
        graph = chief.decompose("Do something generic")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.REFACTOR in agents

    def test_decompose_from_json(self, chief):
        raw = '{"tasks": [{"agentType": "vision", "description": "Analyze", "dependencies": []}]}'
        graph = chief.decompose_from_json("test goal", raw)
        assert graph.task_count == 1
        assert graph.tasks[0].agent_type == AgentType.VISION

    def test_decompose_from_invalid_json(self, chief):
        graph = chief.decompose_from_json("test", "not json")
        assert graph.task_count >= 1

    def test_full_pipeline_phrase(self, chief):
        graph = chief.decompose("Build a dashboard based on this image")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.MIGRATION in agents or AgentType.VISION in agents


# ═══════════════════════════════════════════════════════════════════════════
# SwarmController tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSwarmController:
    @pytest.fixture
    def controller(self):
        return SwarmController()

    def _make_graph(self, tasks: List[SubTask]) -> TaskGraph:
        g = TaskGraph(goal="test")
        for t in tasks:
            g.add_task(t)
        return g

    def test_execute_simple(self, controller):
        graph = self._make_graph([
            SubTask(id="a", agent_type=AgentType.REFACTOR, description="Do it"),
        ])
        result = controller.execute_sync(graph)
        assert result.is_complete
        assert result.is_success
        assert result.tasks[0].status == TaskStatus.COMPLETED

    def test_execute_chain(self, controller):
        graph = self._make_graph([
            SubTask(id="a", agent_type=AgentType.INDEX, description="Index"),
            SubTask(id="b", agent_type=AgentType.REFACTOR, description="Refactor", dependencies=["a"]),
        ])
        result = controller.execute_sync(graph)
        assert result.is_complete
        assert all(t.status == TaskStatus.COMPLETED for t in result.tasks)

    def test_handoff_propagation(self, controller):
        def source_agent(task, handoffs):
            return HandoffPayload(task.id, AgentType.VISION, {"manifest": {"key": "val"}})

        def sink_agent(task, handoffs):
            assert len(handoffs) == 1
            assert handoffs[0].data["manifest"]["key"] == "val"
            return HandoffPayload(task.id, AgentType.MIGRATION, {"received": True})

        controller.register_agent(AgentType.VISION, source_agent)
        controller.register_agent(AgentType.MIGRATION, sink_agent)

        graph = self._make_graph([
            SubTask(id="vis", agent_type=AgentType.VISION),
            SubTask(id="mig", agent_type=AgentType.MIGRATION, dependencies=["vis"]),
        ])
        result = controller.execute_sync(graph)
        assert result.is_success
        assert result.tasks[1].result.data["received"]

    def test_failure_cascading(self, controller):
        def failing_agent(task, handoffs):
            raise RuntimeError("Agent crashed")

        controller.register_agent(AgentType.INDEX, failing_agent)

        graph = self._make_graph([
            SubTask(id="a", agent_type=AgentType.INDEX),
            SubTask(id="b", agent_type=AgentType.REFACTOR, dependencies=["a"]),
        ])
        result = controller.execute_sync(graph)
        assert result.is_complete
        assert not result.is_success
        assert result.tasks[0].status == TaskStatus.FAILED
        assert result.tasks[1].status == TaskStatus.SKIPPED
        assert "crashed" in result.tasks[0].error.lower()

    def test_parallel_ready(self, controller):
        execution_order = []

        def tracking_agent(task, handoffs):
            execution_order.append(task.id)
            return HandoffPayload(task.id, task.agent_type, {})

        controller.register_agent(AgentType.VISION, tracking_agent)
        controller.register_agent(AgentType.GRAPH, tracking_agent)
        controller.register_agent(AgentType.MIGRATION, tracking_agent)

        graph = self._make_graph([
            SubTask(id="root", agent_type=AgentType.INDEX, status=TaskStatus.COMPLETED),
            SubTask(id="vis", agent_type=AgentType.VISION, dependencies=["root"]),
            SubTask(id="gra", agent_type=AgentType.GRAPH, dependencies=["root"]),
            SubTask(id="mig", agent_type=AgentType.MIGRATION, dependencies=["vis", "gra"]),
        ])
        result = controller.execute_sync(graph)
        assert result.is_success
        assert "mig" in execution_order
        mig_idx = execution_order.index("mig")
        assert execution_order.index("vis") < mig_idx
        assert execution_order.index("gra") < mig_idx

    def test_register_custom_agent(self, controller):
        called = []

        def custom_fn(task, handoffs):
            called.append(task.id)
            return HandoffPayload(task.id, AgentType.CHAT, {"answer": "42"})

        controller.register_agent(AgentType.CHAT, custom_fn)
        graph = self._make_graph([
            SubTask(id="q", agent_type=AgentType.CHAT, description="Ask something"),
        ])
        result = controller.execute_sync(graph)
        assert result.is_success
        assert "q" in called


# ═══════════════════════════════════════════════════════════════════════════
# Event callback tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSwarmEvents:
    def test_events_emitted(self):
        events = []

        controller = SwarmController()
        controller.set_event_callback(lambda p: events.append(p))

        graph = TaskGraph(goal="test")
        graph.add_task(SubTask(id="a", agent_type=AgentType.REFACTOR))
        controller.execute_sync(graph)

        event_types = [e["event"] for e in events]
        assert "SWARM_STARTED" in event_types
        assert "TASK_STARTED" in event_types
        assert "TASK_COMPLETED" in event_types
        assert "SWARM_COMPLETED" in event_types

    def test_event_contains_progress(self):
        events = []
        controller = SwarmController()
        controller.set_event_callback(lambda p: events.append(p))

        graph = TaskGraph(goal="test")
        graph.add_task(SubTask(id="a", agent_type=AgentType.REFACTOR))
        graph.add_task(SubTask(id="b", agent_type=AgentType.REFACTOR, dependencies=["a"]))
        controller.execute_sync(graph)

        completed_events = [e for e in events if e["event"] == "TASK_COMPLETED"]
        assert len(completed_events) == 2
        assert completed_events[0]["progress"] == 0.5
        assert completed_events[1]["progress"] == 1.0

    def test_event_contains_task_info(self):
        events = []
        controller = SwarmController()
        controller.set_event_callback(lambda p: events.append(p))

        graph = TaskGraph(goal="test")
        graph.add_task(SubTask(id="myid", agent_type=AgentType.VISION, description="Analyze"))
        controller.execute_sync(graph)

        task_events = [e for e in events if "task" in e]
        assert any(e["task"]["id"] == "myid" for e in task_events)
        assert any(e["task"]["agentType"] == "vision" for e in task_events)

    def test_failure_event(self):
        events = []
        controller = SwarmController()
        controller.set_event_callback(lambda p: events.append(p))

        def bad_agent(task, handoffs):
            raise ValueError("boom")

        controller.register_agent(AgentType.REFACTOR, bad_agent)

        graph = TaskGraph(goal="test")
        graph.add_task(SubTask(id="a", agent_type=AgentType.REFACTOR))
        controller.execute_sync(graph)

        assert any(e["event"] == "TASK_FAILED" for e in events)
        failed = [e for e in events if e["event"] == "TASK_FAILED"][0]
        assert "boom" in failed["task"]["error"]

    def test_skipped_event(self):
        events = []
        controller = SwarmController()
        controller.set_event_callback(lambda p: events.append(p))

        def bad_agent(task, handoffs):
            raise ValueError("fail")

        controller.register_agent(AgentType.INDEX, bad_agent)

        graph = TaskGraph(goal="test")
        graph.add_task(SubTask(id="a", agent_type=AgentType.INDEX))
        graph.add_task(SubTask(id="b", agent_type=AgentType.REFACTOR, dependencies=["a"]))
        controller.execute_sync(graph)

        assert any(e["event"] == "TASK_SKIPPED" for e in events)

    def test_no_callback_ok(self):
        controller = SwarmController()
        graph = TaskGraph(goal="test")
        graph.add_task(SubTask(id="a", agent_type=AgentType.REFACTOR))
        result = controller.execute_sync(graph)
        assert result.is_success


# ═══════════════════════════════════════════════════════════════════════════
# Async execution tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAsyncExecution:
    @pytest.mark.asyncio
    async def test_async_execute(self):
        controller = SwarmController()
        graph = TaskGraph(goal="async test")
        graph.add_task(SubTask(id="a", agent_type=AgentType.REFACTOR))
        result = await controller.execute(graph)
        assert result.is_success

    @pytest.mark.asyncio
    async def test_async_parallel(self):
        order = []

        def tracking(task, handoffs):
            order.append(task.id)
            return HandoffPayload(task.id, task.agent_type, {})

        controller = SwarmController()
        controller.register_agent(AgentType.VISION, tracking)
        controller.register_agent(AgentType.GRAPH, tracking)
        controller.register_agent(AgentType.MIGRATION, tracking)

        graph = TaskGraph(goal="async parallel")
        graph.add_task(SubTask(id="root", status=TaskStatus.COMPLETED))
        graph.add_task(SubTask(id="v", agent_type=AgentType.VISION, dependencies=["root"]))
        graph.add_task(SubTask(id="g", agent_type=AgentType.GRAPH, dependencies=["root"]))
        graph.add_task(SubTask(id="m", agent_type=AgentType.MIGRATION, dependencies=["v", "g"]))
        result = await controller.execute(graph)
        assert result.is_success
        assert order.index("m") > order.index("v")
        assert order.index("m") > order.index("g")


# ═══════════════════════════════════════════════════════════════════════════
# Integration: full pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_design_to_code_pipeline(self):
        chief = ChiefArchitect()
        graph = chief.decompose(
            "Build a contact form based on this image and save data to the DB",
            image_base64="base64data",
            workspace_path="/tmp/project",
        )

        # Should have index + vision + graph/migration + possibly jury
        assert graph.task_count >= 3
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.INDEX in agents

        controller = SwarmController()
        events = []
        controller.set_event_callback(lambda p: events.append(p))
        result = controller.execute_sync(graph)

        assert result.is_complete
        assert len(events) >= 4  # at least SWARM_STARTED + N tasks + SWARM_COMPLETED

    def test_dark_mode_refactor(self):
        chief = ChiefArchitect()
        graph = chief.decompose("Add dark mode to the user profile page")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.VISION in agents or AgentType.MIGRATION in agents

    def test_fix_and_review(self):
        chief = ChiefArchitect()
        graph = chief.decompose("Fix the failing test and review for security")
        agents = {t.agent_type for t in graph.tasks}
        assert AgentType.HEAL in agents or AgentType.JURY in agents


# ═══════════════════════════════════════════════════════════════════════════
# API tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSwarmAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        self.client = TestClient(app)
        # Clear stored graphs between tests
        from code4u.interfaces.api.routes import swarm
        swarm._graphs.clear()
        swarm._events.clear()
        yield

    def test_plan_endpoint(self):
        resp = self.client.post("/api/v1/swarm/plan", json={
            "goal": "Match this design screenshot and create component",
            "workspacePath": "/tmp/proj",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "graph" in data
        assert data["graph"]["taskCount"] >= 2
        assert "summary" in data

    def test_execute_endpoint(self):
        resp = self.client.post("/api/v1/swarm/execute", json={
            "goal": "Do a simple refactor",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["graph"]["isComplete"]
        assert len(data["events"]) >= 2

    def test_get_graph(self):
        # Create one first
        resp = self.client.post("/api/v1/swarm/execute", json={
            "goal": "Test get",
        })
        graph_id = resp.json()["graph"]["id"]

        resp2 = self.client.get(f"/api/v1/swarm/{graph_id}")
        assert resp2.status_code == 200
        assert resp2.json()["graph"]["id"] == graph_id

    def test_get_graph_not_found(self):
        resp = self.client.get("/api/v1/swarm/nonexistent")
        assert resp.status_code == 404

    def test_list_graphs(self):
        self.client.post("/api/v1/swarm/execute", json={"goal": "A"})
        self.client.post("/api/v1/swarm/execute", json={"goal": "B"})

        resp = self.client.get("/api/v1/swarm")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_plan_with_image(self):
        resp = self.client.post("/api/v1/swarm/plan", json={
            "goal": "Build this UI",
            "imageBase64": "base64imagedata",
        })
        assert resp.status_code == 200
        agents = [t["agentType"] for t in resp.json()["graph"]["tasks"]]
        assert "vision" in agents

    def test_execute_events_returned(self):
        resp = self.client.post("/api/v1/swarm/execute", json={
            "goal": "Simple task",
        })
        assert resp.status_code == 200
        events = resp.json()["events"]
        event_types = [e["event"] for e in events]
        assert "SWARM_STARTED" in event_types
        assert "SWARM_COMPLETED" in event_types
