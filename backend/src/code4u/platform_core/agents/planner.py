from __future__ import annotations
"""Planner agent for code4u.ai. Builds execution plan from compiled context."""
from code4u.platform_core.agents.base import Agent, AgentContext, AgentResult, AgentStatus


class PlannerAgent(Agent):
    name = "planner"

    async def execute(self, context: AgentContext) -> AgentResult:
        self.logger.info("creating_execution_plan", intent=context.intent)
        compiled = context.scope.get("compiled_context")
        if not compiled:
            plan = {
                "steps": [
                    {"agent": "planner", "action": "analyze"},
                    {"agent": "verifier", "action": "run_validations"},
                ],
                "blast_radius": {"repositories": 0, "packages": 0, "teams": 0},
                "breaking_change": False,
            }
            return AgentResult(
                status=AgentStatus.SUCCESS,
                output={"plan": plan, "estimated_impact": "unknown"},
            )

        steps = [
            {"agent": "planner", "action": "analyze", "task_type": compiled.task_type},
            {"agent": "verifier", "action": "run_validations"},
        ]
        num_repos = len(compiled.affected_repositories)
        num_teams = len(compiled.owner_teams)
        num_components = len(compiled.affected_components)
        blast_radius = {
            "repositories": num_repos,
            "packages": num_components,
            "teams": num_teams,
        }
        plan = {
            "steps": steps,
            "blast_radius": blast_radius,
            "breaking_change": compiled.breaking_change,
        }
        if num_teams > 1 or num_repos > 1 or compiled.breaking_change:
            estimated_impact = "high"
        elif num_components > 5 or num_teams > 0:
            estimated_impact = "medium"
        else:
            estimated_impact = "low"
        return AgentResult(
            status=AgentStatus.SUCCESS,
            output={"plan": plan, "estimated_impact": estimated_impact},
        )
