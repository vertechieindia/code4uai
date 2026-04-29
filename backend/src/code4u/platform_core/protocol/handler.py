from __future__ import annotations
"""Protocol handler for IDE ↔ Backend communication.

Processes messages and coordinates with the state machine.
"""
from typing import Any, AsyncGenerator
import structlog

from code4u.platform_core.protocol.messages import (
    IntentRequest,
    ExecutionUpdate,
    DiffPayload,
    DiffItem,
    ValidationResult,
    ImpactedComponent,
    ApplyRequest,
    RejectRequest,
    ErrorResponse,
)
from code4u.platform_core.state_machine import (
    StateMachine,
    ExecutionContext,
    AgentCoordinator,
    ExecutionState,
)
from code4u.ai_engine.routing import RoutingEngine

logger = structlog.get_logger("protocol.handler")


class ProtocolHandler:
    """
    Handle IDE protocol messages.
    
    IDE Safeguards:
    - Diff preview mandatory
    - Ownership warnings inline
    - Breaking-change badges
    - One-click rollback
    
    The IDE never executes anything automatically.
    """
    
    def __init__(
        self,
        coordinator: AgentCoordinator | None = None,
        routing_engine: RoutingEngine | None = None
    ):
        self.coordinator = coordinator or AgentCoordinator()
        self.routing = routing_engine or RoutingEngine()
    
    async def handle_intent(
        self,
        request: IntentRequest
    ) -> AsyncGenerator[ExecutionUpdate | DiffPayload | ErrorResponse, None]:
        """
        Handle an intent request.
        
        Yields streaming updates as execution progresses.
        """
        logger.info(
            "intent_received",
            intent=request.intent,
            file=request.cursor.file,
            workspace=request.workspace_id
        )
        
        try:
            # Start execution
            context = await self.coordinator.execute(
                tenant_id=request.workspace_id,
                user_id=request.user_id,
                intent=request.intent,
                target_file=request.cursor.file,
                instruction=request.instruction or request.selection,
            )
            
            # Yield state updates
            for transition in context.transitions:
                yield ExecutionUpdate(
                    execution_id=context.execution_id,
                    state=transition.to_state.value,
                    summary=transition.reason,
                    phase=transition.agent,
                    progress=self._calculate_progress(transition.to_state),
                )
            
            # If ready for review, yield diff payload
            if context.state == ExecutionState.READY_FOR_REVIEW:
                yield self._build_diff_payload(context)
            
            # If failed, yield error
            elif context.state == ExecutionState.FAILED:
                yield ErrorResponse(
                    execution_id=context.execution_id,
                    error=context.transitions[-1].reason if context.transitions else "Unknown error",
                    error_code="EXECUTION_FAILED",
                    recoverable=False,
                )
        
        except Exception as e:
            logger.error("intent_handler_error", error=str(e))
            yield ErrorResponse(
                error=str(e),
                error_code="HANDLER_ERROR",
                recoverable=False,
            )
    
    async def handle_apply(self, request: ApplyRequest) -> ExecutionUpdate | ErrorResponse:
        """Handle apply request from IDE."""
        try:
            context = self.coordinator.apply(
                execution_id=request.execution_id,
                user_id=request.user_id
            )
            
            logger.info(
                "changes_applied",
                execution_id=request.execution_id,
                user_id=request.user_id
            )
            
            return ExecutionUpdate(
                execution_id=context.execution_id,
                state=context.state.value,
                summary="Changes applied successfully",
                progress=100,
            )
        
        except Exception as e:
            logger.error("apply_error", error=str(e))
            return ErrorResponse(
                execution_id=request.execution_id,
                error=str(e),
                error_code="APPLY_FAILED",
            )
    
    async def handle_reject(self, request: RejectRequest) -> ExecutionUpdate | ErrorResponse:
        """Handle reject request from IDE."""
        try:
            context = self.coordinator.reject(
                execution_id=request.execution_id,
                user_id=request.user_id,
                reason=request.reason
            )
            
            logger.info(
                "changes_rejected",
                execution_id=request.execution_id,
                user_id=request.user_id,
                reason=request.reason
            )
            
            return ExecutionUpdate(
                execution_id=context.execution_id,
                state=context.state.value,
                summary=f"Changes rejected: {request.reason}",
                progress=100,
            )
        
        except Exception as e:
            logger.error("reject_error", error=str(e))
            return ErrorResponse(
                execution_id=request.execution_id,
                error=str(e),
                error_code="REJECT_FAILED",
            )
    
    def _calculate_progress(self, state: ExecutionState) -> int:
        """Calculate progress percentage from state."""
        progress_map = {
            ExecutionState.INIT: 0,
            ExecutionState.IMPACT_ANALYZED: 20,
            ExecutionState.PLAN_GENERATED: 35,
            ExecutionState.CONTRACT_VALIDATED: 50,
            ExecutionState.CODE_GENERATED: 70,
            ExecutionState.VERIFIED: 85,
            ExecutionState.READY_FOR_REVIEW: 95,
            ExecutionState.APPLIED: 100,
            ExecutionState.REJECTED: 100,
            ExecutionState.FAILED: 100,
            ExecutionState.CANCELLED: 100,
        }
        return progress_map.get(state, 0)
    
    def _build_diff_payload(self, context: ExecutionContext) -> DiffPayload:
        """Build diff payload from execution context."""
        diffs = []
        breaking_changes = []
        ownership_warnings = []
        
        total_added = 0
        total_removed = 0
        
        for i, diff_data in enumerate(context.generated_diffs):
            diff_content = diff_data.get("diff", "")
            file_path = diff_data.get("file_path", f"file_{i}")
            
            # Parse diff for stats
            lines_added = diff_content.count("\n+") - 1  # Exclude header
            lines_removed = diff_content.count("\n-") - 1
            
            total_added += max(0, lines_added)
            total_removed += max(0, lines_removed)
            
            diff_item = DiffItem(
                diff_id=f"diff_{i}",
                file_path=file_path,
                diff_content=diff_content,
                language=self._detect_language(file_path),
                lines_added=max(0, lines_added),
                lines_removed=max(0, lines_removed),
                is_breaking=diff_data.get("breaking", False),
                owner=diff_data.get("owner"),
            )
            diffs.append(diff_item)
            
            if diff_item.is_breaking:
                breaking_changes.append(f"Breaking change in {file_path}")
            
            if diff_item.owner:
                ownership_warnings.append(f"{file_path} owned by {diff_item.owner}")
        
        # Build validation result
        verification = context.verification_result or {}
        validation = ValidationResult(
            types="pass" if verification.get("type_check", True) else "fail",
            schemas="pass" if verification.get("schema_check", True) else "fail",
            tests="skipped",  # Tests not run by default
        )
        
        return DiffPayload(
            execution_id=context.execution_id,
            state="READY_FOR_REVIEW",
            diffs=diffs,
            validation=validation,
            summary=f"Generated {len(diffs)} diff(s) for review",
            total_files=len(diffs),
            total_lines_added=total_added,
            total_lines_removed=total_removed,
            breaking_changes=breaking_changes,
            ownership_warnings=ownership_warnings,
        )
    
    def _detect_language(self, file_path: str) -> str:
        """Detect language from file path."""
        ext_map = {
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".py": "python",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
        }
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return "plaintext"

