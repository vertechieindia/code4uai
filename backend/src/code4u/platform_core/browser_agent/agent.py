"""Main Browser Agent - LLM-powered autonomous browser control."""

from __future__ import annotations
import asyncio
import time
import uuid
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass

from .models import (
    BrowserAction,
    ActionType,
    BrowserState,
    BrowserTask,
    BrowserResult,
    ActionResult,
    PageSnapshot,
    ElementSelector,
    BrowserConfig,
)
from .controller import BrowserController


@dataclass
class AgentThought:
    """Agent's reasoning about current state."""
    observation: str
    reasoning: str
    next_action: Optional[BrowserAction]
    is_complete: bool
    confidence: float


class BrowserAgent:
    """
    LLM-powered autonomous browser agent.
    
    Can:
    - Navigate websites
    - Fill forms
    - Click buttons
    - Extract data
    - Take screenshots
    - Verify deployments
    - Test UI functionality
    """
    
    def __init__(
        self,
        llm_client=None,
        config: Optional[BrowserConfig] = None,
        on_action: Optional[Callable[[BrowserAction], None]] = None,
        on_state_change: Optional[Callable[[BrowserState], None]] = None,
    ):
        """Initialize browser agent.
        
        Args:
            llm_client: LLM client for decision making
            config: Browser configuration
            on_action: Callback for each action
            on_state_change: Callback for state changes
        """
        self.llm_client = llm_client
        self.config = config or BrowserConfig()
        self.controller = BrowserController(self.config)
        self.on_action = on_action
        self.on_state_change = on_state_change
        
        self._state = BrowserState.IDLE
        self._history: List[ActionResult] = []
    
    @property
    def state(self) -> BrowserState:
        """Current agent state."""
        return self._state
    
    def _set_state(self, state: BrowserState) -> None:
        """Set state and notify callback."""
        self._state = state
        if self.on_state_change:
            self.on_state_change(state)
    
    async def start(self) -> None:
        """Start the browser agent."""
        await self.controller.start()
        self._set_state(BrowserState.IDLE)
    
    async def stop(self) -> None:
        """Stop the browser agent."""
        await self.controller.stop()
        self._set_state(BrowserState.IDLE)
    
    async def execute_task(self, task: BrowserTask) -> BrowserResult:
        """Execute a browser task autonomously.
        
        Args:
            task: The task to execute
            
        Returns:
            BrowserResult with outcome
        """
        start_time = time.time()
        self._history = []
        
        try:
            # Navigate to URL if provided
            if task.url:
                self._set_state(BrowserState.NAVIGATING)
                result = await self.controller.execute_action(
                    BrowserAction(type=ActionType.NAVIGATE, url=task.url)
                )
                self._history.append(result)
                
                if not result.success:
                    return BrowserResult(
                        task_id=task.id,
                        success=False,
                        actions=self._history,
                        error=f"Failed to navigate: {result.error}",
                    )
            
            # Main agent loop
            action_count = 0
            while action_count < task.max_actions:
                self._set_state(BrowserState.INTERACTING)
                
                # Get current page state
                snapshot = await self.controller.get_snapshot()
                
                # Ask LLM what to do next
                thought = await self._think(task, snapshot, self._history)
                
                if thought.is_complete:
                    self._set_state(BrowserState.COMPLETE)
                    return BrowserResult(
                        task_id=task.id,
                        success=True,
                        actions=self._history,
                        final_snapshot=snapshot,
                        total_actions=action_count,
                        total_duration_ms=(time.time() - start_time) * 1000,
                    )
                
                if thought.next_action:
                    # Notify callback
                    if self.on_action:
                        self.on_action(thought.next_action)
                    
                    # Execute action
                    result = await self.controller.execute_action(thought.next_action)
                    self._history.append(result)
                    action_count += 1
                    
                    if not result.success:
                        # Retry logic could go here
                        pass
                    
                    # Wait a bit between actions
                    await asyncio.sleep(0.5)
                else:
                    # No action to take but not complete - might be stuck
                    await asyncio.sleep(1.0)
            
            # Max actions reached
            self._set_state(BrowserState.COMPLETE)
            return BrowserResult(
                task_id=task.id,
                success=False,
                actions=self._history,
                error="Max actions reached without completing task",
                total_actions=action_count,
                total_duration_ms=(time.time() - start_time) * 1000,
            )
        
        except Exception as e:
            self._set_state(BrowserState.ERROR)
            return BrowserResult(
                task_id=task.id,
                success=False,
                actions=self._history,
                error=str(e),
                total_duration_ms=(time.time() - start_time) * 1000,
            )
    
    async def _think(
        self,
        task: BrowserTask,
        snapshot: PageSnapshot,
        history: List[ActionResult],
    ) -> AgentThought:
        """Use LLM to decide next action.
        
        Args:
            task: Current task
            snapshot: Current page state
            history: Action history
            
        Returns:
            AgentThought with next action
        """
        if not self.llm_client:
            # Fallback: simple heuristic-based agent
            return self._heuristic_think(task, snapshot, history)
        
        # Build prompt for LLM
        prompt = self._build_prompt(task, snapshot, history)
        
        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                max_tokens=500,
                temperature=0.2,
            )
            
            return self._parse_llm_response(response.text)
        except Exception as e:
            return AgentThought(
                observation=f"LLM error: {e}",
                reasoning="Falling back to heuristic",
                next_action=None,
                is_complete=False,
                confidence=0.0,
            )
    
    def _build_prompt(
        self,
        task: BrowserTask,
        snapshot: PageSnapshot,
        history: List[ActionResult],
    ) -> str:
        """Build prompt for LLM decision making."""
        # Summarize interactive elements
        elements_summary = "\n".join([
            f"[{e['index']}] {e['tag']}: {e['text'][:50]}"
            for e in snapshot.elements[:20]
        ])
        
        # Summarize history
        history_summary = "\n".join([
            f"- {r.action.type.value}: {'✓' if r.success else '✗'}"
            for r in history[-5:]
        ])
        
        return f"""You are a browser automation agent. Complete the following task:

TASK: {task.description}

CURRENT PAGE:
- URL: {snapshot.url}
- Title: {snapshot.title}

INTERACTIVE ELEMENTS:
{elements_summary}

RECENT ACTIONS:
{history_summary}

SUCCESS CRITERIA:
{chr(10).join(task.success_criteria) if task.success_criteria else "Not specified"}

Decide what to do next. Respond in this format:
OBSERVATION: What you see on the page
REASONING: Why you're taking this action
ACTION: One of [click, type, scroll, navigate, wait, extract, complete]
TARGET: Element index or selector (if applicable)
VALUE: Text to type or URL (if applicable)
COMPLETE: true/false

If the task is complete, set COMPLETE to true and explain why in REASONING.
"""
    
    def _parse_llm_response(self, response: str) -> AgentThought:
        """Parse LLM response into AgentThought."""
        lines = response.strip().split("\n")
        parsed = {}
        
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                parsed[key.strip().upper()] = value.strip()
        
        is_complete = parsed.get("COMPLETE", "false").lower() == "true"
        
        action = None
        if not is_complete:
            action_type = parsed.get("ACTION", "").lower()
            target = parsed.get("TARGET", "")
            value = parsed.get("VALUE", "")
            
            if action_type == "click" and target:
                action = BrowserAction(
                    type=ActionType.CLICK,
                    target=ElementSelector(selector=target),
                )
            elif action_type == "type" and target and value:
                action = BrowserAction(
                    type=ActionType.TYPE,
                    target=ElementSelector(selector=target),
                    text=value,
                )
            elif action_type == "navigate" and value:
                action = BrowserAction(
                    type=ActionType.NAVIGATE,
                    url=value,
                )
            elif action_type == "scroll":
                action = BrowserAction(
                    type=ActionType.SCROLL,
                    scroll_y=300,
                )
            elif action_type == "wait":
                action = BrowserAction(
                    type=ActionType.WAIT,
                    wait_time=2.0,
                )
        
        return AgentThought(
            observation=parsed.get("OBSERVATION", ""),
            reasoning=parsed.get("REASONING", ""),
            next_action=action,
            is_complete=is_complete,
            confidence=0.8 if action or is_complete else 0.3,
        )
    
    def _heuristic_think(
        self,
        task: BrowserTask,
        snapshot: PageSnapshot,
        history: List[ActionResult],
    ) -> AgentThought:
        """Simple heuristic-based decision making (fallback)."""
        # Check success criteria
        for criterion in task.success_criteria:
            if criterion.lower() in snapshot.text.lower():
                return AgentThought(
                    observation=f"Found: {criterion}",
                    reasoning="Success criterion met",
                    next_action=None,
                    is_complete=True,
                    confidence=0.9,
                )
        
        # Look for obvious next actions
        elements = snapshot.elements
        
        # Look for submit buttons
        for elem in elements:
            if elem["tag"] == "button" and any(
                word in elem["text"].lower() 
                for word in ["submit", "send", "continue", "next"]
            ):
                return AgentThought(
                    observation=f"Found button: {elem['text']}",
                    reasoning="Clicking action button",
                    next_action=BrowserAction(
                        type=ActionType.CLICK,
                        target=ElementSelector(
                            selector=f"[id='{elem['id']}']" if elem["id"] else f"button:has-text('{elem['text']}')",
                        ),
                    ),
                    is_complete=False,
                    confidence=0.6,
                )
        
        # If we've done many actions with no progress, give up
        if len(history) > 10:
            return AgentThought(
                observation="Many actions taken",
                reasoning="Unable to complete task",
                next_action=None,
                is_complete=True,
                confidence=0.3,
            )
        
        # Default: scroll to see more
        return AgentThought(
            observation="Looking for relevant elements",
            reasoning="Scrolling to find more content",
            next_action=BrowserAction(
                type=ActionType.SCROLL,
                scroll_y=300,
            ),
            is_complete=False,
            confidence=0.4,
        )
    
    async def navigate(self, url: str) -> ActionResult:
        """Navigate to a URL.
        
        Args:
            url: URL to navigate to
            
        Returns:
            ActionResult
        """
        action = BrowserAction(type=ActionType.NAVIGATE, url=url)
        return await self.controller.execute_action(action)
    
    async def click(self, selector: str) -> ActionResult:
        """Click an element.
        
        Args:
            selector: CSS selector
            
        Returns:
            ActionResult
        """
        action = BrowserAction(
            type=ActionType.CLICK,
            target=ElementSelector(selector=selector),
        )
        return await self.controller.execute_action(action)
    
    async def type_text(self, selector: str, text: str) -> ActionResult:
        """Type text into an element.
        
        Args:
            selector: CSS selector
            text: Text to type
            
        Returns:
            ActionResult
        """
        action = BrowserAction(
            type=ActionType.TYPE,
            target=ElementSelector(selector=selector),
            text=text,
        )
        return await self.controller.execute_action(action)
    
    async def screenshot(self) -> str:
        """Take a screenshot.
        
        Returns:
            Base64 encoded screenshot
        """
        result = await self.controller.execute_action(
            BrowserAction(type=ActionType.SCREENSHOT)
        )
        return result.screenshot or ""
    
    async def get_snapshot(self) -> PageSnapshot:
        """Get current page snapshot.
        
        Returns:
            PageSnapshot
        """
        return await self.controller.get_snapshot()

