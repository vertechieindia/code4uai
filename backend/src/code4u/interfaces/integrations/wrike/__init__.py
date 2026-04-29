"""Wrike integration for project management."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@register_integration("wrike")
class WrikeIntegration(TaskIntegration):
    """Wrike Integration for code4u.ai."""
    
    name = "wrike"
    BASE_URL = "https://www.wrike.com/api/v4"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.access_token = os.getenv("WRIKE_ACCESS_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/contacts?me=true")
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        response = await self._client.get(f"/tasks/{task_id}")
        response.raise_for_status()
        data = response.json().get("data", [])
        return data[0] if data else {}
    
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        data = {"title": title, "description": description, **kwargs}
        response = await self._client.post(f"/folders/{project_id}/tasks", json=data)
        response.raise_for_status()
        return response.json().get("data", [{}])[0]
    
    async def update_task(self, task_id: str, **updates) -> Dict[str, Any]:
        response = await self._client.put(f"/tasks/{task_id}", json=updates)
        response.raise_for_status()
        return response.json().get("data", [{}])[0]
    
    async def add_comment(self, task_id: str, comment: str) -> Dict[str, Any]:
        data = {"text": comment}
        response = await self._client.post(f"/tasks/{task_id}/comments", json=data)
        response.raise_for_status()
        return response.json().get("data", [{}])[0]
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        import uuid
        importance_map = {"High": "high", "Normal": "medium", "Low": "low"}
        return Requirement(
            id=str(uuid.uuid4()),
            title=task.get("title", ""),
            description=task.get("description", ""),
            source_type="wrike",
            source_id=task.get("id", ""),
            source_url=task.get("permalink", ""),
            type="task",
            priority=importance_map.get(task.get("importance", "Normal"), "medium"),
        )

