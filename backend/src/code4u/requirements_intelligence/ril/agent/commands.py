"""Slack/Teams command handlers for RIL."""

from __future__ import annotations
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from .executor import ExecutionMode


class CommandType(str, Enum):
    """Command types."""
    CONVERT = "convert"
    STATUS = "status"
    LIST = "list"
    APPROVE = "approve"
    REJECT = "reject"
    HELP = "help"


@dataclass
class ParsedCommand:
    """A parsed command."""
    type: CommandType
    args: Dict[str, Any]
    raw: str


COMMAND_PATTERNS = {
    "convert": [
        r"convert\s+(?P<meeting_id>[\w-]+)\s+to\s+(?P<target>prd|plan|implementation)",
        r"generate\s+(?P<target>prd|plan)\s+from\s+(?P<meeting_id>[\w-]+)",
        r"create\s+(?P<target>prd|plan)\s+for\s+(?P<meeting_id>[\w-]+)",
    ],
    "status": [
        r"status\s+(?P<request_id>[\w-]+)",
        r"check\s+(?P<request_id>[\w-]+)",
    ],
    "list": [
        r"list\s+(?P<target>requirements|meetings|plans)",
        r"show\s+(?P<target>requirements|meetings|plans)",
    ],
    "approve": [
        r"approve\s+(?P<request_id>[\w-]+)",
        r"accept\s+(?P<request_id>[\w-]+)",
    ],
    "reject": [
        r"reject\s+(?P<request_id>[\w-]+)(?:\s+reason:\s*(?P<reason>.+))?",
        r"decline\s+(?P<request_id>[\w-]+)",
    ],
}


