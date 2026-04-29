"""Chief Architect — high-reasoning goal decomposition.

Takes a natural-language *goal* and produces a ``TaskGraph`` —
a DAG of ``SubTask`` objects routed to specialist agents.

Two backends:
  1. **LLM** — sends the goal to Gemini 1.5 Pro / GPT-4o with a
     structured system prompt to produce a JSON task graph.
  2. **Local heuristic** — deterministic keyword-based decomposition
     for testing and offline usage.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import structlog

from code4u.agents.orchestrator.models import (
    AgentType,
    SubTask,
    TaskGraph,
    TaskStatus,
)

logger = structlog.get_logger("chief_architect")


# ---------------------------------------------------------------------------
# Keyword → agent routing tables
# ---------------------------------------------------------------------------

_VISION_KEYWORDS = [
    "screenshot", "image", "visual", "design", "mockup", "figma",
    "ui", "layout", "dark mode", "dark-mode", "color", "style",
    "css", "tailwind", "theme", "look like", "match this",
]

_GRAPH_KEYWORDS = [
    "find", "search", "where", "schema", "database", "db",
    "dependency", "import", "used by", "callers", "structure",
    "how does", "explain", "architecture",
]

_MIGRATION_KEYWORDS = [
    "move", "extract", "create file", "new file", "scaffold",
    "component", "page", "build", "generate", "add",
]

_HEAL_KEYWORDS = [
    "fix", "error", "bug", "broken", "heal", "repair",
    "failing", "test", "traceback", "stack trace",
]

_RECIPE_KEYWORDS = [
    "standardize", "lint", "recipe", "format", "convention",
    "best practice", "upgrade",
]

_PROFILER_KEYWORDS = [
    "performance", "optimize", "slow", "bottleneck", "latency",
    "profile", "speed up", "speedup", "cpu", "memory", "cache",
    "efficient", "o(n", "n+1", "profiler", "flame graph",
]

_JURY_KEYWORDS = [
    "review", "security", "audit", "quality", "safe",
    "guardrail", "check",
]

_DEPLOY_KEYWORDS = [
    "deploy", "ci/cd", "cicd", "pipeline", "github action",
    "gitlab ci", "dockerfile", "docker", "kubernetes", "k8s",
    "staging", "production", "release", "ship", "publish",
    "continuous integration", "continuous delivery",
]

# Sub-phrases that trigger a full pipeline
_FULL_PIPELINE_PHRASES = [
    "based on this image", "from this screenshot", "match this design",
    "save to", "persist", "store in db", "contact form",
    "build a", "create a", "add a",
]


# ---------------------------------------------------------------------------
# ChiefArchitect
# ---------------------------------------------------------------------------

class ChiefArchitect:
    """Decomposes a natural-language goal into a TaskGraph.

    Usage::

        chief = ChiefArchitect()
        graph = chief.decompose("Add a dark-mode user profile page")
        for task in graph.tasks:
            print(task.agent_type, task.description)
    """

    def decompose(
        self,
        goal: str,
        *,
        workspace_path: str = "",
        image_base64: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskGraph:
        """Decompose *goal* into a TaskGraph.

        Tries LLM decomposition first; falls back to local heuristics.
        If *context* contains ``"architectural_rules"`` (a string of
        rule descriptions), these are injected into every sub-task's
        config so specialist agents are aware of the "Laws of the Land."
        """
        graph = self._try_llm_decomposition(goal, workspace_path, image_base64, context)
        if graph is None:
            graph = self._local_decomposition(goal, workspace_path, image_base64, context)

        # JIT context: hydrate architectural rules into every sub-task
        rules_ctx = (context or {}).get("architectural_rules", "")
        if rules_ctx:
            for task in graph.tasks:
                task.config["architectural_rules"] = rules_ctx

        complexity = self.estimate_complexity(goal)
        for task in graph.tasks:
            task.config["estimated_complexity"] = complexity

        logger.info(
            "goal_decomposed",
            goal=goal[:80],
            tasks=graph.task_count,
            agents=[t.agent_type.value for t in graph.tasks],
            complexity=complexity,
        )
        return graph

    def estimate_complexity(self, goal: str) -> str:
        """Estimate task complexity: low / medium / high.

        Used by the SmartRouter to pick local (cheap) vs cloud (pro) models.
        """
        goal_lower = goal.lower()

        high_signals = [
            "refactor", "restructure", "migrate", "rewrite", "architect",
            "cross-file", "multi-file", "split into", "merge into",
            "convert to class", "extract to", "full-stack",
        ]
        low_signals = [
            "rename", "variable", "lint", "format", "typo", "comment",
            "unused import", "dead code", "documentation", "docstring",
            "health check", "simple", "trivial",
        ]

        high_count = sum(1 for s in high_signals if s in goal_lower)
        low_count = sum(1 for s in low_signals if s in goal_lower)

        if high_count >= 2 or len(goal) > 200:
            return "high"
        if low_count >= 1 and high_count == 0:
            return "low"
        if high_count == 1:
            return "medium"
        return "low" if len(goal) < 60 else "medium"

    def decompose_from_json(self, goal: str, raw_json: str) -> TaskGraph:
        """Parse a raw JSON task graph (e.g., from an LLM response)."""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return self._local_decomposition(goal, "", "", None)
        return self._parse_task_graph_json(goal, data)

    # -- LLM backend ---------------------------------------------------------

    def _try_llm_decomposition(
        self,
        goal: str,
        workspace_path: str,
        image_base64: str,
        context: Optional[Dict[str, Any]],
    ) -> Optional[TaskGraph]:
        """Attempt decomposition via a high-reasoning LLM."""
        return None

    # -- Local heuristic decomposition ---------------------------------------

    def _local_decomposition(
        self,
        goal: str,
        workspace_path: str,
        image_base64: str,
        context: Optional[Dict[str, Any]],
    ) -> TaskGraph:
        """Deterministic keyword-based goal decomposition."""
        goal_lower = goal.lower()
        graph = TaskGraph(goal=goal)
        context = context or {}

        detected_agents = self._detect_agents(goal_lower, image_base64)

        # Always start with indexing if workspace provided
        prev_ids: List[str] = []
        if workspace_path:
            index_task = SubTask(
                agent_type=AgentType.INDEX,
                description=f"Index workspace at {workspace_path}",
                config={"workspace_path": workspace_path},
                priority=0,
            )
            graph.add_task(index_task)
            prev_ids = [index_task.id]

        # Vision analysis (if image provided or visual keywords detected)
        vision_id = ""
        if AgentType.VISION in detected_agents:
            vision_task = SubTask(
                agent_type=AgentType.VISION,
                description=self._build_description(AgentType.VISION, goal),
                dependencies=list(prev_ids),
                config={
                    "image_base64": image_base64,
                    "description": goal,
                },
                priority=1,
            )
            graph.add_task(vision_task)
            vision_id = vision_task.id

        # Graph analysis (find schemas, dependencies, architecture)
        graph_id = ""
        if AgentType.GRAPH in detected_agents:
            graph_task = SubTask(
                agent_type=AgentType.GRAPH,
                description=self._build_description(AgentType.GRAPH, goal),
                dependencies=list(prev_ids),
                config={
                    "query": goal,
                    "workspace_path": workspace_path,
                },
                priority=1,
            )
            graph.add_task(graph_task)
            graph_id = graph_task.id

        # Migration / code generation (depends on vision + graph if present)
        migration_deps: List[str] = []
        if vision_id:
            migration_deps.append(vision_id)
        if graph_id:
            migration_deps.append(graph_id)
        if not migration_deps and prev_ids:
            migration_deps = list(prev_ids)

        if AgentType.MIGRATION in detected_agents:
            migration_task = SubTask(
                agent_type=AgentType.MIGRATION,
                description=self._build_description(AgentType.MIGRATION, goal),
                dependencies=migration_deps,
                config={"intent": goal, "workspace_path": workspace_path},
                priority=2,
            )
            graph.add_task(migration_task)
            migration_deps = [migration_task.id]

        # Heal agent (typically standalone)
        if AgentType.HEAL in detected_agents and AgentType.MIGRATION not in detected_agents:
            heal_task = SubTask(
                agent_type=AgentType.HEAL,
                description=self._build_description(AgentType.HEAL, goal),
                dependencies=list(prev_ids),
                config={"error_text": goal, "workspace_path": workspace_path},
                priority=2,
            )
            graph.add_task(heal_task)
            migration_deps = [heal_task.id]

        # Recipe agent (standalone)
        if AgentType.RECIPE in detected_agents and AgentType.MIGRATION not in detected_agents:
            recipe_task = SubTask(
                agent_type=AgentType.RECIPE,
                description=self._build_description(AgentType.RECIPE, goal),
                dependencies=list(prev_ids),
                config={"intent": goal, "workspace_path": workspace_path},
                priority=2,
            )
            graph.add_task(recipe_task)
            migration_deps = [recipe_task.id]

        # Profiler agent (performance tuning pipeline)
        if AgentType.PROFILER in detected_agents:
            profiler_task = SubTask(
                agent_type=AgentType.PROFILER,
                description=self._build_description(AgentType.PROFILER, goal),
                dependencies=list(prev_ids),
                config={"intent": goal, "workspace_path": workspace_path},
                priority=2,
            )
            graph.add_task(profiler_task)
            migration_deps = [profiler_task.id]

        # Deploy agent (CI/CD pipeline generation)
        if AgentType.DEPLOY in detected_agents:
            deploy_task = SubTask(
                agent_type=AgentType.DEPLOY,
                description=self._build_description(AgentType.DEPLOY, goal),
                dependencies=list(prev_ids),
                config={"intent": goal, "workspace_path": workspace_path},
                priority=3,
            )
            graph.add_task(deploy_task)
            migration_deps = [deploy_task.id]

        # Refactor (generic fallback if no specific agent matched)
        if not detected_agents or (
            detected_agents == {AgentType.JURY}
        ):
            refactor_task = SubTask(
                agent_type=AgentType.REFACTOR,
                description=f"Execute refactor: {goal}",
                dependencies=list(prev_ids),
                config={"intent": goal, "workspace_path": workspace_path},
                priority=2,
            )
            graph.add_task(refactor_task)
            migration_deps = [refactor_task.id]

        # Quality review (always last if jury detected or multi-step)
        if AgentType.JURY in detected_agents or len(graph.tasks) >= 3:
            code_task_ids = [
                t.id for t in graph.tasks
                if t.agent_type in (AgentType.MIGRATION, AgentType.REFACTOR, AgentType.HEAL, AgentType.RECIPE)
            ]
            jury_task = SubTask(
                agent_type=AgentType.JURY,
                description="Quality review: security, complexity, and best practices",
                dependencies=code_task_ids if code_task_ids else list(prev_ids),
                priority=10,
            )
            graph.add_task(jury_task)

        return graph

    def _detect_agents(self, goal_lower: str, image_base64: str) -> set:
        """Detect which specialist agents are needed."""
        agents = set()

        if image_base64 or any(kw in goal_lower for kw in _VISION_KEYWORDS):
            agents.add(AgentType.VISION)

        if any(kw in goal_lower for kw in _GRAPH_KEYWORDS):
            agents.add(AgentType.GRAPH)

        if any(kw in goal_lower for kw in _MIGRATION_KEYWORDS):
            agents.add(AgentType.MIGRATION)

        if any(kw in goal_lower for kw in _HEAL_KEYWORDS):
            agents.add(AgentType.HEAL)

        if any(kw in goal_lower for kw in _RECIPE_KEYWORDS):
            agents.add(AgentType.RECIPE)

        if any(kw in goal_lower for kw in _PROFILER_KEYWORDS):
            agents.add(AgentType.PROFILER)

        if any(kw in goal_lower for kw in _JURY_KEYWORDS):
            agents.add(AgentType.JURY)

        if any(kw in goal_lower for kw in _DEPLOY_KEYWORDS):
            agents.add(AgentType.DEPLOY)

        # Full pipeline phrases imply migration
        if any(phrase in goal_lower for phrase in _FULL_PIPELINE_PHRASES):
            agents.add(AgentType.MIGRATION)

        return agents

    def _build_description(self, agent: AgentType, goal: str) -> str:
        """Generate a human-readable description for a sub-task."""
        prefixes = {
            AgentType.VISION: "Analyze visual design",
            AgentType.GRAPH: "Analyze code architecture",
            AgentType.MIGRATION: "Generate/migrate code",
            AgentType.HEAL: "Diagnose and repair errors",
            AgentType.RECIPE: "Apply code recipe",
            AgentType.REFACTOR: "Execute refactor",
            AgentType.JURY: "Quality review",
            AgentType.INDEX: "Index workspace",
            AgentType.CHAT: "Answer architectural question",
            AgentType.PROFILER: "Profile and optimize performance",
            AgentType.DEPLOY: "Generate CI/CD pipeline and deployment config",
        }
        prefix = prefixes.get(agent, "Execute task")
        short_goal = goal[:60] + "..." if len(goal) > 60 else goal
        return f"{prefix}: {short_goal}"

    # -- JSON parsing --------------------------------------------------------

    def _parse_task_graph_json(self, goal: str, data: Dict[str, Any]) -> TaskGraph:
        """Parse a JSON dict into a TaskGraph."""
        graph = TaskGraph(goal=goal)

        for task_data in data.get("tasks", []):
            agent_str = task_data.get("agentType", task_data.get("agent_type", "refactor"))
            try:
                agent_type = AgentType(agent_str)
            except ValueError:
                agent_type = AgentType.REFACTOR

            task = SubTask(
                id=task_data.get("id", SubTask().id),
                agent_type=agent_type,
                description=task_data.get("description", ""),
                dependencies=task_data.get("dependencies", []),
                config=task_data.get("config", {}),
                priority=task_data.get("priority", 0),
            )
            graph.add_task(task)

        return graph
