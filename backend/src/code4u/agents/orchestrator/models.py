"""Task schema for the Autonomous Swarm Orchestrator.

Defines the data models that the Chief Architect produces and
the Swarm Controller consumes:

  - ``AgentType``    — which specialist to invoke.
  - ``TaskStatus``   — lifecycle state of a sub-task.
  - ``SubTask``      — one unit of work assigned to a specialist.
  - ``HandoffPayload`` — output from one agent passed to the next.
  - ``TaskGraph``    — the complete execution plan with dependencies.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentType(str, Enum):
    """Specialist agent types available in the swarm."""
    VISION = "vision"
    GRAPH = "graph"
    MIGRATION = "migration"
    HEAL = "heal"
    JURY = "jury"
    CHAT = "chat"
    RECIPE = "recipe"
    INDEX = "index"
    REFACTOR = "refactor"
    PROFILER = "profiler"
    DEPLOY = "deploy"


class TaskStatus(str, Enum):
    """Lifecycle state of a sub-task."""
    PENDING = "pending"
    BLOCKED = "blocked"       # waiting on upstream dependency
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class HandoffPayload:
    """Output from one agent that feeds into another.

    The ``data`` dict is agent-specific — e.g. the Vision agent
    produces ``{"manifest": {...}, "mapped": {...}}`` while the
    Graph agent produces ``{"entry_points": [...], "dependents": [...]}``.
    """
    source_task_id: str
    agent_type: AgentType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sourceTaskId": self.source_task_id,
            "agentType": self.agent_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class SubTask:
    """One unit of work assigned to a specialist agent."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_type: AgentType = AgentType.REFACTOR
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    result: Optional[HandoffPayload] = None
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    priority: int = 0  # lower = higher priority

    @property
    def duration_ms(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return 0.0

    @property
    def is_terminal(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED)

    @property
    def is_ready(self) -> bool:
        return self.status == TaskStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agentType": self.agent_type.value,
            "description": self.description,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "config": self.config,
            "result": self.result.to_dict() if self.result else None,
            "error": self.error,
            "durationMs": round(self.duration_ms, 1),
            "priority": self.priority,
        }


@dataclass
class TaskGraph:
    """Complete execution plan with sub-tasks and dependencies.

    The graph is a DAG — each ``SubTask.dependencies`` lists the IDs
    of tasks that must complete before it can start.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    goal: str = ""
    tasks: List[SubTask] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- Queries -------------------------------------------------------------

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @property
    def completed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)

    @property
    def progress(self) -> float:
        if not self.tasks:
            return 1.0
        terminal = sum(1 for t in self.tasks if t.is_terminal)
        return terminal / len(self.tasks)

    @property
    def is_complete(self) -> bool:
        return all(t.is_terminal for t in self.tasks)

    @property
    def is_success(self) -> bool:
        return self.is_complete and self.failed_count == 0

    def get_task(self, task_id: str) -> Optional[SubTask]:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def get_ready_tasks(self) -> List[SubTask]:
        """Return tasks whose dependencies are all satisfied."""
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        ready = []
        for t in self.tasks:
            if not t.is_ready:
                continue
            if all(dep in completed_ids for dep in t.dependencies):
                ready.append(t)
        return ready

    def get_handoffs_for(self, task: SubTask) -> List[HandoffPayload]:
        """Collect outputs from upstream dependencies."""
        handoffs = []
        for dep_id in task.dependencies:
            dep = self.get_task(dep_id)
            if dep and dep.result:
                handoffs.append(dep.result)
        return handoffs

    def add_task(self, task: SubTask) -> None:
        self.tasks.append(task)

    @property
    def duration_ms(self) -> float:
        if self.created_at and self.completed_at:
            return (self.completed_at - self.created_at) * 1000
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
            "taskCount": self.task_count,
            "completedCount": self.completed_count,
            "failedCount": self.failed_count,
            "progress": round(self.progress, 2),
            "isComplete": self.is_complete,
            "isSuccess": self.is_success,
            "durationMs": round(self.duration_ms, 1),
            "metadata": self.metadata,
        }

    def summary(self) -> str:
        parts = [f"TaskGraph '{self.goal}' ({self.task_count} tasks)"]
        for t in self.tasks:
            deps = f" (after {', '.join(t.dependencies)})" if t.dependencies else ""
            parts.append(f"  [{t.status.value:12s}] {t.agent_type.value:10s} — {t.description}{deps}")
        return "\n".join(parts)
