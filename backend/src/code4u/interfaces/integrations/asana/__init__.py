"""Asana integration for project management."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@register_integration("asana")
class AsanaIntegration(TaskIntegration):
    """
    Asana Integration for code4u.ai.
    
    Features:
    - Watch projects and tasks
    - Create tasks from requirements
    - Update task status
    - Add comments with implementation details
    """
    
    name = "asana"
    BASE_URL = "https://app.asana.com/api/1.0"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        """Initialize Asana integration."""
        super().__init__(config)
        self.config = config or IntegrationConfig(
            api_key=os.getenv("ASANA_API_KEY", ""),
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        """Connect to Asana."""
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Accept": "application/json",
            },
        )
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from Asana."""
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Asana connection."""
        try:
            response = await self._client.get("/users/me")
            user = response.json().get("data", {})
            return {"status": "healthy", "user": user.get("name")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get a task from Asana."""
        response = await self._client.get(f"/tasks/{task_id}")
        response.raise_for_status()
        return response.json().get("data", {})
    
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a task in Asana."""
        data = {
            "data": {
                "name": title,
                "notes": description,
                "projects": [project_id] if project_id else [],
                **kwargs,
            }
        }
        
        response = await self._client.post("/tasks", json=data)
        response.raise_for_status()
        return response.json().get("data", {})
    
    async def update_task(self, task_id: str, **updates) -> Dict[str, Any]:
        """Update a task in Asana."""
        data = {"data": updates}
        response = await self._client.put(f"/tasks/{task_id}", json=data)
        response.raise_for_status()
        return response.json().get("data", {})
    
    async def add_comment(self, task_id: str, comment: str) -> Dict[str, Any]:
        """Add a comment to a task."""
        data = {"data": {"text": comment}}
        response = await self._client.post(f"/tasks/{task_id}/stories", json=data)
        response.raise_for_status()
        return response.json().get("data", {})
    
    async def get_projects(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get projects in a workspace."""
        response = await self._client.get(f"/workspaces/{workspace_id}/projects")
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def get_tasks_from_project(
        self,
        project_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get tasks from a project."""
        params = {"limit": limit, "opt_fields": "name,notes,completed,due_on,assignee"}
        response = await self._client.get(f"/projects/{project_id}/tasks", params=params)
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        """Convert Asana task to Requirement."""
        import uuid
        return Requirement(
            id=str(uuid.uuid4()),
            title=task.get("name", ""),
            description=task.get("notes", ""),
            source_type="asana",
            source_id=task.get("gid", ""),
            source_url=f"https://app.asana.com/0/0/{task.get('gid')}",
            type="task",
            priority="medium",
            assignee=task.get("assignee", {}).get("name") if task.get("assignee") else None,
        )

