"""Dropbox integration for file storage."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import BaseIntegration, IntegrationType, IntegrationConfig
from ..registry import register_integration


@register_integration("dropbox")
class DropboxIntegration(BaseIntegration):
    """
    Dropbox Integration for code4u.ai.
    
    Features:
    - File storage and retrieval
    - Shared links
    - Team folders
    """
    
    name = "dropbox"
    type = IntegrationType.STORAGE
    API_URL = "https://api.dropboxapi.com/2"
    CONTENT_URL = "https://content.dropboxapi.com/2"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.access_token = os.getenv("DROPBOX_ACCESS_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        self._client = httpx.AsyncClient(
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
            response = await self._client.post(
                f"{self.API_URL}/users/get_current_account"
            )
            user = response.json()
            return {"status": "healthy", "user": user.get("name", {}).get("display_name")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def list_folder(self, path: str = "") -> List[Dict[str, Any]]:
        """List contents of a folder."""
        data = {"path": path if path else ""}
        response = await self._client.post(
            f"{self.API_URL}/files/list_folder",
            json=data,
        )
        response.raise_for_status()
        return response.json().get("entries", [])
    
    async def upload_file(
        self,
        path: str,
        content: bytes,
        mode: str = "add",
    ) -> Dict[str, Any]:
        """Upload a file."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": f'{{"path": "{path}", "mode": "{mode}"}}',
        }
        response = await self._client.post(
            f"{self.CONTENT_URL}/files/upload",
            content=content,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()
    
    async def download_file(self, path: str) -> bytes:
        """Download a file."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Dropbox-API-Arg": f'{{"path": "{path}"}}',
        }
        response = await self._client.post(
            f"{self.CONTENT_URL}/files/download",
            headers=headers,
        )
        response.raise_for_status()
        return response.content
    
    async def create_shared_link(self, path: str) -> Dict[str, Any]:
        """Create a shared link for a file."""
        data = {"path": path, "settings": {"requested_visibility": "public"}}
        response = await self._client.post(
            f"{self.API_URL}/sharing/create_shared_link_with_settings",
            json=data,
        )
        response.raise_for_status()
        return response.json()
    
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for files."""
        data = {"query": query}
        response = await self._client.post(
            f"{self.API_URL}/files/search_v2",
            json=data,
        )
        response.raise_for_status()
        return response.json().get("matches", [])

