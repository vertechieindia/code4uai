"""Jira webhook handler."""

from __future__ import annotations
from typing import Dict, Any, Optional

from .integration import JiraIntegration


class JiraWebhookHandler:
    """Handler for Jira webhooks."""
    
    def __init__(self, integration: Optional[JiraIntegration] = None):
        """Initialize handler.
        
        Args:
            integration: Jira integration instance
        """
        self.integration = integration or JiraIntegration()
    
    async def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming Jira webhook.
        
        Args:
            payload: Webhook payload
            
        Returns:
            Response
        """
        result = await self.integration.handle_webhook(payload)
        
        if result and result.get("action") == "start_implementation":
            # Would trigger the agent
            return {
                "status": "triggered",
                "issue_key": result["issue"].key,
                "plan": {
                    "complexity": result["plan"].complexity,
                    "estimated_time": result["plan"].estimated_time,
                    "steps": result["plan"].steps,
                },
            }
        
        return {"status": "ignored"}

