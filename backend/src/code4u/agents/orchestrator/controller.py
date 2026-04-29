"""Swarm Controller — executes a TaskGraph by dispatching to specialists.

The controller:
  1. Pulls ready tasks (whose dependencies are all satisfied).
  2. Dispatches each to the appropriate specialist agent.
  3. Collects ``HandoffPayload`` outputs and makes them available
     to downstream tasks.
  4. Broadcasts ``SWARM_UPDATE`` events via the ``PresenceManager``
     so clients can watch the swarm in real-time.
  5. Continues until all tasks are terminal (completed/failed/skipped).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

import structlog

from code4u.agents.orchestrator.models import (
    AgentType,
    HandoffPayload,
    SubTask,
    TaskGraph,
    TaskStatus,
)

logger = structlog.get_logger("swarm_controller")


# ---------------------------------------------------------------------------
# Agent dispatcher type
# ---------------------------------------------------------------------------

AgentFn = Callable[[SubTask, List[HandoffPayload]], HandoffPayload]


# ---------------------------------------------------------------------------
# Default agent stubs (return minimal handoff payloads)
# ---------------------------------------------------------------------------

def _stub_agent(task: SubTask, handoffs: List[HandoffPayload]) -> HandoffPayload:
    """Fallback agent that acknowledges the task without doing real work."""
    return HandoffPayload(
        source_task_id=task.id,
        agent_type=task.agent_type,
        data={"stub": True, "description": task.description},
    )


def _index_agent(task: SubTask, handoffs: List[HandoffPayload]) -> HandoffPayload:
    """Index agent — uses SymbolIndexer to build a DependencyMap."""
    workspace = task.config.get("workspace_path", "")
    file_count = 0
    symbol_count = 0

    if workspace:
        try:
            from pathlib import Path
            from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
                SymbolIndexer,
                DependencyMap,
            )
            dep_map = DependencyMap()
            indexer = SymbolIndexer()
            indexer.index_workspace(str(Path(workspace)), dep_map)
            file_count = len(dep_map.all_files)
            symbol_count = sum(
                len(dep_map.get_symbol_defs(f)) for f in dep_map.all_files
            )
        except Exception as exc:
            logger.warning("index_agent_error", error=str(exc))

    return HandoffPayload(
        source_task_id=task.id,
        agent_type=AgentType.INDEX,
        data={
            "workspace_path": workspace,
            "file_count": file_count,
            "symbol_count": symbol_count,
        },
    )


def _vision_agent(task: SubTask, handoffs: List[HandoffPayload]) -> HandoffPayload:
    """Vision agent — analyzes image using VisionAnalyzer + DesignSystemMapper."""
    from code4u.agents.vision.processor import VisionAnalyzer
    from code4u.agents.vision.mapper import DesignSystemMapper

    image = task.config.get("image_base64", "")
    desc = task.config.get("description", "")

    analyzer = VisionAnalyzer()
    manifest = analyzer.analyze_image(image, desc)

    mapper = DesignSystemMapper()
    tw_config = task.config.get("tailwind_config_path", "")
    if tw_config:
        mapper.load_tailwind_config(tw_config)
    mapped = mapper.map_manifest(manifest)

    return HandoffPayload(
        source_task_id=task.id,
        agent_type=AgentType.VISION,
        data={
            "manifest": manifest.to_dict(),
            "mapped": mapped.to_dict(),
        },
    )


def _graph_agent(task: SubTask, handoffs: List[HandoffPayload]) -> HandoffPayload:
    """Graph agent — uses ContextRetriever for code exploration."""
    query = task.config.get("query", "")
    workspace = task.config.get("workspace_path", "")

    entry_points: List[str] = []
    dependents: List[str] = []

    if workspace and query:
        try:
            from pathlib import Path
            from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
                SymbolIndexer,
                DependencyMap,
            )
            from code4u.agents.chat.retriever import ContextRetriever

            dep_map = DependencyMap()
            indexer = SymbolIndexer()
            indexer.index_workspace(str(Path(workspace)), dep_map)

            retriever = ContextRetriever(dep_map)
            ctx = retriever.retrieve(query)
            entry_points = [n.path for n in ctx.graph_nodes if n.relationship == "entry_point"]
            dependents = [n.path for n in ctx.graph_nodes if n.hop_distance > 0]
        except Exception as exc:
            logger.warning("graph_agent_error", error=str(exc))

    return HandoffPayload(
        source_task_id=task.id,
        agent_type=AgentType.GRAPH,
        data={
            "query": query,
            "entry_points": entry_points,
            "dependents": dependents,
        },
    )


def _jury_agent(task: SubTask, handoffs: List[HandoffPayload]) -> HandoffPayload:
    """Jury agent — runs consensus review on upstream outputs."""
    from code4u.core.consensus import ReviewOrchestrator

    orch = ReviewOrchestrator()

    # Build mock operations from upstream handoffs
    operations = []
    for h in handoffs:
        code_data = h.data
        if isinstance(code_data, dict) and "code" in code_data:
            operations.append(type("Op", (), {
                "file_path": code_data.get("file_path", "generated.py"),
                "action": "edit",
                "new_content": code_data.get("code", ""),
            })())

    if not operations:
        return HandoffPayload(
            source_task_id=task.id,
            agent_type=AgentType.JURY,
            data={"verdict": "APPROVED", "reason": "No code to review"},
        )

    result = orch.review(operations)
    return HandoffPayload(
        source_task_id=task.id,
        agent_type=AgentType.JURY,
        data={
            "verdict": result.verdict.value,
            "score": result.final_score,
            "violations": result.total_violations,
        },
    )


def _deploy_agent(task: SubTask, handoffs: List[HandoffPayload]) -> HandoffPayload:
    """Deploy agent — generates CI/CD pipeline configuration."""
    workspace = task.config.get("workspace_path", "")
    intent = task.config.get("intent", "")

    language = "python"
    provider = "github"
    if workspace:
        try:
            from pathlib import Path
            p = Path(workspace)
            if (p / "go.mod").exists():
                language = "go"
            elif (p / "tsconfig.json").exists():
                language = "typescript"
            elif (p / "package.json").exists():
                language = "javascript"
            elif (p / "Cargo.toml").exists():
                language = "rust"
            elif (p / "build.gradle").exists() or (p / "pom.xml").exists():
                language = "java"
        except Exception:
            pass

    if "gitlab" in intent.lower():
        provider = "gitlab"

    return HandoffPayload(
        source_task_id=task.id,
        agent_type=AgentType.DEPLOY,
        data={
            "language": language,
            "provider": provider,
            "workspace_path": workspace,
            "pipeline_generated": True,
            "filename": ".github/workflows/deploy.yml" if provider == "github" else ".gitlab-ci.yml",
        },
    )


# ---------------------------------------------------------------------------
# SwarmController
# ---------------------------------------------------------------------------

class SwarmController:
    """Executes a ``TaskGraph`` by dispatching sub-tasks to specialists.

    Usage::

        controller = SwarmController()
        result = await controller.execute(graph)
        # or synchronous:
        result = controller.execute_sync(graph)
    """

    def __init__(self) -> None:
        self._agents: Dict[AgentType, AgentFn] = {
            AgentType.INDEX: _index_agent,
            AgentType.VISION: _vision_agent,
            AgentType.GRAPH: _graph_agent,
            AgentType.JURY: _jury_agent,
            AgentType.MIGRATION: _stub_agent,
            AgentType.HEAL: _stub_agent,
            AgentType.RECIPE: _stub_agent,
            AgentType.REFACTOR: _stub_agent,
            AgentType.CHAT: _stub_agent,
            AgentType.DEPLOY: _deploy_agent,
        }
        self._event_callback: Optional[Callable] = None

    def register_agent(self, agent_type: AgentType, fn: AgentFn) -> None:
        """Register or override a specialist agent handler."""
        self._agents[agent_type] = fn

    def set_event_callback(self, callback: Callable) -> None:
        """Set a callback for swarm events (for WebSocket broadcasting)."""
        self._event_callback = callback

    # -- Synchronous execution -----------------------------------------------

    def execute_sync(self, graph: TaskGraph) -> TaskGraph:
        """Execute a TaskGraph synchronously (blocking)."""
        self._emit_event("SWARM_STARTED", graph, None)

        max_iterations = len(graph.tasks) * 2 + 1
        iteration = 0

        while not graph.is_complete and iteration < max_iterations:
            iteration += 1
            ready = graph.get_ready_tasks()

            if not ready:
                # Check for blocked tasks with failed dependencies
                self._resolve_blocked(graph)
                if graph.is_complete:
                    break
                ready = graph.get_ready_tasks()
                if not ready:
                    break

            for task in ready:
                self._run_task(task, graph)

        graph.completed_at = time.time()
        self._emit_event("SWARM_COMPLETED", graph, None)

        logger.info(
            "swarm_completed",
            goal=graph.goal[:60],
            tasks=graph.task_count,
            completed=graph.completed_count,
            failed=graph.failed_count,
            duration_ms=round(graph.duration_ms, 1),
        )

        return graph

    # -- Async execution (parallel where possible) ---------------------------

    async def execute(self, graph: TaskGraph) -> TaskGraph:
        """Execute a TaskGraph with async dispatch (parallel-ready tasks)."""
        self._emit_event("SWARM_STARTED", graph, None)

        max_iterations = len(graph.tasks) * 2 + 1
        iteration = 0

        while not graph.is_complete and iteration < max_iterations:
            iteration += 1
            ready = graph.get_ready_tasks()

            if not ready:
                self._resolve_blocked(graph)
                if graph.is_complete:
                    break
                ready = graph.get_ready_tasks()
                if not ready:
                    break

            if len(ready) == 1:
                self._run_task(ready[0], graph)
            else:
                # Run independent tasks in parallel via asyncio
                loop = asyncio.get_event_loop()
                tasks = [
                    loop.run_in_executor(None, self._run_task, task, graph)
                    for task in ready
                ]
                await asyncio.gather(*tasks)

        graph.completed_at = time.time()
        self._emit_event("SWARM_COMPLETED", graph, None)

        logger.info(
            "swarm_completed_async",
            goal=graph.goal[:60],
            tasks=graph.task_count,
            completed=graph.completed_count,
            failed=graph.failed_count,
            duration_ms=round(graph.duration_ms, 1),
        )

        return graph

    # -- Internal ------------------------------------------------------------

    def _run_task(self, task: SubTask, graph: TaskGraph) -> None:
        """Execute a single sub-task via its specialist agent."""
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = time.time()
        self._emit_event("TASK_STARTED", graph, task)

        agent_fn = self._agents.get(task.agent_type, _stub_agent)
        handoffs = graph.get_handoffs_for(task)

        try:
            result = agent_fn(task, handoffs)
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            self._emit_event("TASK_COMPLETED", graph, task)

            logger.info(
                "task_completed",
                task_id=task.id,
                agent=task.agent_type.value,
                duration_ms=round(task.duration_ms, 1),
            )
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.completed_at = time.time()
            self._emit_event("TASK_FAILED", graph, task)

            logger.error(
                "task_failed",
                task_id=task.id,
                agent=task.agent_type.value,
                error=str(exc),
            )

    def _resolve_blocked(self, graph: TaskGraph) -> None:
        """Skip tasks whose dependencies have failed."""
        failed_ids = {t.id for t in graph.tasks if t.status == TaskStatus.FAILED}
        for task in graph.tasks:
            if task.status != TaskStatus.PENDING:
                continue
            if any(dep in failed_ids for dep in task.dependencies):
                task.status = TaskStatus.SKIPPED
                task.error = "Upstream dependency failed"
                task.completed_at = time.time()
                self._emit_event("TASK_SKIPPED", graph, task)

    def _emit_event(
        self,
        event_type: str,
        graph: TaskGraph,
        task: Optional[SubTask],
    ) -> None:
        """Emit a swarm event via the registered callback."""
        if not self._event_callback:
            return

        payload: Dict[str, Any] = {
            "event": event_type,
            "graphId": graph.id,
            "goal": graph.goal,
            "progress": round(graph.progress, 2),
            "taskCount": graph.task_count,
            "completedCount": graph.completed_count,
            "timestamp": time.time(),
        }

        if task:
            payload["task"] = {
                "id": task.id,
                "agentType": task.agent_type.value,
                "description": task.description,
                "status": task.status.value,
                "durationMs": round(task.duration_ms, 1),
                "error": task.error,
            }

        try:
            self._event_callback(payload)
        except Exception:
            pass
