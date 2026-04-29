"""Data models for Browser Agent."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class ActionType(str, Enum):
    """Types of browser actions."""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    HOVER = "hover"
    SELECT = "select"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"
    EXECUTE_JS = "execute_js"
    PRESS_KEY = "press_key"
    DRAG_DROP = "drag_drop"
    UPLOAD = "upload"
    DOWNLOAD = "download"


class BrowserState(str, Enum):
    """States of the browser agent."""
    IDLE = "idle"
    NAVIGATING = "navigating"
    INTERACTING = "interacting"
    WAITING = "waiting"
    EXTRACTING = "extracting"
    ERROR = "error"
    COMPLETE = "complete"


@dataclass
class ElementSelector:
    """Selector for targeting DOM elements."""
    # Primary selector (CSS, XPath, or accessibility)
    selector: str
    selector_type: str = "css"  # css, xpath, accessibility, text
    
    # Fallback selectors
    fallbacks: List[str] = field(default_factory=list)
    
    # Human-readable description
    description: Optional[str] = None
    
    # Position hints
    index: int = 0
    visible_only: bool = True
    

@dataclass
class BrowserAction:
    """A single browser action."""
    type: ActionType
    
    # Target element (for click, type, etc.)
    target: Optional[ElementSelector] = None
    
    # Action-specific data
    url: Optional[str] = None  # for navigate
    text: Optional[str] = None  # for type
    key: Optional[str] = None  # for press_key
    script: Optional[str] = None  # for execute_js
    scroll_x: int = 0
    scroll_y: int = 0
    wait_time: float = 0.0
    
    # Options
    timeout: float = 30.0
    retry_count: int = 3
    

@dataclass
class PageSnapshot:
    """Snapshot of current page state."""
    url: str
    title: str
    html: Optional[str] = None
    text: Optional[str] = None
    
    # Accessibility tree (for agent understanding)
    accessibility_tree: Optional[Dict[str, Any]] = None
    
    # DOM summary
    elements: List[Dict[str, Any]] = field(default_factory=list)
    
    # Console logs
    console_logs: List[Dict[str, Any]] = field(default_factory=list)
    
    # Network requests
    network_requests: List[Dict[str, Any]] = field(default_factory=list)
    
    # Screenshot
    screenshot_base64: Optional[str] = None
    
    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)
    

@dataclass
class BrowserTask:
    """A task for the browser agent to complete."""
    id: str
    description: str
    
    # Target URL (optional, may already be on the page)
    url: Optional[str] = None
    
    # Expected outcomes
    success_criteria: List[str] = field(default_factory=list)
    
    # Context from user
    context: Optional[str] = None
    
    # Constraints
    allowed_domains: List[str] = field(default_factory=list)
    blocked_domains: List[str] = field(default_factory=list)
    max_actions: int = 50
    timeout: float = 300.0
    
    # Options
    take_screenshots: bool = True
    record_video: bool = False
    

@dataclass
class ActionResult:
    """Result of a single action."""
    action: BrowserAction
    success: bool
    error: Optional[str] = None
    duration_ms: float = 0.0
    screenshot: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    

@dataclass
class BrowserResult:
    """Result of a browser task."""
    task_id: str
    success: bool
    
    # Actions taken
    actions: List[ActionResult] = field(default_factory=list)
    
    # Final state
    final_snapshot: Optional[PageSnapshot] = None
    
    # Extracted data
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    
    # Error information
    error: Optional[str] = None
    error_screenshot: Optional[str] = None
    
    # Metrics
    total_actions: int = 0
    total_duration_ms: float = 0.0
    
    # Recording
    video_path: Optional[str] = None


@dataclass
class BrowserConfig:
    """Configuration for browser agent."""
    # Browser settings
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    user_agent: Optional[str] = None
    
    # Security
    allow_javascript: bool = True
    allow_downloads: bool = False
    allow_popups: bool = False
    
    # Allowlist/Denylist
    allowed_domains: List[str] = field(default_factory=list)
    blocked_domains: List[str] = field(default_factory=lambda: [
        "*.exe",
        "*.msi",
        "chrome-extension://*",
    ])
    
    # Timeouts
    navigation_timeout: float = 30.0
    action_timeout: float = 10.0
    
    # Recording
    screenshots_dir: Optional[str] = None
    video_dir: Optional[str] = None

