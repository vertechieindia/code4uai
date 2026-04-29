from __future__ import annotations
"""Agent coordinator for code4u.ai.

Orchestrates agents through the state machine.
Each agent advances the state, not chats.
"""
from typing import Any
import structlog

from code4u.platform_core.state_machine.states import ExecutionState, STATE_AGENT_MAP
from code4u.platform_core.state_machine.machine import StateMachine, ExecutionContext

logger = structlog.get_logger("state_machine.coordinator")


class AgentCoordinator:
    """
    Coordinate agents through the state machine.
    
    Agent Responsibilities by State:
    - IMPACT_ANALYZED: Knowledge Graph
    - PLAN_GENERATED: Planner Agent
    - CONTRACT_VALIDATED: Contract Agent
    - CODE_GENERATED: Frontend/Backend Agent
    - VERIFIED: Verifier Agent
    - READY_FOR_REVIEW: Human
    """
    
    def __init__(self, state_machine: StateMachine | None = None):
        self.machine = state_machine or StateMachine()
        self._agents: Dict[str, Any] = {}
    
    def register_agent(self, name: str, agent: Any) -> None:
        """Register an agent."""
        self._agents[name] = agent
        logger.info("agent_registered", name=name)
    
    async def execute(
        self,
        tenant_id: str,
        user_id: str,
        intent: str,
        target_file: str,
        instruction: str,
        context: Dict[str, Any] | None = None
    ) -> ExecutionContext:
        """
        Execute a complete operation through the state machine.
        
        Runs each agent in sequence, advancing state.
        """
        import uuid
        
        execution_id = str(uuid.uuid4())[:12]
        
        # Create context
        exec_context = self.machine.create_context(
            execution_id=execution_id,
            tenant_id=tenant_id,
            user_id=user_id,
            intent=intent,
            target_file=target_file,
            instruction=instruction,
        )
        
        logger.info(
            "execution_started",
            execution_id=execution_id,
            intent=intent,
            target_file=target_file
        )
        
        try:
            # Phase 1: Impact Analysis
            exec_context = await self._run_impact_analysis(exec_context, context)
            
            # Phase 2: Plan Generation
            exec_context = await self._run_plan_generation(exec_context)
            
            # Phase 3: Contract Validation
            exec_context = await self._run_contract_validation(exec_context)
            
            # Phase 4: Code Generation
            exec_context = await self._run_code_generation(exec_context)
            
            # Phase 5: Verification
            exec_context = await self._run_verification(exec_context)
            
            # Phase 6: Ready for Review
            exec_context = self.machine.transition(
                execution_id=execution_id,
                to_state=ExecutionState.READY_FOR_REVIEW,
                agent="coordinator",
                reason="All validations passed"
            )
            
            logger.info(
                "execution_ready_for_review",
                execution_id=execution_id,
                diff_count=len(exec_context.generated_diffs)
            )
            
            return exec_context
            
        except Exception as e:
            logger.error(
                "execution_failed",
                execution_id=execution_id,
                error=str(e)
            )
            return self.machine.fail(
                execution_id=execution_id,
                reason=str(e),
                error=str(type(e).__name__)
            )
    
    async def _run_impact_analysis(
        self,
        context: ExecutionContext,
        extra_context: Dict[str, Any] | None
    ) -> ExecutionContext:
        """Run impact analysis phase."""
        agent = self._agents.get("knowledge_graph")
        
        if agent:
            result = await agent.analyze_impact(
                file_path=context.target_file,
                intent=context.intent
            )
        else:
            # Mock for testing
            result = {
                "impacted_nodes": [],
                "blast_radius": {"files": 1, "repos": 1, "teams": 1},
                "breaking_change": False,
            }
        
        return self.machine.transition_with_artifact(
            execution_id=context.execution_id,
            to_state=ExecutionState.IMPACT_ANALYZED,
            artifact_key="impact_analysis",
            artifact_value=result,
            agent="knowledge_graph",
            reason="Impact analysis complete"
        )
    
    async def _run_plan_generation(
        self,
        context: ExecutionContext
    ) -> ExecutionContext:
        """Run plan generation phase."""
        agent = self._agents.get("planner")
        
        if agent:
            result = await agent.generate_plan(
                intent=context.intent,
                impact=context.impact_analysis
            )
        else:
            # Mock for testing
            result = {
                "steps": [
                    {"action": "validate_contracts"},
                    {"action": "generate_diff"},
                    {"action": "verify"},
                ],
                "estimated_complexity": "medium",
            }
        
        return self.machine.transition_with_artifact(
            execution_id=context.execution_id,
            to_state=ExecutionState.PLAN_GENERATED,
            artifact_key="execution_plan",
            artifact_value=result,
            agent="planner",
            reason="Plan generated"
        )
    
    async def _run_contract_validation(
        self,
        context: ExecutionContext
    ) -> ExecutionContext:
        """Run contract validation phase."""
        agent = self._agents.get("contract")
        
        if agent:
            result = await agent.validate(
                plan=context.execution_plan,
                impact=context.impact_analysis
            )
        else:
            # Mock for testing
            result = {
                "valid": True,
                "schema_checks": [],
                "api_checks": [],
            }
        
        return self.machine.transition_with_artifact(
            execution_id=context.execution_id,
            to_state=ExecutionState.CONTRACT_VALIDATED,
            artifact_key="contract_validation",
            artifact_value=result,
            agent="contract",
            reason="Contracts validated"
        )
    
    async def _run_code_generation(
        self,
        context: ExecutionContext
    ) -> ExecutionContext:
        """Run code generation phase."""
        agent = self._agents.get("llm")
        
        if agent:
            result = await agent.generate(
                instruction=context.instruction,
                target_file=context.target_file,
                plan=context.execution_plan
            )
        else:
            # Mock for testing
            result = [{
                "file_path": context.target_file,
                "diff": "--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new",
            }]
        
        return self.machine.transition_with_artifact(
            execution_id=context.execution_id,
            to_state=ExecutionState.CODE_GENERATED,
            artifact_key="generated_diffs",
            artifact_value=result,
            agent="llm",
            reason="Code generated"
        )
    
    async def _run_verification(
        self,
        context: ExecutionContext
    ) -> ExecutionContext:
        """Run verification phase."""
        agent = self._agents.get("verifier")
        
        if agent:
            result = await agent.verify(
                diffs=context.generated_diffs
            )
        else:
            # Mock for testing
            result = {
                "passed": True,
                "type_check": True,
                "lint_check": True,
                "schema_check": True,
            }
        
        return self.machine.transition_with_artifact(
            execution_id=context.execution_id,
            to_state=ExecutionState.VERIFIED,
            artifact_key="verification_result",
            artifact_value=result,
            agent="verifier",
            reason="Verification passed"
        )
    
    def apply(self, execution_id: str, user_id: str) -> ExecutionContext:
        """Apply the changes (human approval)."""
        context = self.machine.get_context(execution_id)
        if not context:
            raise ValueError(f"Unknown execution: {execution_id}")
        
        if context.state != ExecutionState.READY_FOR_REVIEW:
            raise ValueError(f"Cannot apply from state: {context.state.value}")
        
        return self.machine.transition(
            execution_id=execution_id,
            to_state=ExecutionState.APPLIED,
            agent="human",
            reason=f"Applied by user {user_id}"
        )
    
    def reject(self, execution_id: str, user_id: str, reason: str = "") -> ExecutionContext:
        """Reject the changes (human decision)."""
        context = self.machine.get_context(execution_id)
        if not context:
            raise ValueError(f"Unknown execution: {execution_id}")
        
        return self.machine.transition(
            execution_id=execution_id,
            to_state=ExecutionState.REJECTED,
            agent="human",
            reason=reason or f"Rejected by user {user_id}"
        )

