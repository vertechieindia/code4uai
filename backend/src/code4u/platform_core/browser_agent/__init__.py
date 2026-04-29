"""
code4u.ai Browser Agent

Autonomous browser agent for:
- Web scraping and data extraction
- UI testing and interaction
- Live preview manipulation
- Deployment verification
- Documentation browsing
"""

from .agent import BrowserAgent
from .controller import BrowserController
from .models import (
    BrowserAction,
    BrowserState,
    BrowserTask,
    BrowserResult,
    ElementSelector,
    PageSnapshot,
    BrowserConfig,
    ActionType,
    ActionResult,
)
from .tools import BrowserTools

__all__ = [
    "BrowserAgent",
    "BrowserController",
    "BrowserAction",
    "BrowserState",
    "BrowserTask",
    "BrowserResult",
    "ElementSelector",
    "PageSnapshot",
    "BrowserTools",
    "BrowserConfig",
    "ActionType",
    "ActionResult",
]

