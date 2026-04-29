"""Miro integration for visual collaboration."""

from __future__ import annotations
import os
from typing import Optional, List, Dict, Any
import httpx

from ..base import BaseIntegration, IntegrationType, IntegrationConfig
from ..registry import register_integration


@register_integration("miro")
class MiroIntegration(BaseIntegration):
    """
    Miro Integration for code4u.ai.
    
    Features:
    - Create boards for planning
    - Extract requirements from stickies/cards
    - Sync diagrams
    """
    
    name = "miro"
    type = IntegrationType.DESIGN
    BASE_URL = "https://api.miro.com/v2"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.access_token = os.getenv("MIRO_ACCESS_TOKEN", "")
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
            response = await self._client.get("/boards")
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_boards(self) -> List[Dict[str, Any]]:
        """Get all boards."""
        response = await self._client.get("/boards")
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def get_stickies(self, board_id: str) -> List[Dict[str, Any]]:
        """Get sticky notes from a board."""
        response = await self._client.get(f"/boards/{board_id}/sticky_notes")
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def create_sticky(
        self,
        board_id: str,
        content: str,
        x: float = 0,
        y: float = 0,
    ) -> Dict[str, Any]:
        """Create a sticky note."""
        data = {
            "data": {"content": content},
            "position": {"x": x, "y": y},
        }
        response = await self._client.post(f"/boards/{board_id}/sticky_notes", json=data)
        response.raise_for_status()
        return response.json()
    
    async def extract_requirements_from_board(
        self,
        board_id: str,
    ) -> List[Dict[str, Any]]:
        """Extract requirements from sticky notes."""
        stickies = await self.get_stickies(board_id)
        
        requirements = []
        for sticky in stickies:
            content = sticky.get("data", {}).get("content", "")
            if content:
                requirements.append({
                    "id": sticky.get("id"),
                    "title": content[:100],
                    "description": content,
                    "source_type": "miro",
                    "source_id": sticky.get("id"),
                })
        
        return requirements

