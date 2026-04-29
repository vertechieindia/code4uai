"""API routes for MCP Marketplace."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from code4u.interfaces.mcp_marketplace import MCPMarketplace, MCPRegistry
from code4u.interfaces.mcp_marketplace.marketplace import MCPCategory


router = APIRouter(prefix="/mcp", tags=["mcp-marketplace"])

# Instances
_marketplaces: Dict[str, MCPMarketplace] = {}
_registries: Dict[str, MCPRegistry] = {}


def get_marketplace(tenant_id: str) -> MCPMarketplace:
    if tenant_id not in _marketplaces:
        _marketplaces[tenant_id] = MCPMarketplace(tenant_id)
    return _marketplaces[tenant_id]


def get_registry(tenant_id: str) -> MCPRegistry:
    if tenant_id not in _registries:
        _registries[tenant_id] = MCPRegistry(tenant_id)
    return _registries[tenant_id]


# ============= Request/Response Models =============

class ServerInfo(BaseModel):
    """MCP server info."""
    id: str
    name: str
    description: str
    publisher: str
    verified: bool
    category: str
    version: str
    downloads: int
    rating: float
    tools: List[str]
    requires_auth: bool


class InstallRequest(BaseModel):
    """Request to install a server."""
    server_id: str
    config: Dict[str, Any] = {}
    env_vars: Dict[str, str] = {}


class InstalledInfo(BaseModel):
    """Installed server info."""
    server_id: str
    name: str
    version: str
    status: str
    enabled: bool


class ToolCallRequest(BaseModel):
    """Request to call a tool."""
    tool_name: str
    arguments: Dict[str, Any] = {}


# ============= Marketplace Endpoints =============

@router.get("/servers")
async def list_servers(
    category: Optional[str] = None,
    search: Optional[str] = None,
    verified_only: bool = False,
    x_tenant_id: str = Header(default="default"),
) -> List[ServerInfo]:
    """List available MCP servers."""
    marketplace = get_marketplace(x_tenant_id)
    
    cat = MCPCategory(category) if category else None
    servers = marketplace.list_servers(category=cat, search=search, verified_only=verified_only)
    
    return [
        ServerInfo(
            id=s.id,
            name=s.name,
            description=s.description,
            publisher=s.publisher,
            verified=s.verified,
            category=s.category.value,
            version=s.version,
            downloads=s.downloads,
            rating=s.rating,
            tools=s.tools,
            requires_auth=s.requires_auth,
        )
        for s in servers
    ]


@router.get("/servers/{server_id}")
async def get_server(
    server_id: str,
    x_tenant_id: str = Header(default="default"),
) -> ServerInfo:
    """Get server details."""
    marketplace = get_marketplace(x_tenant_id)
    server = marketplace.get_server(server_id)
    
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    return ServerInfo(
        id=server.id,
        name=server.name,
        description=server.description,
        publisher=server.publisher,
        verified=server.verified,
        category=server.category.value,
        version=server.version,
        downloads=server.downloads,
        rating=server.rating,
        tools=server.tools,
        requires_auth=server.requires_auth,
    )


@router.get("/categories")
async def get_categories(
    x_tenant_id: str = Header(default="default"),
) -> List[Dict[str, Any]]:
    """Get all categories with counts."""
    marketplace = get_marketplace(x_tenant_id)
    return marketplace.get_categories()


@router.post("/install")
async def install_server(
    request: InstallRequest,
    x_tenant_id: str = Header(default="default"),
) -> InstalledInfo:
    """Install an MCP server."""
    marketplace = get_marketplace(x_tenant_id)
    
    try:
        installed = await marketplace.install(
            server_id=request.server_id,
            config=request.config,
            env_vars=request.env_vars,
        )
        
        return InstalledInfo(
            server_id=installed.server_id,
            name=installed.name,
            version=installed.version,
            status=installed.status.value,
            enabled=installed.enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/installed/{server_id}")
async def uninstall_server(
    server_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, bool]:
    """Uninstall an MCP server."""
    marketplace = get_marketplace(x_tenant_id)
    result = await marketplace.uninstall(server_id)
    return {"uninstalled": result}


@router.get("/installed")
async def list_installed(
    x_tenant_id: str = Header(default="default"),
) -> List[InstalledInfo]:
    """List installed servers."""
    marketplace = get_marketplace(x_tenant_id)
    
    return [
        InstalledInfo(
            server_id=s.server_id,
            name=s.name,
            version=s.version,
            status=s.status.value,
            enabled=s.enabled,
        )
        for s in marketplace.list_installed()
    ]


@router.post("/installed/{server_id}/enable")
async def enable_server(
    server_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, bool]:
    """Enable an installed server."""
    marketplace = get_marketplace(x_tenant_id)
    result = await marketplace.enable(server_id)
    return {"enabled": result}


@router.post("/installed/{server_id}/disable")
async def disable_server(
    server_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, bool]:
    """Disable an installed server."""
    marketplace = get_marketplace(x_tenant_id)
    result = await marketplace.disable(server_id)
    return {"disabled": result}


# ============= Runtime Endpoints =============

@router.post("/runtime/{server_id}/start")
async def start_server(
    server_id: str,
    config: Dict[str, Any] = {},
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Start an MCP server."""
    registry = get_registry(x_tenant_id)
    runtime = await registry.start_server(server_id, config)
    
    return {
        "server_id": runtime.server_id,
        "status": runtime.status.value,
        "url": runtime.url,
    }


@router.post("/runtime/{server_id}/stop")
async def stop_server(
    server_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, bool]:
    """Stop an MCP server."""
    registry = get_registry(x_tenant_id)
    result = await registry.stop_server(server_id)
    return {"stopped": result}


@router.get("/runtime")
async def list_runtimes(
    x_tenant_id: str = Header(default="default"),
) -> List[Dict[str, Any]]:
    """List all server runtimes."""
    registry = get_registry(x_tenant_id)
    
    return [
        {
            "server_id": r.server_id,
            "status": r.status.value,
            "url": r.url,
            "requests_count": r.requests_count,
        }
        for r in registry.list_runtimes()
    ]


@router.get("/tools")
async def list_tools(
    server_id: Optional[str] = None,
    x_tenant_id: str = Header(default="default"),
) -> List[Dict[str, Any]]:
    """List available tools."""
    registry = get_registry(x_tenant_id)
    
    return [
        {
            "name": t.name,
            "description": t.description,
            "server_id": t.server_id,
            "input_schema": t.input_schema,
        }
        for t in registry.list_tools(server_id)
    ]


@router.post("/tools/call")
async def call_tool(
    request: ToolCallRequest,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Call an MCP tool."""
    registry = get_registry(x_tenant_id)
    
    try:
        result = await registry.call_tool(request.tool_name, request.arguments)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/health")
async def health_check_all(
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Health check all running servers."""
    registry = get_registry(x_tenant_id)
    return await registry.health_check_all()

