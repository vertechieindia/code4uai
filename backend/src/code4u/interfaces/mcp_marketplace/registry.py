"""MCP Registry - Runtime management of MCP servers."""

from __future__ import annotations
import asyncio
import uuid
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ServerStatus(str, Enum):
    """Runtime status of an MCP server."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    RESTARTING = "restarting"


@dataclass
class ServerRuntime:
    """Runtime state of an MCP server."""
    server_id: str
    status: ServerStatus = ServerStatus.STOPPED
    
    # Process info
    process_id: Optional[int] = None
    port: Optional[int] = None
    url: Optional[str] = None
    
    # Health
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"
    error_message: Optional[str] = None
    
    # Stats
    requests_count: int = 0
    errors_count: int = 0
    avg_latency_ms: float = 0.0
    
    # Timestamps
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None


@dataclass
class MCPTool:
    """A tool provided by an MCP server."""
    name: str
    description: str
    
    # Schema
    input_schema: Dict[str, Any] = field(default_factory=dict)
    
    # Source
    server_id: str = ""


@dataclass
class MCPResource:
    """A resource provided by an MCP server."""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "application/json"
    
    # Source
    server_id: str = ""


class MCPRegistry:
    """
    Registry for managing MCP server runtimes.
    
    Responsibilities:
    - Start/stop MCP servers
    - Health monitoring
    - Tool/resource discovery
    - Request routing
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize registry."""
        self.tenant_id = tenant_id
        self._runtimes: Dict[str, ServerRuntime] = {}
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}
        self._health_check_interval = 30  # seconds
    
    async def start_server(
        self,
        server_id: str,
        config: Dict[str, Any],
    ) -> ServerRuntime:
        """Start an MCP server.
        
        Args:
            server_id: Server to start
            config: Server configuration
            
        Returns:
            Server runtime
        """
        runtime = ServerRuntime(
            server_id=server_id,
            status=ServerStatus.STARTING,
            started_at=datetime.utcnow(),
        )
        
        self._runtimes[server_id] = runtime
        
        try:
            # In production, this would:
            # 1. Spawn process for the MCP server
            # 2. Wait for it to be ready
            # 3. Discover tools/resources
            
            # Simulated startup
            runtime.status = ServerStatus.RUNNING
            runtime.port = 3000 + len(self._runtimes)
            runtime.url = f"http://localhost:{runtime.port}"
            
            # Discover capabilities
            await self._discover_capabilities(server_id)
            
        except Exception as e:
            runtime.status = ServerStatus.ERROR
            runtime.error_message = str(e)
        
        return runtime
    
    async def stop_server(self, server_id: str) -> bool:
        """Stop an MCP server."""
        runtime = self._runtimes.get(server_id)
        if not runtime:
            return False
        
        runtime.status = ServerStatus.STOPPED
        runtime.stopped_at = datetime.utcnow()
        
        # Remove tools/resources from this server
        self._tools = {k: v for k, v in self._tools.items() if v.server_id != server_id}
        self._resources = {k: v for k, v in self._resources.items() if v.server_id != server_id}
        
        return True
    
    async def restart_server(self, server_id: str) -> ServerRuntime:
        """Restart an MCP server."""
        runtime = self._runtimes.get(server_id)
        if runtime:
            runtime.status = ServerStatus.RESTARTING
            await self.stop_server(server_id)
        
        # Get config and restart
        config = {}  # Would retrieve from storage
        return await self.start_server(server_id, config)
    
    async def _discover_capabilities(self, server_id: str) -> None:
        """Discover tools and resources from a server."""
        # In production, this would call the MCP server's
        # tools/list and resources/list methods
        
        # Simulated discovery based on server_id
        if server_id == "browser":
            self._tools["browser.navigate"] = MCPTool(
                name="navigate",
                description="Navigate to a URL",
                input_schema={"type": "object", "properties": {"url": {"type": "string"}}},
                server_id=server_id,
            )
            self._tools["browser.click"] = MCPTool(
                name="click",
                description="Click an element",
                input_schema={"type": "object", "properties": {"selector": {"type": "string"}}},
                server_id=server_id,
            )
    
    def get_runtime(self, server_id: str) -> Optional[ServerRuntime]:
        """Get server runtime."""
        return self._runtimes.get(server_id)
    
    def list_runtimes(self) -> List[ServerRuntime]:
        """List all server runtimes."""
        return list(self._runtimes.values())
    
    def list_running(self) -> List[ServerRuntime]:
        """List running servers."""
        return [r for r in self._runtimes.values() if r.status == ServerStatus.RUNNING]
    
    def list_tools(
        self,
        server_id: Optional[str] = None,
    ) -> List[MCPTool]:
        """List available tools.
        
        Args:
            server_id: Optional filter by server
            
        Returns:
            List of tools
        """
        tools = list(self._tools.values())
        if server_id:
            tools = [t for t in tools if t.server_id == server_id]
        return tools
    
    def list_resources(
        self,
        server_id: Optional[str] = None,
    ) -> List[MCPResource]:
        """List available resources."""
        resources = list(self._resources.values())
        if server_id:
            resources = [r for r in resources if r.server_id == server_id]
        return resources
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call a tool.
        
        Args:
            tool_name: Tool to call
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        runtime = self._runtimes.get(tool.server_id)
        if not runtime or runtime.status != ServerStatus.RUNNING:
            raise RuntimeError(f"Server not running: {tool.server_id}")
        
        # In production, this would make an MCP protocol call
        # to the server at runtime.url
        
        runtime.requests_count += 1
        runtime.last_health_check = datetime.utcnow()
        
        return {"result": f"Called {tool_name} with {arguments}"}
    
    async def read_resource(
        self,
        uri: str,
    ) -> Dict[str, Any]:
        """Read a resource.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource content
        """
        resource = self._resources.get(uri)
        if not resource:
            raise ValueError(f"Resource not found: {uri}")
        
        runtime = self._runtimes.get(resource.server_id)
        if not runtime or runtime.status != ServerStatus.RUNNING:
            raise RuntimeError(f"Server not running: {resource.server_id}")
        
        # Would make MCP call
        return {"uri": uri, "content": "..."}
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Health check all running servers."""
        results = {}
        
        for server_id, runtime in self._runtimes.items():
            if runtime.status == ServerStatus.RUNNING:
                try:
                    # Would ping the server
                    runtime.health_status = "healthy"
                    runtime.last_health_check = datetime.utcnow()
                    results[server_id] = {"status": "healthy"}
                except Exception as e:
                    runtime.health_status = "unhealthy"
                    runtime.error_message = str(e)
                    results[server_id] = {"status": "unhealthy", "error": str(e)}
            else:
                results[server_id] = {"status": runtime.status.value}
        
        return results

