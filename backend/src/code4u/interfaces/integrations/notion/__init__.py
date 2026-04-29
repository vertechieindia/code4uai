"""Notion integration for documentation and task management."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@register_integration("notion")
class NotionIntegration(TaskIntegration):
    """
    Notion Integration for code4u.ai.
    
    Features:
    - Create and update pages
    - Database operations
    - Requirements documentation
    - Meeting notes storage
    """
    
    name = "notion"
    BASE_URL = "https://api.notion.com/v1"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.api_key = os.getenv("NOTION_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/users/me")
            return {"status": "healthy", "user": response.json().get("name")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get a page from Notion."""
        response = await self._client.get(f"/pages/{task_id}")
        response.raise_for_status()
        return response.json()
    
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,  # database_id
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a page in a Notion database."""
        data = {
            "parent": {"database_id": project_id},
            "properties": {
                "Name": {"title": [{"text": {"content": title}}]},
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": description}}]
                    }
                }
            ],
        }
        
        # Add any additional properties
        for key, value in kwargs.items():
            if key.startswith("prop_"):
                prop_name = key[5:]
                data["properties"][prop_name] = value
        
        response = await self._client.post("/pages", json=data)
        response.raise_for_status()
        return response.json()
    
    async def update_task(self, task_id: str, **updates) -> Dict[str, Any]:
        """Update a Notion page."""
        data = {"properties": updates}
        response = await self._client.patch(f"/pages/{task_id}", json=data)
        response.raise_for_status()
        return response.json()
    
    async def add_comment(self, task_id: str, comment: str) -> Dict[str, Any]:
        """Add a comment to a page."""
        data = {
            "parent": {"page_id": task_id},
            "rich_text": [{"text": {"content": comment}}],
        }
        response = await self._client.post("/comments", json=data)
        response.raise_for_status()
        return response.json()
    
    async def create_meeting_notes_page(
        self,
        parent_page_id: str,
        title: str,
        summary: str,
        key_points: List[str],
        action_items: List[Dict[str, Any]],
        requirements: List[Requirement],
    ) -> Dict[str, Any]:
        """Create a meeting notes page with structured content."""
        children = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Summary"}}]}
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": summary}}]}
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Key Points"}}]}
            },
        ]
        
        # Add key points as bullet list
        for point in key_points:
            children.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": point}}]}
            })
        
        # Add action items
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "Action Items"}}]}
        })
        
        for item in action_items:
            children.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"text": {"content": f"{item.get('task', '')} - {item.get('owner', '')}"}}],
                    "checked": False,
                }
            })
        
        # Add requirements
        if requirements:
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "Extracted Requirements"}}]}
            })
            
            for req in requirements:
                children.append({
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": [{"text": {"content": f"[{req.priority.upper()}] {req.title}"}}],
                        "children": [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {"rich_text": [{"text": {"content": req.description}}]}
                            }
                        ]
                    }
                })
        
        data = {
            "parent": {"page_id": parent_page_id},
            "properties": {
                "title": {"title": [{"text": {"content": title}}]}
            },
            "children": children,
        }
        
        response = await self._client.post("/pages", json=data)
        response.raise_for_status()
        return response.json()
    
    async def query_database(
        self,
        database_id: str,
        filter: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """Query a Notion database."""
        data = {}
        if filter:
            data["filter"] = filter
        
        response = await self._client.post(f"/databases/{database_id}/query", json=data)
        response.raise_for_status()
        return response.json().get("results", [])
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        import uuid
        properties = task.get("properties", {})
        title = ""
        if "Name" in properties:
            title_prop = properties["Name"].get("title", [])
            if title_prop:
                title = title_prop[0].get("text", {}).get("content", "")
        
        return Requirement(
            id=str(uuid.uuid4()),
            title=title,
            description="",
            source_type="notion",
            source_id=task.get("id", ""),
            source_url=task.get("url", ""),
            type="task",
            priority="medium",
        )

