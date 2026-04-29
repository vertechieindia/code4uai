"""Jira/Atlassian integration for project management and issue tracking."""

from __future__ import annotations
import os
import base64
from typing import Optional, List, Dict, Any
import httpx

from ..base import TaskIntegration, IntegrationConfig, Requirement
from ..registry import register_integration


@register_integration("jira")
class JiraIntegration(TaskIntegration):
    """
    Jira Integration for code4u.ai.
    
    Features:
    - Watch for new issues
    - Create issues from requirements
    - Update issue status as work progresses
    - Add comments with implementation details
    - Link PRs and commits
    - Transition workflow states
    """
    
    name = "jira"
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        super().__init__(config)
        self.base_url = os.getenv("JIRA_BASE_URL", "")  # e.g., https://company.atlassian.net
        self.email = os.getenv("JIRA_EMAIL", "")
        self.api_token = os.getenv("JIRA_API_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def connect(self) -> bool:
        auth = base64.b64encode(f"{self.email}:{self.api_token}".encode()).decode()
        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/rest/api/3",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
            },
        )
        return True
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/myself")
            user = response.json()
            return {"status": "healthy", "user": user.get("displayName")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get an issue from Jira."""
        response = await self._client.get(f"/issue/{task_id}")
        response.raise_for_status()
        return response.json()
    
    async def create_task(
        self,
        title: str,
        description: str,
        project_id: Optional[str] = None,  # Project key, e.g., "PROJ"
        issue_type: str = "Task",
        **kwargs,
    ) -> Dict[str, Any]:
        """Create an issue in Jira."""
        # Convert description to Jira's Atlassian Document Format
        adf_description = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description}]
                }
            ]
        }
        
        data = {
            "fields": {
                "project": {"key": project_id},
                "summary": title,
                "description": adf_description,
                "issuetype": {"name": issue_type},
                **kwargs,
            }
        }
        
        response = await self._client.post("/issue", json=data)
        response.raise_for_status()
        return response.json()
    
    async def update_task(self, task_id: str, **updates) -> Dict[str, Any]:
        """Update an issue in Jira."""
        data = {"fields": updates}
        response = await self._client.put(f"/issue/{task_id}", json=data)
        response.raise_for_status()
        return {"status": "updated", "key": task_id}
    
    async def add_comment(self, task_id: str, comment: str) -> Dict[str, Any]:
        """Add a comment to an issue."""
        adf_comment = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}]
                    }
                ]
            }
        }
        response = await self._client.post(f"/issue/{task_id}/comment", json=adf_comment)
        response.raise_for_status()
        return response.json()
    
    async def transition_issue(
        self,
        task_id: str,
        transition_name: str,
    ) -> Dict[str, Any]:
        """Transition an issue to a new status."""
        # Get available transitions
        response = await self._client.get(f"/issue/{task_id}/transitions")
        transitions = response.json().get("transitions", [])
        
        # Find matching transition
        transition_id = None
        for t in transitions:
            if t["name"].lower() == transition_name.lower():
                transition_id = t["id"]
                break
        
        if not transition_id:
            return {"error": f"Transition not found: {transition_name}"}
        
        # Execute transition
        data = {"transition": {"id": transition_id}}
        response = await self._client.post(f"/issue/{task_id}/transitions", json=data)
        response.raise_for_status()
        
        return {"status": "transitioned", "to": transition_name}
    
    async def search_issues(
        self,
        jql: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search issues using JQL."""
        params = {"jql": jql, "maxResults": limit}
        response = await self._client.get("/search", params=params)
        response.raise_for_status()
        return response.json().get("issues", [])
    
    async def get_new_tasks(
        self,
        project_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get new/unassigned tasks."""
        jql = "status = 'To Do' OR status = 'Open'"
        if project_key:
            jql = f"project = {project_key} AND ({jql})"
        return await self.search_issues(jql)
    
    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get all accessible projects."""
        response = await self._client.get("/project")
        response.raise_for_status()
        return response.json()
    
    async def link_pr(
        self,
        task_id: str,
        pr_url: str,
        pr_title: str,
    ) -> Dict[str, Any]:
        """Link a pull request to an issue."""
        # Add as remote link
        data = {
            "object": {
                "url": pr_url,
                "title": pr_title,
                "icon": {"url16x16": "https://github.com/favicon.ico"},
            }
        }
        response = await self._client.post(f"/issue/{task_id}/remotelink", json=data)
        response.raise_for_status()
        return response.json()
    
    async def mark_done(
        self,
        task_id: str,
        resolution_comment: str,
    ) -> Dict[str, Any]:
        """Mark an issue as done."""
        # Add resolution comment
        await self.add_comment(task_id, resolution_comment)
        
        # Transition to Done
        return await self.transition_issue(task_id, "Done")
    
    async def to_requirement(self, task: Dict[str, Any]) -> Requirement:
        """Convert Jira issue to Requirement."""
        import uuid
        
        fields = task.get("fields", {})
        
        # Extract description text from ADF
        description = ""
        desc_content = fields.get("description", {})
        if isinstance(desc_content, dict):
            for block in desc_content.get("content", []):
                for item in block.get("content", []):
                    if item.get("type") == "text":
                        description += item.get("text", "")
        
        # Map Jira priority
        priority_map = {
            "Highest": "critical",
            "High": "high",
            "Medium": "medium",
            "Low": "low",
            "Lowest": "low",
        }
        jira_priority = fields.get("priority", {}).get("name", "Medium")
        
        # Map issue type
        issue_type = fields.get("issuetype", {}).get("name", "Task").lower()
        type_map = {
            "bug": "bug",
            "story": "feature",
            "epic": "feature",
            "task": "task",
            "sub-task": "task",
            "improvement": "enhancement",
        }
        
        return Requirement(
            id=str(uuid.uuid4()),
            title=fields.get("summary", ""),
            description=description,
            source_type="jira",
            source_id=task.get("key", ""),
            source_url=f"{self.base_url}/browse/{task.get('key')}",
            type=type_map.get(issue_type, "task"),
            priority=priority_map.get(jira_priority, "medium"),
            assignee=fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
        )
