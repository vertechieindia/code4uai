"""Freshservice integration for ITSM."""

from __future__ import annotations
import os
import base64
from typing import Optional, List, Dict, Any
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@register_integration("freshservice")
class FreshserviceIntegration(TaskIntegration):
    """Freshservice Integration for code4u.ai."""
    
    name = "freshservice"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.domain = os.getenv("FRESHSERVICE_DOMAIN", "")
        self.api_key = os.getenv("FRESHSERVICE_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        auth = base64.b64encode(f"{self.api_key}:X".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=f"https://{self.domain}.freshservice.com/api/v2",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/agents/me")
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        response = await self._client.get(f"/tickets/{task_id}")
        response.raise_for_status()
        return response.json().get("ticket", {})
    
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        data = {"subject": title, "description": description, "email": kwargs.get("email", ""), **kwargs}
        response = await self._client.post("/tickets", json=data)
        response.raise_for_status()
        return response.json().get("ticket", {})
    
    async def update_task(self, task_id: str, **updates) -> Dict[str, Any]:
        response = await self._client.put(f"/tickets/{task_id}", json=updates)
        response.raise_for_status()
        return response.json().get("ticket", {})
    
    async def add_comment(self, task_id: str, comment: str) -> Dict[str, Any]:
        data = {"body": comment, "private": True}
        response = await self._client.post(f"/tickets/{task_id}/notes", json=data)
        response.raise_for_status()
        return response.json()
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        import uuid
        priority_map = {1: "low", 2: "medium", 3: "high", 4: "critical"}
        return Requirement(
            id=str(uuid.uuid4()),
            title=task.get("subject", ""),
            description=task.get("description_text", ""),
            source_type="freshservice",
            source_id=str(task.get("id", "")),
            type="bug" if task.get("type") == "Incident" else "task",
            priority=priority_map.get(task.get("priority", 2), "medium"),
        )

