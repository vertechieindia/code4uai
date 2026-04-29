"""Trello integration for project management."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@register_integration("trello")
class TrelloIntegration(TaskIntegration):
    """Trello Integration for code4u.ai."""
    
    name = "trello"
    BASE_URL = "https://api.trello.com/1"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.config = config or IntegrationConfig()
        self.api_key = os.getenv("TRELLO_API_KEY", "")
        self.token = os.getenv("TRELLO_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(base_url=self.BASE_URL)
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get(f"/members/me?key={self.api_key}&token={self.token}")
            return {"status": "healthy", "user": response.json().get("fullName")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        response = await self._client.get(f"/cards/{task_id}?key={self.api_key}&token={self.token}")
        response.raise_for_status()
        return response.json()
    
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,  # list_id in Trello
        **kwargs,
    ) -> Dict[str, Any]:
        data = {
            "name": title,
            "desc": description,
            "idList": project_id,
            "key": self.api_key,
            "token": self.token,
            **kwargs,
        }
        response = await self._client.post("/cards", params=data)
        response.raise_for_status()
        return response.json()
    
    async def update_task(self, task_id: str, **updates) -> Dict[str, Any]:
        updates["key"] = self.api_key
        updates["token"] = self.token
        response = await self._client.put(f"/cards/{task_id}", params=updates)
        response.raise_for_status()
        return response.json()
    
    async def add_comment(self, task_id: str, comment: str) -> Dict[str, Any]:
        params = {"text": comment, "key": self.api_key, "token": self.token}
        response = await self._client.post(f"/cards/{task_id}/actions/comments", params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_boards(self) -> List[Dict[str, Any]]:
        response = await self._client.get(f"/members/me/boards?key={self.api_key}&token={self.token}")
        response.raise_for_status()
        return response.json()
    
    async def get_cards_from_board(self, board_id: str) -> List[Dict[str, Any]]:
        response = await self._client.get(f"/boards/{board_id}/cards?key={self.api_key}&token={self.token}")
        response.raise_for_status()
        return response.json()
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        import uuid
        return Requirement(
            id=str(uuid.uuid4()),
            title=task.get("name", ""),
            description=task.get("desc", ""),
            source_type="trello",
            source_id=task.get("id", ""),
            source_url=task.get("url", ""),
            type="task",
            priority="medium",
        )

