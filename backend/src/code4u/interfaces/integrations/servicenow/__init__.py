"""ServiceNow integration for ITSM."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@dataclass
class ServiceNowConfig(IntegrationConfig):
    """ServiceNow configuration."""
    instance_url: str = ""
    username: str = ""
    password: str = ""
    
    # Tables to watch
    watch_tables: List[str] = None
    
    # Auto-trigger on these states
    trigger_states: List[str] = None
    
    def __post_init__(self):
        self.watch_tables = self.watch_tables or ["incident", "sc_req_item", "change_request"]
        self.trigger_states = self.trigger_states or ["New", "Assigned"]


@register_integration("servicenow")
class ServiceNowIntegration(TaskIntegration):
    """
    ServiceNow Integration for code4u.ai.
    
    Supports:
    - Incidents
    - Service Requests
    - Change Requests
    - Problem Management
    - Knowledge Base
    
    Features:
    - Watch for new tickets
    - Extract requirements from descriptions
    - Auto-create implementation plans
    - Update ticket status as work progresses
    - Link commits and PRs
    """
    
    name = "servicenow"
    
    def __init__(self, config: Optional[ServiceNowConfig] = None):
        """Initialize ServiceNow integration."""
        super().__init__(config)
        self.config = config or ServiceNowConfig(
            instance_url=os.getenv("SERVICENOW_INSTANCE_URL", ""),
            username=os.getenv("SERVICENOW_USERNAME", ""),
            password=os.getenv("SERVICENOW_PASSWORD", ""),
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        """Connect to ServiceNow."""
        self._client = httpx.AsyncClient(
            base_url=f"{self.config.instance_url}/api/now",
            auth=(self.config.username, self.config.password),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from ServiceNow."""
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check ServiceNow connection."""
        try:
            response = await self._client.get("/table/sys_user?sysparm_limit=1")
            return {"status": "healthy", "instance": self.config.instance_url}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_task(self, task_id: str, table: str = "incident") -> Dict[str, Any]:
        """Get a task from ServiceNow.
        
        Args:
            task_id: Task sys_id or number
            table: Table name
            
        Returns:
            Task data
        """
        response = await self._client.get(f"/table/{table}/{task_id}")
        response.raise_for_status()
        return response.json().get("result", {})
    
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,
        table: str = "incident",
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a task in ServiceNow."""
        data = {
            "short_description": title,
            "description": description,
            **kwargs,
        }
        
        response = await self._client.post(f"/table/{table}", json=data)
        response.raise_for_status()
        return response.json().get("result", {})
    
    async def update_task(
        self,
        task_id: str,
        table: str = "incident",
        **updates,
    ) -> Dict[str, Any]:
        """Update a task in ServiceNow."""
        response = await self._client.patch(f"/table/{table}/{task_id}", json=updates)
        response.raise_for_status()
        return response.json().get("result", {})
    
    async def add_comment(
        self,
        task_id: str,
        comment: str,
        table: str = "incident",
    ) -> Dict[str, Any]:
        """Add work notes to a task."""
        return await self.update_task(task_id, table, work_notes=comment)
    
    async def search_tasks(
        self,
        query: str,
        table: str = "incident",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search for tasks."""
        params = {
            "sysparm_query": query,
            "sysparm_limit": limit,
        }
        response = await self._client.get(f"/table/{table}", params=params)
        response.raise_for_status()
        return response.json().get("result", [])
    
    async def get_new_tasks(
        self,
        table: str = "incident",
    ) -> List[Dict[str, Any]]:
        """Get new tasks that need processing."""
        states = ",".join(self.config.trigger_states)
        query = f"stateIN{states}^assigned_toISEMPTY"
        return await self.search_tasks(query, table)
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        """Convert ServiceNow task to Requirement."""
        import uuid
        
        priority_map = {
            "1": "critical",
            "2": "high",
            "3": "medium",
            "4": "low",
            "5": "low",
        }
        
        return Requirement(
            id=str(uuid.uuid4()),
            title=task.get("short_description", ""),
            description=task.get("description", ""),
            source_type="servicenow",
            source_id=task.get("sys_id", ""),
            source_url=f"{self.config.instance_url}/nav_to.do?uri=incident.do?sys_id={task.get('sys_id')}",
            type="bug" if "incident" in task.get("sys_class_name", "") else "task",
            priority=priority_map.get(str(task.get("priority", "3")), "medium"),
        )
    
    async def link_implementation(
        self,
        task_id: str,
        pr_url: str,
        commit_hash: str,
        table: str = "incident",
    ) -> None:
        """Link PR and commit to a ServiceNow task."""
        comment = f"[code4u.ai] Implementation completed.\n\nPR: {pr_url}\nCommit: {commit_hash}"
        await self.add_comment(task_id, comment, table)
    
    async def mark_resolved(
        self,
        task_id: str,
        resolution_notes: str,
        table: str = "incident",
    ) -> Dict[str, Any]:
        """Mark a task as resolved."""
        return await self.update_task(
            task_id,
            table,
            state="6",  # Resolved
            close_notes=resolution_notes,
        )

