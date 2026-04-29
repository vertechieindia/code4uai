"""Jira integration for automatic task creation from tickets."""

from __future__ import annotations
import os
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JiraConfig:
    """Jira integration configuration."""
    base_url: str = ""
    email: str = ""
    api_token: str = ""
    
    # Projects to watch
    watched_projects: List[str] = field(default_factory=list)
    
    # Issue types that trigger agent
    auto_trigger_types: List[str] = field(default_factory=lambda: [
        "Bug",
        "Task",
        "Story",
    ])
    
    # Labels that trigger agent
    trigger_labels: List[str] = field(default_factory=lambda: [
        "code4u",
        "ai-ready",
        "auto-implement",
    ])
    
    # Status for completed work
    done_status: str = "Done"
    in_progress_status: str = "In Progress"


@dataclass
class JiraIssue:
    """Parsed Jira issue."""
    key: str
    summary: str
    description: str
    issue_type: str
    status: str
    priority: str
    
    # Assignment
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    
    # Labels and components
    labels: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)
    
    # Links
    epic_key: Optional[str] = None
    parent_key: Optional[str] = None
    
    # Time
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    
    # Custom fields
    acceptance_criteria: Optional[str] = None
    technical_notes: Optional[str] = None
    
    # Raw
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImplementationPlan:
    """Plan for implementing a Jira issue."""
    issue_key: str
    
    # Analysis
    files_to_modify: List[str] = field(default_factory=list)
    new_files: List[str] = field(default_factory=list)
    
    # Complexity
    complexity: str = "medium"  # low, medium, high
    estimated_time: str = "1-2 hours"
    
    # Steps
    steps: List[str] = field(default_factory=list)
    
    # Risks
    risks: List[str] = field(default_factory=list)
    breaking_changes: bool = False
    
    # Dependencies
    blocked_by: List[str] = field(default_factory=list)


