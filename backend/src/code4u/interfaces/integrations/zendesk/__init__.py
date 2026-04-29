"""Zendesk integration for customer service."""

from __future__ import annotations
import os
import base64
from typing import Optional, List, Dict, Any
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@register_integration("zendesk")
class ZendeskIntegration(TaskIntegration):
    """Zendesk Integration for code4u.ai."""
    
    name = "zendesk"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.subdomain = os.getenv("ZENDESK_SUBDOMAIN", "")
        self.email = os.getenv("ZENDESK_EMAIL", "")
        self.api_token = os.getenv("ZENDESK_API_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        auth = base64.b64encode(f"{self.email}/token:{self.api_token}".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=f"https://{self.subdomain}.zendesk.com/api/v2",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/users/me")
            return {"status": "healthy", "user": response.json().get("user", {}).get("name")}
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
        data = {"ticket": {"subject": title, "description": description, **kwargs}}
        response = await self._client.post("/tickets", json=data)
        response.raise_for_status()
        return response.json().get("ticket", {})
    
    async def update_task(self, task_id: str, **updates) -> Dict[str, Any]:
        data = {"ticket": updates}
        response = await self._client.put(f"/tickets/{task_id}", json=data)
        response.raise_for_status()
        return response.json().get("ticket", {})
    
    async def add_comment(self, task_id: str, comment: str) -> Dict[str, Any]:
        data = {"ticket": {"comment": {"body": comment, "public": False}}}
        response = await self._client.put(f"/tickets/{task_id}", json=data)
        response.raise_for_status()
        return response.json()
    
    async def search_tickets(self, query: str) -> List[Dict[str, Any]]:
        response = await self._client.get(f"/search?query={query}")
        response.raise_for_status()
        return response.json().get("results", [])
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        import uuid
        priority_map = {"urgent": "critical", "high": "high", "normal": "medium", "low": "low"}
        return Requirement(
            id=str(uuid.uuid4()),
            title=task.get("subject", ""),
            description=task.get("description", ""),
            source_type="zendesk",
            source_id=str(task.get("id", "")),
            source_url=f"https://{self.subdomain}.zendesk.com/agent/tickets/{task.get('id')}",
            type="bug" if task.get("type") == "incident" else "task",
            priority=priority_map.get(task.get("priority", "normal"), "medium"),
        )

