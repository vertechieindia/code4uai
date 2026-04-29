"""Basecamp integration for project management."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@register_integration("basecamp")
class BasecampIntegration(TaskIntegration):
    """Basecamp Integration for code4u.ai."""
    
    name = "basecamp"
    BASE_URL = "https://3.basecampapi.com"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.account_id = os.getenv("BASECAMP_ACCOUNT_ID", "")
        self.access_token = os.getenv("BASECAMP_ACCESS_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            base_url=f"{self.BASE_URL}/{self.account_id}",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/projects.json")
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        # Basecamp requires project_id and todolist_id
        return {}
    
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,
        todolist_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        data = {"content": title, "description": description, **kwargs}
        response = await self._client.post(
            f"/buckets/{project_id}/todolists/{todolist_id}/todos.json",
            json=data,
        )
        response.raise_for_status()
        return response.json()
    
    async def update_task(self, task_id: str, **updates) -> Dict[str, Any]:
        return {}
    
    async def add_comment(self, task_id: str, comment: str) -> Dict[str, Any]:
        return {}
    
    async def get_projects(self) -> List[Dict[str, Any]]:
        response = await self._client.get("/projects.json")
        response.raise_for_status()
        return response.json()
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        import uuid
        return Requirement(
            id=str(uuid.uuid4()),
            title=task.get("content", ""),
            description=task.get("description", ""),
            source_type="basecamp",
            source_id=str(task.get("id", "")),
            type="task",
            priority="medium",
        )

