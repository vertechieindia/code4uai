"""Jira API client."""

from __future__ import annotations
import os
import base64
from typing import Optional, Dict, Any, List
import httpx


class JiraClient:
    """HTTP client for Jira API."""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        """Initialize Jira client.
        
        Args:
            base_url: Jira instance URL
            email: User email
            api_token: API token
        """
        self.base_url = base_url or os.getenv("JIRA_BASE_URL", "")
        email = email or os.getenv("JIRA_EMAIL", "")
        api_token = api_token or os.getenv("JIRA_API_TOKEN", "")
        
        # Basic auth
        auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        
        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/rest/api/3",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
    
    async def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Get issue by key."""
        response = await self._client.get(f"/issue/{issue_key}")
        response.raise_for_status()
        return response.json()
    
    async def search_issues(
        self,
        jql: str,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search issues with JQL."""
        response = await self._client.post("/search", json={
            "jql": jql,
            "maxResults": max_results,
        })
        response.raise_for_status()
        return response.json().get("issues", [])
    
    async def add_comment(
        self,
        issue_key: str,
        body: str,
    ) -> Dict[str, Any]:
        """Add comment to issue."""
        response = await self._client.post(
            f"/issue/{issue_key}/comment",
            json={
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": body}],
                        }
                    ],
                }
            },
        )
        response.raise_for_status()
        return response.json()
    
    async def transition_issue(
        self,
        issue_key: str,
        transition_id: str,
    ) -> None:
        """Transition issue to new status."""
        response = await self._client.post(
            f"/issue/{issue_key}/transitions",
            json={"transition": {"id": transition_id}},
        )
        response.raise_for_status()
    
    async def get_transitions(self, issue_key: str) -> List[Dict[str, Any]]:
        """Get available transitions for issue."""
        response = await self._client.get(f"/issue/{issue_key}/transitions")
        response.raise_for_status()
        return response.json().get("transitions", [])
    
    async def close(self) -> None:
        """Close the client."""
        await self._client.aclose()