class CommandHandler:
    """
    Handles Slack/Teams commands for RIL.
    
    Example commands:
    - /code4u convert meeting-123 to implementation plan
    - /code4u status req-456
    - /code4u list requirements
    - /code4u approve exec-789
    - /code4u reject exec-789 reason: needs more detail
    """
    
    def __init__(
        self,
        executor=None,
        planner=None,
        graph_integration=None,
    ):
        """Initialize handler.
        
        Args:
            executor: RequirementExecutor instance
            planner: RequirementPlanner instance
            graph_integration: RequirementGraphIntegration instance
        """
        self.executor = executor
        self.planner = planner
        self.graph_integration = graph_integration
    
    def parse(self, command_text: str) -> Optional[ParsedCommand]:
        """Parse a command string.
        
        Args:
            command_text: Raw command text
            
        Returns:
            Parsed command or None
        """
        text = command_text.strip().lower()
        
        # Check for help
        if text in ["help", "?", "commands"]:
            return ParsedCommand(
                type=CommandType.HELP,
                args={},
                raw=command_text,
            )
        
        # Try each command pattern
        for cmd_type, patterns in COMMAND_PATTERNS.items():
            for pattern in patterns:
                match = re.match(pattern, text, re.IGNORECASE)
                if match:
                    return ParsedCommand(
                        type=CommandType(cmd_type),
                        args=match.groupdict(),
                        raw=command_text,
                    )
        
        return None
    
    async def handle(
        self,
        command_text: str,
        user_id: str,
        tenant_id: str,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle a command.
        
        Args:
            command_text: Command text
            user_id: User ID
            tenant_id: Tenant ID
            channel_id: Optional channel ID
            
        Returns:
            Response dictionary
        """
        parsed = self.parse(command_text)
        
        if not parsed:
            return {
                "success": False,
                "error": "Unknown command. Type 'help' for available commands.",
            }
        
        handler_map = {
            CommandType.CONVERT: self._handle_convert,
            CommandType.STATUS: self._handle_status,
            CommandType.LIST: self._handle_list,
            CommandType.APPROVE: self._handle_approve,
            CommandType.REJECT: self._handle_reject,
            CommandType.HELP: self._handle_help,
        }
        
        handler = handler_map.get(parsed.type)
        if handler:
            return await handler(parsed, user_id, tenant_id)
        
        return {"success": False, "error": "Handler not implemented"}
    
    async def _handle_convert(
        self,
        command: ParsedCommand,
        user_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Handle convert command."""
        meeting_id = command.args.get("meeting_id")
        target = command.args.get("target", "plan")
        
        if not meeting_id:
            return {"success": False, "error": "Meeting ID required"}
        
        # Map target to execution mode
        mode_map = {
            "prd": ExecutionMode.GENERATE_PRD,
            "plan": ExecutionMode.GENERATE_PLAN,
            "implementation": ExecutionMode.EXECUTE,
        }
        
        mode = mode_map.get(target, ExecutionMode.GENERATE_PLAN)
        
        if not self.executor:
            return {"success": False, "error": "Executor not configured"}
        
        # Get requirements from meeting
        if self.graph_integration:
            requirements = self.graph_integration.get_requirements_from_meeting(meeting_id)
            requirement_ids = [r.id for r in requirements]
        else:
            # Fallback - assume meeting_id is requirement_id
            requirement_ids = [meeting_id]
        
        if not requirement_ids:
            return {
                "success": False,
                "error": f"No requirements found for meeting {meeting_id}",
            }
        
        # Create execution request
        request = await self.executor.create_execution_request(
            requirement_ids=requirement_ids,
            mode=mode,
            created_by=user_id,
            tenant_id=tenant_id,
        )
        
        return {
            "success": True,
            "request_id": request.id,
            "status": request.status.value,
            "mode": mode.value,
            "requirements_count": len(requirement_ids),
            "message": self._get_convert_message(request, mode),
        }
    
    def _get_convert_message(self, request, mode: ExecutionMode) -> str:
        """Get message for convert response."""
        if mode == ExecutionMode.GENERATE_PRD:
            return f"PRD generated. Request ID: {request.id}"
        elif mode == ExecutionMode.GENERATE_PLAN:
            return f"Technical plan generated. Request ID: {request.id}"
        elif mode == ExecutionMode.EXECUTE:
            return f"Execution request created. Awaiting approval. Request ID: {request.id}"
        return f"Request created: {request.id}"
    
    async def _handle_status(
        self,
        command: ParsedCommand,
        user_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Handle status command."""
        request_id = command.args.get("request_id")
        
        if not request_id or not self.executor:
            return {"success": False, "error": "Request ID required"}
        
        request = self.executor.get_request(request_id)
        if not request:
            return {"success": False, "error": f"Request {request_id} not found"}
        
        result = {
            "success": True,
            "request_id": request.id,
            "status": request.status.value,
            "mode": request.mode.value,
            "requirements_count": len(request.requirement_ids),
            "created_at": request.created_at.isoformat(),
        }
        
        if request.error:
            result["error_message"] = request.error
        
        if request.result:
            result["result"] = request.result
        
        return result
    
    async def _handle_list(
        self,
        command: ParsedCommand,
        user_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Handle list command."""
        target = command.args.get("target", "requirements")
        
        if target == "requirements":
            if self.graph_integration:
                reqs = await self.graph_integration.search_requirements(
                    query="",  # All
                    tenant_id=tenant_id,
                    limit=10,
                )
                return {
                    "success": True,
                    "requirements": [
                        {"id": r.id, "title": r.title, "status": r.status}
                        for r in reqs
                    ],
                }
            return {"success": True, "requirements": []}
        
        elif target == "plans":
            if self.planner:
                plans = [
                    p.to_dict() for p in self.planner._plans.values()
                ]
                return {"success": True, "plans": plans}
            return {"success": True, "plans": []}
        
        elif target == "meetings":
            if self.graph_integration:
                meetings = list(self.graph_integration._meeting_nodes.values())
                return {
                    "success": True,
                    "meetings": [
                        {
                            "id": m.id,
                            "title": m.title,
                            "platform": m.platform,
                            "requirements_count": m.requirements_count,
                        }
                        for m in meetings
                    ],
                }
            return {"success": True, "meetings": []}
        
        return {"success": False, "error": f"Unknown target: {target}"}
    
    async def _handle_approve(
        self,
        command: ParsedCommand,
        user_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Handle approve command."""
        request_id = command.args.get("request_id")
        
        if not request_id or not self.executor:
            return {"success": False, "error": "Request ID required"}
        
        success = await self.executor.approve_execution(request_id, user_id)
        
        if success:
            return {
                "success": True,
                "message": f"Request {request_id} approved. Execution started.",
            }
        
        return {"success": False, "error": "Failed to approve request"}
    
    async def _handle_reject(
        self,
        command: ParsedCommand,
        user_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Handle reject command."""
        request_id = command.args.get("request_id")
        reason = command.args.get("reason", "No reason provided")
        
        if not request_id or not self.executor:
            return {"success": False, "error": "Request ID required"}
        
        success = await self.executor.reject_execution(request_id, reason)
        
        if success:
            return {
                "success": True,
                "message": f"Request {request_id} rejected.",
            }
        
        return {"success": False, "error": "Failed to reject request"}
    
    async def _handle_help(
        self,
        command: ParsedCommand,
        user_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Handle help command."""
        return {
            "success": True,
            "commands": [
                {
                    "command": "convert <meeting-id> to <prd|plan|implementation>",
                    "description": "Convert meeting requirements to a document or execution",
                    "examples": [
                        "convert meeting-123 to plan",
                        "convert meeting-123 to prd",
                        "convert meeting-123 to implementation",
                    ],
                },
                {
                    "command": "status <request-id>",
                    "description": "Check status of an execution request",
                    "examples": ["status exec-456"],
                },
                {
                    "command": "list <requirements|meetings|plans>",
                    "description": "List items",
                    "examples": ["list requirements", "list meetings"],
                },
                {
                    "command": "approve <request-id>",
                    "description": "Approve an execution request",
                    "examples": ["approve exec-789"],
                },
                {
                    "command": "reject <request-id> [reason: ...]",
                    "description": "Reject an execution request",
                    "examples": ["reject exec-789 reason: needs more detail"],
                },
            ],
        }

