"""Monday.com integration for project management."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@register_integration("monday")
class MondayIntegration(TaskIntegration):
    """Monday.com Integration for code4u.ai."""
    
    name = "monday"
    BASE_URL = "https://api.monday.com/v2"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.config = config or IntegrationConfig(
            api_key=os.getenv("MONDAY_API_KEY", ""),
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": self.config.api_key,
                "Content-Type": "application/json",
            },
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            query = '{ me { name email } }'
            response = await self._client.post("", json={"query": query})
            return {"status": "healthy", "user": response.json().get("data", {}).get("me")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _graphql(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute GraphQL query."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        response = await self._client.post("", json=payload)
        response.raise_for_status()
        return response.json()
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        query = f'''
        {{ items(ids: [{task_id}]) {{
            id name column_values {{ id text value }}
        }} }}
        '''
        result = await self._graphql(query)
        items = result.get("data", {}).get("items", [])
        return items[0] if items else {}
    
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,  # board_id in Monday
        **kwargs,
    ) -> Dict[str, Any]:
        mutation = f'''
        mutation {{
            create_item(board_id: {project_id}, item_name: "{title}") {{
                id
            }}
        }}
        '''
        result = await self._graphql(mutation)
        return result.get("data", {}).get("create_item", {})
    
    async def update_task(self, task_id: str, **updates) -> Dict[str, Any]:
        # Monday uses column_values for updates
        return {}
    
    async def add_comment(self, task_id: str, comment: str) -> Dict[str, Any]:
        mutation = f'''
        mutation {{
            create_update(item_id: {task_id}, body: "{comment}") {{
                id
            }}
        }}
        '''
        result = await self._graphql(mutation)
        return result.get("data", {}).get("create_update", {})
    
    async def get_boards(self) -> List[Dict[str, Any]]:
        query = '{ boards { id name } }'
        result = await self._graphql(query)
        return result.get("data", {}).get("boards", [])
    
    async def get_items_from_board(self, board_id: str) -> List[Dict[str, Any]]:
        query = f'''
        {{ boards(ids: [{board_id}]) {{
            items_page {{ items {{ id name column_values {{ id text }} }} }}
        }} }}
        '''
        result = await self._graphql(query)
        boards = result.get("data", {}).get("boards", [])
        return boards[0].get("items_page", {}).get("items", []) if boards else []
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        import uuid
        return Requirement(
            id=str(uuid.uuid4()),
            title=task.get("name", ""),
            description="",  # Monday uses column_values
            source_type="monday",
            source_id=task.get("id", ""),
            type="task",
            priority="medium",
        )

