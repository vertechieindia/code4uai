"""MCP Server - Base class for building MCP servers."""

from __future__ import annotations
import asyncio
import json
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class ToolDefinition:
    """Definition of an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class ResourceDefinition:
    """Definition of an MCP resource."""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "application/json"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


@dataclass
class PromptDefinition:
    """Definition of an MCP prompt."""
    name: str
    description: str = ""
    arguments: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
        }


class MCPServer(ABC):
    """
    Base class for building MCP servers.
    
    Implements the Model Context Protocol for:
    - Tool execution
    - Resource access
    - Prompt templates
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """Initialize MCP server.
        
        Args:
            name: Server name
            version: Server version
        """
        self.name = name
        self.version = version
        
        self._tools: Dict[str, ToolDefinition] = {}
        self._resources: Dict[str, ResourceDefinition] = {}
        self._prompts: Dict[str, PromptDefinition] = {}
        
        self._tool_handlers: Dict[str, Callable] = {}
        self._resource_handlers: Dict[str, Callable] = {}
        self._prompt_handlers: Dict[str, Callable] = {}
    
    def tool(
        self,
        name: str,
        description: str,
        input_schema: Optional[Dict[str, Any]] = None,
    ) -> Callable:
        """Decorator to register a tool.
        
        Args:
            name: Tool name
            description: Tool description
            input_schema: JSON Schema for input
        """
        def decorator(func: Callable) -> Callable:
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                input_schema=input_schema or {},
            )
            self._tool_handlers[name] = func
            return func
        return decorator
    
    def resource(
        self,
        uri: str,
        name: str,
        description: str = "",
        mime_type: str = "application/json",
    ) -> Callable:
        """Decorator to register a resource.
        
        Args:
            uri: Resource URI
            name: Resource name
            description: Resource description
            mime_type: MIME type
        """
        def decorator(func: Callable) -> Callable:
            self._resources[uri] = ResourceDefinition(
                uri=uri,
                name=name,
                description=description,
                mime_type=mime_type,
            )
            self._resource_handlers[uri] = func
            return func
        return decorator
    
    def prompt(
        self,
        name: str,
        description: str = "",
        arguments: Optional[List[Dict[str, Any]]] = None,
    ) -> Callable:
        """Decorator to register a prompt template.
        
        Args:
            name: Prompt name
            description: Prompt description
            arguments: Prompt arguments
        """
        def decorator(func: Callable) -> Callable:
            self._prompts[name] = PromptDefinition(
                name=name,
                description=description,
                arguments=arguments or [],
            )
            self._prompt_handlers[name] = func
            return func
        return decorator
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools."""
        return [t.to_dict() for t in self._tools.values()]
    
    def list_resources(self) -> List[Dict[str, Any]]:
        """List all registered resources."""
        return [r.to_dict() for r in self._resources.values()]
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """List all registered prompts."""
        return [p.to_dict() for p in self._prompts.values()]
    
    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call a tool.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        handler = self._tool_handlers.get(name)
        if not handler:
            raise ValueError(f"Tool not found: {name}")
        
        if asyncio.iscoroutinefunction(handler):
            result = await handler(**arguments)
        else:
            result = handler(**arguments)
        
        return {"content": [{"type": "text", "text": str(result)}]}
    
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
        handler = self._resource_handlers.get(uri)
        if not handler:
            raise ValueError(f"Resource not found: {uri}")
        
        if asyncio.iscoroutinefunction(handler):
            content = await handler()
        else:
            content = handler()
        
        resource = self._resources[uri]
        return {
            "contents": [{
                "uri": uri,
                "mimeType": resource.mime_type,
                "text": json.dumps(content) if isinstance(content, (dict, list)) else str(content),
            }]
        }
    
    async def get_prompt(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Get a prompt.
        
        Args:
            name: Prompt name
            arguments: Prompt arguments
            
        Returns:
            Prompt messages
        """
        handler = self._prompt_handlers.get(name)
        if not handler:
            raise ValueError(f"Prompt not found: {name}")
        
        if asyncio.iscoroutinefunction(handler):
            messages = await handler(**arguments)
        else:
            messages = handler(**arguments)
        
        return {"messages": messages}
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information."""
        return {
            "name": self.name,
            "version": self.version,
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True} if self._tools else {},
                "resources": {"listChanged": True} if self._resources else {},
                "prompts": {"listChanged": True} if self._prompts else {},
            }
        }


# Example server implementation
class ExampleMCPServer(MCPServer):
    """Example MCP server for demonstration."""
    
    def __init__(self):
        super().__init__("example-server", "1.0.0")
        
        # Register tools using decorators
        @self.tool(
            "greet",
            "Greet a user",
            {"type": "object", "properties": {"name": {"type": "string"}}},
        )
        def greet(name: str) -> str:
            return f"Hello, {name}!"
        
        @self.resource(
            "example://info",
            "Server Info",
            "Get server information",
        )
        def get_info() -> Dict[str, Any]:
            return {"name": self.name, "version": self.version}
        
        @self.prompt(
            "greeting",
            "Generate a greeting",
            [{"name": "name", "required": True}],
        )
        def greeting_prompt(name: str) -> List[Dict[str, Any]]:
            return [
                {"role": "user", "content": {"type": "text", "text": f"Please greet {name}"}}
            ]

