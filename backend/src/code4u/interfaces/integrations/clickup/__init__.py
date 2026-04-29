"""ClickUp integration for project management."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@register_integration("clickup")
class ClickUpIntegration(TaskIntegration):
    """ClickUp Integration for code4u.ai."""
    
    name = "clickup"
    BASE_URL = "https://api.clickup.com/api/v2"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.config = config or IntegrationConfig(
            api_key=os.getenv("CLICKUP_API_KEY", ""),
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": self.config.api_key},
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/user")
            return {"status": "healthy", "user": response.json().get("user", {}).get("username")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        response = await self._client.get(f"/task/{task_id}")
        response.raise_for_status()
        return response.json()
    
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,  # list_id in ClickUp
        **kwargs,
    ) -> Dict[str, Any]:
        data = {"name": title, "description": description, **kwargs}
        response = await self._client.post(f"/list/{project_id}/task", json=data)
        response.raise_for_status()
        return response.json()
    
    async def update_task(self, task_id: str, **updates) -> Dict[str, Any]:
        response = await self._client.put(f"/task/{task_id}", json=updates)
        response.raise_for_status()
        return response.json()
    
    async def add_comment(self, task_id: str, comment: str) -> Dict[str, Any]:
        data = {"comment_text": comment}
        response = await self._client.post(f"/task/{task_id}/comment", json=data)
        response.raise_for_status()
        return response.json()
    
    async def get_workspaces(self) -> List[Dict[str, Any]]:
        response = await self._client.get("/team")
        response.raise_for_status()
        return response.json().get("teams", [])
    
    async def get_tasks_from_list(self, list_id: str) -> List[Dict[str, Any]]:
        response = await self._client.get(f"/list/{list_id}/task")
        response.raise_for_status()
        return response.json().get("tasks", [])
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        import uuid
        priority_map = {1: "critical", 2: "high", 3: "medium", 4: "low"}
        return Requirement(
            id=str(uuid.uuid4()),
            title=task.get("name", ""),
            description=task.get("description", ""),
            source_type="clickup",
            source_id=task.get("id", ""),
            source_url=task.get("url", ""),
            type="task",
            priority=priority_map.get(task.get("priority", {}).get("id", 3), "medium"),
        )

