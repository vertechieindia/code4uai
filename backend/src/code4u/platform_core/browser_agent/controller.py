"""Browser controller using Playwright."""

from __future__ import annotations
import asyncio
import base64
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

from .models import (
    BrowserAction,
    ActionType,
    ActionResult,
    PageSnapshot,
    ElementSelector,
    BrowserConfig,
)


class BrowserController:
    """
    Controls browser instances using Playwright.
    
    Provides low-level browser automation capabilities:
    - Navigation
    - Element interaction
    - Data extraction
    - Screenshot/recording
    """
    
    def __init__(self, config: Optional[BrowserConfig] = None):
        """Initialize browser controller.
        
        Args:
            config: Browser configuration
        """
        self.config = config or BrowserConfig()
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None
    
    async def start(self) -> None:
        """Start the browser."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is required for browser agent. "
                "Install with: pip install playwright && playwright install"
            )
        
        self._playwright = await async_playwright().start()
        
        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
        )
        
        self._context = await self._browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            user_agent=self.config.user_agent,
            java_script_enabled=self.config.allow_javascript,
        )
        
        # Set up console log capture
        self._console_logs: List[Dict[str, Any]] = []
        self._network_requests: List[Dict[str, Any]] = []
        
        self._page = await self._context.new_page()
        
        # Capture console logs
        self._page.on("console", lambda msg: self._console_logs.append({
            "type": msg.type,
            "text": msg.text,
            "timestamp": time.time(),
        }))
        
        # Capture network requests
        self._page.on("request", lambda req: self._network_requests.append({
            "url": req.url,
            "method": req.method,
            "timestamp": time.time(),
        }))
    
    async def stop(self) -> None:
        """Stop the browser."""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def execute_action(self, action: BrowserAction) -> ActionResult:
        """Execute a browser action.
        
        Args:
            action: The action to execute
            
        Returns:
            ActionResult with success/failure info
        """
        start_time = time.time()
        
        try:
            if action.type == ActionType.NAVIGATE:
                await self._navigate(action.url)
            
            elif action.type == ActionType.CLICK:
                await self._click(action.target)
            
            elif action.type == ActionType.TYPE:
                await self._type(action.target, action.text)
            
            elif action.type == ActionType.SCROLL:
                await self._scroll(action.scroll_x, action.scroll_y)
            
            elif action.type == ActionType.HOVER:
                await self._hover(action.target)
            
            elif action.type == ActionType.SELECT:
                await self._select(action.target, action.text)
            
            elif action.type == ActionType.WAIT:
                await asyncio.sleep(action.wait_time)
            
            elif action.type == ActionType.SCREENSHOT:
                screenshot = await self._screenshot()
                return ActionResult(
                    action=action,
                    success=True,
                    duration_ms=(time.time() - start_time) * 1000,
                    screenshot=screenshot,
                )
            
            elif action.type == ActionType.EXTRACT:
                data = await self._extract(action.target)
                return ActionResult(
                    action=action,
                    success=True,
                    duration_ms=(time.time() - start_time) * 1000,
                    extracted_data=data,
                )
            
            elif action.type == ActionType.EXECUTE_JS:
                result = await self._execute_js(action.script)
                return ActionResult(
                    action=action,
                    success=True,
                    duration_ms=(time.time() - start_time) * 1000,
                    extracted_data={"result": result},
                )
            
            elif action.type == ActionType.PRESS_KEY:
                await self._press_key(action.key)
            
            else:
                raise ValueError(f"Unknown action type: {action.type}")
            
            return ActionResult(
                action=action,
                success=True,
                duration_ms=(time.time() - start_time) * 1000,
            )
        
        except Exception as e:
            screenshot = None
            try:
                screenshot = await self._screenshot()
            except:
                pass
            
            return ActionResult(
                action=action,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
                screenshot=screenshot,
            )
    
    async def get_snapshot(self) -> PageSnapshot:
        """Get current page snapshot.
        
        Returns:
            PageSnapshot with current state
        """
        return PageSnapshot(
            url=self._page.url,
            title=await self._page.title(),
            html=await self._page.content(),
            text=await self._page.inner_text("body"),
            accessibility_tree=await self._get_accessibility_tree(),
            elements=await self._get_interactive_elements(),
            console_logs=self._console_logs.copy(),
            network_requests=self._network_requests.copy(),
            screenshot_base64=await self._screenshot(),
        )
    
    async def _navigate(self, url: str) -> None:
        """Navigate to URL."""
        # Check domain allowlist/blocklist
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        if self.config.blocked_domains:
            for blocked in self.config.blocked_domains:
                if blocked.replace("*.", "") in domain:
                    raise ValueError(f"Domain blocked: {domain}")
        
        if self.config.allowed_domains:
            allowed = any(
                allowed.replace("*.", "") in domain 
                for allowed in self.config.allowed_domains
            )
            if not allowed and "localhost" not in domain:
                raise ValueError(f"Domain not in allowlist: {domain}")
        
        await self._page.goto(url, timeout=self.config.navigation_timeout * 1000)
    
    async def _click(self, target: ElementSelector) -> None:
        """Click an element."""
        element = await self._find_element(target)
        await element.click(timeout=self.config.action_timeout * 1000)
    
    async def _type(self, target: ElementSelector, text: str) -> None:
        """Type text into an element."""
        element = await self._find_element(target)
        await element.fill(text, timeout=self.config.action_timeout * 1000)
    
    async def _scroll(self, x: int, y: int) -> None:
        """Scroll the page."""
        await self._page.evaluate(f"window.scrollBy({x}, {y})")
    
    async def _hover(self, target: ElementSelector) -> None:
        """Hover over an element."""
        element = await self._find_element(target)
        await element.hover(timeout=self.config.action_timeout * 1000)
    
    async def _select(self, target: ElementSelector, value: str) -> None:
        """Select an option in a dropdown."""
        element = await self._find_element(target)
        await element.select_option(value, timeout=self.config.action_timeout * 1000)
    
    async def _press_key(self, key: str) -> None:
        """Press a keyboard key."""
        await self._page.keyboard.press(key)
    
    async def _screenshot(self) -> str:
        """Take a screenshot and return base64."""
        screenshot_bytes = await self._page.screenshot()
        return base64.b64encode(screenshot_bytes).decode()
    
    async def _extract(self, target: ElementSelector) -> Dict[str, Any]:
        """Extract data from element(s)."""
        if target:
            element = await self._find_element(target)
            return {
                "text": await element.inner_text(),
                "html": await element.inner_html(),
                "attributes": await element.evaluate(
                    "el => Object.fromEntries([...el.attributes].map(a => [a.name, a.value]))"
                ),
            }
        else:
            # Extract all text
            return {
                "text": await self._page.inner_text("body"),
                "title": await self._page.title(),
                "url": self._page.url,
            }
    
    async def _execute_js(self, script: str) -> Any:
        """Execute JavaScript on the page."""
        return await self._page.evaluate(script)
    
    async def _find_element(self, target: ElementSelector):
        """Find element using selector."""
        if target.selector_type == "css":
            elements = await self._page.query_selector_all(target.selector)
        elif target.selector_type == "xpath":
            elements = await self._page.query_selector_all(f"xpath={target.selector}")
        elif target.selector_type == "text":
            elements = await self._page.query_selector_all(f"text={target.selector}")
        else:
            elements = await self._page.query_selector_all(target.selector)
        
        if not elements:
            # Try fallbacks
            for fallback in target.fallbacks:
                elements = await self._page.query_selector_all(fallback)
                if elements:
                    break
        
        if not elements:
            raise ValueError(f"Element not found: {target.selector}")
        
        if target.visible_only:
            for elem in elements:
                if await elem.is_visible():
                    return elem
            raise ValueError(f"No visible element found: {target.selector}")
        
        if target.index < len(elements):
            return elements[target.index]
        
        return elements[0]
    
    async def _get_accessibility_tree(self) -> Dict[str, Any]:
        """Get accessibility tree for the page."""
        try:
            snapshot = await self._page.accessibility.snapshot()
            return snapshot or {}
        except:
            return {}
    
    async def _get_interactive_elements(self) -> List[Dict[str, Any]]:
        """Get list of interactive elements on page."""
        script = """
        () => {
            const elements = [];
            const interactiveSelectors = 'a, button, input, select, textarea, [role="button"], [role="link"], [onclick]';
            document.querySelectorAll(interactiveSelectors).forEach((el, idx) => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    elements.push({
                        index: idx,
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText?.substring(0, 100) || '',
                        href: el.href || null,
                        type: el.type || null,
                        id: el.id || null,
                        className: el.className || null,
                        role: el.getAttribute('role'),
                        ariaLabel: el.getAttribute('aria-label'),
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                    });
                }
            });
            return elements;
        }
        """
        return await self._page.evaluate(script)

