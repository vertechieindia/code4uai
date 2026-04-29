"""AbstractAgent — base contract for all code4u specialist agents.

Every agent in the swarm (built-in or plugin) must implement this
interface.  The ``SwarmController`` dispatches ``SubTask`` objects
to agents based on their ``agent_type``.

Plugin authors create a subclass, implement ``run()``, and drop
the ``.py`` file into ``~/.code4u/plugins/``.  The dynamic loader
discovers and registers it automatically.

Usage (plugin example)::

    from code4u.agents.base import AbstractAgent, AgentManifest
    from code4u.agents.orchestrator.models import SubTask, HandoffPayload, AgentType

    class SecurityAuditAgent(AbstractAgent):
        manifest = AgentManifest(
            name="security_audit",
            agent_type=AgentType.JURY,
            version="1.0.0",
            description="Deep security audit using custom OWASP rules.",
            icon="🛡️",
            capabilities=["security", "owasp", "audit"],
        )

        def run(self, task, handoffs):
            # ... custom logic ...
            return HandoffPayload(task.id, self.manifest.agent_type, {"verdict": "PASS"})
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from code4u.agents.orchestrator.models import (
    AgentType,
    HandoffPayload,
    SubTask,
)


# ---------------------------------------------------------------------------
# Agent manifest (metadata describing the plugin)
# ---------------------------------------------------------------------------

@dataclass
class AgentManifest:
    """Metadata describing a specialist agent."""
    name: str
    agent_type: AgentType = AgentType.REFACTOR
    version: str = "0.1.0"
    description: str = ""
    icon: str = "⚙️"
    capabilities: List[str] = field(default_factory=list)
    author: str = ""
    priority: int = 0  # higher = preferred over defaults with same agent_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "agentType": self.agent_type.value,
            "version": self.version,
            "description": self.description,
            "icon": self.icon,
            "capabilities": self.capabilities,
            "author": self.author,
            "priority": self.priority,
        }


# ---------------------------------------------------------------------------
# AbstractAgent
# ---------------------------------------------------------------------------

class AbstractAgent(abc.ABC):
    """Base class for all code4u specialist agents.

    Subclasses must:
      1. Set ``manifest`` — an ``AgentManifest`` describing the agent.
      2. Implement ``run(task, handoffs)`` — the execution logic.
    """

    manifest: AgentManifest

    @abc.abstractmethod
    def run(
        self,
        task: SubTask,
        handoffs: List[HandoffPayload],
    ) -> HandoffPayload:
        """Execute the agent's work on a sub-task.

        Args:
            task: The sub-task assigned by the SwarmController.
            handoffs: Outputs from upstream dependencies.

        Returns:
            A ``HandoffPayload`` with the agent's output data.
        """
        ...

    def can_handle(self, task: SubTask) -> bool:
        """Check if this agent can handle the given task.

        Override for custom routing logic beyond ``agent_type`` matching.
        """
        return task.agent_type == self.manifest.agent_type

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def agent_type(self) -> AgentType:
        return self.manifest.agent_type

    def to_dict(self) -> Dict[str, Any]:
        return self.manifest.to_dict()
