"""Browser tools for agent function calling."""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .agent import BrowserAgent
from .models import BrowserTask, BrowserAction, ActionType, ElementSelector


@dataclass
class ToolDefinition:
    """Definition of a browser tool."""
    name: str
    description: str
    parameters: Dict[str, Any]


class BrowserTools:
    """
    Browser tools for LLM function calling.
    
    Provides structured tool definitions that can be used
    with OpenAI-style function calling or tool use.
    """
    
    TOOLS: List[ToolDefinition] = [
        ToolDefinition(
            name="browser_navigate",
            description="Navigate to a URL",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to navigate to"
                    }
                },
                "required": ["url"]
            }
        ),
        ToolDefinition(
            name="browser_click",
            description="Click on an element on the page",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the element to click"
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description of the element"
                    }
                },
                "required": ["selector"]
            }
        ),
        ToolDefinition(
            name="browser_type",
            description="Type text into an input field",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the input element"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type"
                    },
                    "submit": {
                        "type": "boolean",
                        "description": "Whether to press Enter after typing"
                    }
                },
                "required": ["selector", "text"]
            }
        ),
        ToolDefinition(
            name="browser_scroll",
            description="Scroll the page",
            parameters={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down"],
                        "description": "Direction to scroll"
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Pixels to scroll (default 300)"
                    }
                },
                "required": ["direction"]
            }
        ),
        ToolDefinition(
            name="browser_screenshot",
            description="Take a screenshot of the current page",
            parameters={
                "type": "object",
                "properties": {
                    "full_page": {
                        "type": "boolean",
                        "description": "Whether to capture the full page"
                    }
                }
            }
        ),
        ToolDefinition(
            name="browser_snapshot",
            description="Get an accessibility snapshot of the page for understanding content",
            parameters={
                "type": "object",
                "properties": {}
            }
        ),
        ToolDefinition(
            name="browser_extract",
            description="Extract text or data from an element",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the element (optional, extracts full page if not provided)"
                    }
                }
            }
        ),
        ToolDefinition(
            name="browser_wait",
            description="Wait for a specified time or for an element to appear",
            parameters={
                "type": "object",
                "properties": {
                    "time": {
                        "type": "number",
                        "description": "Time to wait in seconds"
                    },
                    "selector": {
                        "type": "string",
                        "description": "Wait for this element to appear"
                    }
                }
            }
        ),
        ToolDefinition(
            name="browser_hover",
            description="Hover over an element",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the element"
                    }
                },
                "required": ["selector"]
            }
        ),
        ToolDefinition(
            name="browser_select",
            description="Select an option from a dropdown",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the select element"
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to select"
                    }
                },
                "required": ["selector", "value"]
            }
        ),
        ToolDefinition(
            name="browser_press_key",
            description="Press a keyboard key",
            parameters={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key to press (e.g., 'Enter', 'Escape', 'Tab')"
                    }
                },
                "required": ["key"]
            }
        ),
    ]
    
    def __init__(self, agent: BrowserAgent):
        """Initialize browser tools.
        
        Args:
            agent: BrowserAgent instance
        """
        self.agent = agent
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for LLM function calling.
        
        Returns:
            List of tool definitions in OpenAI format
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in self.TOOLS
        ]
    
    async def execute_tool(
        self, 
        name: str, 
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a browser tool.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        if name == "browser_navigate":
            result = await self.agent.navigate(arguments["url"])
            return {"success": result.success, "error": result.error}
        
        elif name == "browser_click":
            result = await self.agent.click(arguments["selector"])
            return {"success": result.success, "error": result.error}
        
        elif name == "browser_type":
            result = await self.agent.type_text(
                arguments["selector"],
                arguments["text"]
            )
            if arguments.get("submit"):
                await self.agent.controller.execute_action(
                    BrowserAction(type=ActionType.PRESS_KEY, key="Enter")
                )
            return {"success": result.success, "error": result.error}
        
        elif name == "browser_scroll":
            direction = arguments["direction"]
            amount = arguments.get("amount", 300)
            scroll_y = amount if direction == "down" else -amount
            result = await self.agent.controller.execute_action(
                BrowserAction(type=ActionType.SCROLL, scroll_y=scroll_y)
            )
            return {"success": result.success}
        
        elif name == "browser_screenshot":
            screenshot = await self.agent.screenshot()
            return {"screenshot": screenshot[:100] + "..." if screenshot else None}
        
        elif name == "browser_snapshot":
            snapshot = await self.agent.get_snapshot()
            return {
                "url": snapshot.url,
                "title": snapshot.title,
                "elements_count": len(snapshot.elements),
                "text_preview": snapshot.text[:500] if snapshot.text else "",
            }
        
        elif name == "browser_extract":
            selector = arguments.get("selector")
            result = await self.agent.controller.execute_action(
                BrowserAction(
                    type=ActionType.EXTRACT,
                    target=ElementSelector(selector=selector) if selector else None
                )
            )
            return {"data": result.extracted_data, "success": result.success}
        
        elif name == "browser_wait":
            wait_time = arguments.get("time", 1.0)
            result = await self.agent.controller.execute_action(
                BrowserAction(type=ActionType.WAIT, wait_time=wait_time)
            )
            return {"success": result.success}
        
        elif name == "browser_hover":
            result = await self.agent.controller.execute_action(
                BrowserAction(
                    type=ActionType.HOVER,
                    target=ElementSelector(selector=arguments["selector"])
                )
            )
            return {"success": result.success, "error": result.error}
        
        elif name == "browser_select":
            result = await self.agent.controller.execute_action(
                BrowserAction(
                    type=ActionType.SELECT,
                    target=ElementSelector(selector=arguments["selector"]),
                    text=arguments["value"]
                )
            )
            return {"success": result.success, "error": result.error}
        
        elif name == "browser_press_key":
            result = await self.agent.controller.execute_action(
                BrowserAction(type=ActionType.PRESS_KEY, key=arguments["key"])
            )
            return {"success": result.success}
        
        else:
            return {"error": f"Unknown tool: {name}"}

