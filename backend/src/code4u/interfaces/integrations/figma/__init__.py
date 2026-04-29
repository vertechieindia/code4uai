"""Figma integration for design collaboration."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import BaseIntegration, IntegrationType, IntegrationConfig
from ..registry import register_integration


@register_integration("figma")
class FigmaIntegration(BaseIntegration):
    """
    Figma Integration for code4u.ai.
    
    Features:
    - Get design files and components
    - Extract design specs
    - Comment on designs
    - Watch for design updates
    """
    
    name = "figma"
    type = IntegrationType.DESIGN
    BASE_URL = "https://api.figma.com/v1"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.access_token = os.getenv("FIGMA_ACCESS_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"X-Figma-Token": self.access_token},
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/me")
            user = response.json()
            return {"status": "healthy", "user": user.get("handle")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_file(self, file_key: str) -> Dict[str, Any]:
        """Get a Figma file."""
        response = await self._client.get(f"/files/{file_key}")
        response.raise_for_status()
        return response.json()
    
    async def get_file_nodes(
        self,
        file_key: str,
        node_ids: List[str],
    ) -> Dict[str, Any]:
        """Get specific nodes from a file."""
        ids = ",".join(node_ids)
        response = await self._client.get(f"/files/{file_key}/nodes?ids={ids}")
        response.raise_for_status()
        return response.json()
    
    async def get_comments(self, file_key: str) -> List[Dict[str, Any]]:
        """Get comments on a file."""
        response = await self._client.get(f"/files/{file_key}/comments")
        response.raise_for_status()
        return response.json().get("comments", [])
    
    async def add_comment(
        self,
        file_key: str,
        message: str,
        client_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a comment to a file."""
        data = {"message": message}
        if client_meta:
            data["client_meta"] = client_meta
        
        response = await self._client.post(f"/files/{file_key}/comments", json=data)
        response.raise_for_status()
        return response.json()
    
    async def get_images(
        self,
        file_key: str,
        node_ids: List[str],
        format: str = "png",
        scale: float = 1.0,
    ) -> Dict[str, Any]:
        """Export nodes as images."""
        ids = ",".join(node_ids)
        params = {"ids": ids, "format": format, "scale": scale}
        response = await self._client.get(f"/images/{file_key}", params=params)
        response.raise_for_status()
        return response.json()
    
    async def get_team_projects(self, team_id: str) -> List[Dict[str, Any]]:
        """Get projects in a team."""
        response = await self._client.get(f"/teams/{team_id}/projects")
        response.raise_for_status()
        return response.json().get("projects", [])
    
    async def get_project_files(self, project_id: str) -> List[Dict[str, Any]]:
        """Get files in a project."""
        response = await self._client.get(f"/projects/{project_id}/files")
        response.raise_for_status()
        return response.json().get("files", [])

