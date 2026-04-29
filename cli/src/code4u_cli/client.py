"""HTTP client for code4u.ai API."""

from __future__ import annotations
import os
from typing import Optional, Dict, Any, AsyncIterator
import httpx
from pydantic import BaseModel


class ClientConfig(BaseModel):
    """Client configuration."""
    server_url: str = "http://localhost:8002"
    api_key: Optional[str] = None
    tenant_id: str = "default"
    timeout: float = 60.0


def get_config() -> ClientConfig:
    """Get client configuration from environment."""
    return ClientConfig(
        server_url=os.getenv("CODE4U_SERVER_URL", "http://localhost:8002"),
        api_key=os.getenv("CODE4U_API_KEY"),
        tenant_id=os.getenv("CODE4U_TENANT_ID", "default"),
    )


class Code4uClient:
    """HTTP client for code4u.ai API."""
    
    def __init__(self, config: Optional[ClientConfig] = None):
        """Initialize client.
        
        Args:
            config: Client configuration
        """
        self.config = config or get_config()
        self._client = httpx.AsyncClient(
            base_url=self.config.server_url,
            timeout=self.config.timeout,
            headers=self._get_headers(),
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "X-Tenant-ID": self.config.tenant_id,
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self._client.aclose()
    
    async def health(self) -> Dict[str, Any]:
        """Check API health."""
        response = await self._client.get("/health")
        response.raise_for_status()
        return response.json()
    
    async def refactor(
        self,
        intent: str,
        file_path: str,
        selection: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request a refactoring.
        
        Args:
            intent: Refactoring description
            file_path: Target file
            selection: Optional selected code
            
        Returns:
            Refactoring result
        """
        response = await self._client.post("/api/v1/refactor", json={
            "intent": intent,
            "file_path": file_path,
            "selection": selection,
        })
        response.raise_for_status()
        return response.json()
    
    async def analyze_impact(
        self,
        file_path: str,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze change impact.
        
        Args:
            file_path: File to analyze
            symbol: Optional symbol to focus on
            
        Returns:
            Impact analysis
        """
        response = await self._client.post("/api/v1/graph/impact", json={
            "file_path": file_path,
            "symbol": symbol,
        })
        response.raise_for_status()
        return response.json()
    
    async def get_completions(
        self,
        file_path: str,
        content: str,
        cursor_line: int,
        cursor_column: int,
        language: str,
    ) -> Dict[str, Any]:
        """Get code completions.
        
        Args:
            file_path: File path
            content: File content
            cursor_line: Cursor line
            cursor_column: Cursor column
            language: Programming language
            
        Returns:
            Completions
        """
        response = await self._client.post("/api/v1/autocomplete/complete", json={
            "file_path": file_path,
            "content": content,
            "cursor_line": cursor_line,
            "cursor_column": cursor_column,
            "language": language,
        })
        response.raise_for_status()
        return response.json()
    
    async def chat_stream(
        self,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream chat response.
        
        Args:
            message: User message
            conversation_id: Optional conversation ID
            
        Yields:
            Response chunks
        """
        async with self._client.stream(
            "POST",
            "/api/v1/agent/chat/stream",
            json={
                "message": message,
                "conversation_id": conversation_id,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]
    
    async def index_directory(
        self,
        directory: str,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """Index a directory for the Knowledge Graph.
        
        Args:
            directory: Directory to index
            recursive: Whether to recurse
            
        Returns:
            Indexing stats
        """
        response = await self._client.post("/api/v1/graph/index", json={
            "directory": directory,
            "recursive": recursive,
        })
        response.raise_for_status()
        return response.json()
    
    async def get_graph_stats(self) -> Dict[str, Any]:
        """Get Knowledge Graph statistics."""
        response = await self._client.get("/api/v1/graph/stats")
        response.raise_for_status()
        return response.json()
    
    async def get_models(self) -> Dict[str, Any]:
        """Get available models."""
        response = await self._client.get("/api/v1/models")
        response.raise_for_status()
        return response.json()