class JiraIntegration:
    """
    Jira integration for code4u.ai.
    
    Features:
    - Watch projects for new issues
    - Auto-analyze issues for implementation
    - Create implementation plans
    - Update issue status as work progresses
    - Link PRs and commits
    """
    
    def __init__(self, config: Optional[JiraConfig] = None):
        """Initialize Jira integration.
        
        Args:
            config: Jira configuration
        """
        self.config = config or JiraConfig(
            base_url=os.getenv("JIRA_BASE_URL", ""),
            email=os.getenv("JIRA_EMAIL", ""),
            api_token=os.getenv("JIRA_API_TOKEN", ""),
        )
    
    def should_auto_trigger(self, issue: JiraIssue) -> bool:
        """Check if issue should auto-trigger agent.
        
        Args:
            issue: Jira issue
            
        Returns:
            True if should trigger
        """
        # Check issue type
        if issue.issue_type not in self.config.auto_trigger_types:
            return False
        
        # Check labels
        if not any(label in self.config.trigger_labels for label in issue.labels):
            return False
        
        return True
    
    async def analyze_issue(self, issue: JiraIssue) -> ImplementationPlan:
        """Analyze a Jira issue and create implementation plan.
        
        Args:
            issue: Jira issue to analyze
            
        Returns:
            Implementation plan
        """
        plan = ImplementationPlan(issue_key=issue.key)
        
        # Parse description for technical details
        description = issue.description or ""
        
        # Look for file references
        file_pattern = r"`([^`]+\.[a-z]+)`"
        files = re.findall(file_pattern, description)
        plan.files_to_modify = files
        
        # Determine complexity
        word_count = len(description.split())
        if word_count < 50:
            plan.complexity = "low"
            plan.estimated_time = "< 1 hour"
        elif word_count < 200:
            plan.complexity = "medium"
            plan.estimated_time = "1-4 hours"
        else:
            plan.complexity = "high"
            plan.estimated_time = "4-8 hours"
        
        # Generate steps
        plan.steps = self._generate_steps(issue)
        
        # Identify risks
        if "breaking" in description.lower() or "api" in description.lower():
            plan.breaking_changes = True
            plan.risks.append("Potential breaking changes to public API")
        
        if "database" in description.lower() or "schema" in description.lower():
            plan.risks.append("Database schema changes may require migration")
        
        return plan
    
    def _generate_steps(self, issue: JiraIssue) -> List[str]:
        """Generate implementation steps from issue."""
        steps = []
        
        # Based on issue type
        if issue.issue_type == "Bug":
            steps = [
                "Reproduce the bug locally",
                "Identify root cause",
                "Implement fix",
                "Add regression test",
                "Update documentation if needed",
            ]
        elif issue.issue_type == "Story":
            steps = [
                "Review acceptance criteria",
                "Design implementation approach",
                "Implement feature",
                "Add tests",
                "Update documentation",
            ]
        else:
            steps = [
                "Analyze requirements",
                "Implement changes",
                "Test changes",
                "Request review",
            ]
        
        return steps
    
    async def handle_webhook(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle Jira webhook event.
        
        Args:
            event: Webhook event payload
            
        Returns:
            Action to take, or None
        """
        webhook_event = event.get("webhookEvent", "")
        issue_data = event.get("issue", {})
        
        if not issue_data:
            return None
        
        issue = self._parse_issue(issue_data)
        
        if webhook_event == "jira:issue_created":
            if self.should_auto_trigger(issue):
                plan = await self.analyze_issue(issue)
                return {
                    "action": "start_implementation",
                    "issue": issue,
                    "plan": plan,
                }
        
        elif webhook_event == "jira:issue_updated":
            # Check if label was added
            changelog = event.get("changelog", {}).get("items", [])
            for item in changelog:
                if item.get("field") == "labels":
                    if self.should_auto_trigger(issue):
                        plan = await self.analyze_issue(issue)
                        return {
                            "action": "start_implementation",
                            "issue": issue,
                            "plan": plan,
                        }
        
        return None
    
    def _parse_issue(self, data: Dict[str, Any]) -> JiraIssue:
        """Parse Jira API response to JiraIssue."""
        fields = data.get("fields", {})
        
        return JiraIssue(
            key=data.get("key", ""),
            summary=fields.get("summary", ""),
            description=fields.get("description", "") or "",
            issue_type=fields.get("issuetype", {}).get("name", ""),
            status=fields.get("status", {}).get("name", ""),
            priority=fields.get("priority", {}).get("name", ""),
            assignee=fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            reporter=fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
            labels=fields.get("labels", []),
            components=[c.get("name") for c in fields.get("components", [])],
            raw=data,
        )
    
    async def update_issue_status(
        self,
        issue_key: str,
        status: str,
        comment: Optional[str] = None,
    ) -> None:
        """Update issue status.
        
        Args:
            issue_key: Issue key (e.g., "PROJ-123")
            status: New status
            comment: Optional comment to add
        """
        # Would use Jira API to transition issue
        pass
    
    async def add_comment(
        self,
        issue_key: str,
        comment: str,
    ) -> None:
        """Add comment to issue.
        
        Args:
            issue_key: Issue key
            comment: Comment text (supports Jira markup)
        """
        # Would use Jira API
        pass
    
    async def link_pr(
        self,
        issue_key: str,
        pr_url: str,
        pr_title: str,
    ) -> None:
        """Link a PR to an issue.
        
        Args:
            issue_key: Issue key
            pr_url: Pull request URL
            pr_title: PR title
        """
        comment = f"🔗 *Pull Request Created*\n\n[{pr_title}|{pr_url}]"
        await self.add_comment(issue_key, comment)
    
    async def mark_done(
        self,
        issue_key: str,
        summary: str,
    ) -> None:
        """Mark issue as done.
        
        Args:
            issue_key: Issue key
            summary: Completion summary
        """
        await self.update_issue_status(issue_key, self.config.done_status)
        await self.add_comment(
            issue_key,
            f"✅ *Implemented by code4u.ai*\n\n{summary}",
        )

