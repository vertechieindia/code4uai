"""
Agent Integration Layer

Controlled execution from requirements.

Modes:
1. Listen-only (default) - Capture and structure only
2. Generate PRD - Create product requirement document
3. Generate Technical Plan - Create implementation plan
4. Execute (explicit approval) - Trigger agent execution

Example Slack command:
  /code4u convert meeting-123 to implementation plan

Agent then:
1. Reads requirement nodes
2. Maps to services
3. Produces a plan artifact
4. Requests approval
"""

from .executor import RequirementExecutor
from .planner import RequirementPlanner
from .commands import CommandHandler

__all__ = [
    "RequirementExecutor",
    "RequirementPlanner",
    "CommandHandler",
]

