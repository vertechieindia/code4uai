"""API routes for all integrations.

Day 6: Added ``GET /integrations/issues`` for fetching open issues
from Jira, Linear, or GitHub Issues.
"""

from __future__ import annotations
import os
from datetime import datetime
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Query, Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

import structlog

from code4u.interfaces.integrations import registry, IntegrationConfig


router = APIRouter(prefix="/integrations", tags=["integrations"])


# ============= Request/Response Models =============

class ConfigureIntegrationRequest(BaseModel):
    """Request to configure an integration."""
    name: str
    enabled: bool = True
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    settings: Dict[str, Any] = {}


class IntegrationInfo(BaseModel):
    """Integration info."""
    name: str
    type: str
    enabled: bool = False
    health: Optional[str] = None


class RequirementFromSource(BaseModel):
    """Request to get requirements from a source."""
    source: str  # Integration name
    query: Optional[str] = None
    project_id: Optional[str] = None
    limit: int = 50


class CreateTaskRequest(BaseModel):
    """Request to create a task in an integration."""
    integration: str
    title: str
    description: str
    project_id: Optional[str] = None
    extra: Dict[str, Any] = {}


class UpdateTaskRequest(BaseModel):
    """Request to update a task."""
    integration: str
    task_id: str
    updates: Dict[str, Any]


class CommentRequest(BaseModel):
    """Request to add a comment."""
    integration: str
    task_id: str
    comment: str


# ============= Integration Management =============

@router.get("/available")
async def list_available_integrations() -> List[Dict[str, Any]]:
    """List all available integrations."""
    return registry.list_available()


@router.post("/configure")
async def configure_integration(
    request: ConfigureIntegrationRequest,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, str]:
    """Configure an integration for a tenant."""
    config = IntegrationConfig(
        enabled=request.enabled,
        api_key=request.api_key,
        api_secret=request.api_secret,
        base_url=request.base_url,
        tenant_id=x_tenant_id,
        settings=request.settings,
    )
    
    registry.configure(x_tenant_id, request.name, config)
    
    return {"status": "configured", "integration": request.name}


@router.get("/configured")
async def list_configured_integrations(
    x_tenant_id: str = Header(default="default"),
) -> List[IntegrationInfo]:
    """List configured integrations for a tenant."""
    instances = await registry.get_all_instances(x_tenant_id)
    
    return [
        IntegrationInfo(
            name=i.name,
            type=i.type.value if hasattr(i, "type") else "unknown",
            enabled=True,
        )
        for i in instances
    ]


@router.get("/health")
async def check_all_health(
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Check health of all integrations."""
    return await registry.health_check_all(x_tenant_id)


@router.get("/{name}/health")
async def check_integration_health(
    name: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Check health of a specific integration."""
    instance = await registry.get_instance(x_tenant_id, name)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Integration not found: {name}")
    
    return await instance.health_check()


# ============= Task Operations =============

@router.post("/tasks/create")
async def create_task(
    request: CreateTaskRequest,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Create a task in an integration."""
    instance = await registry.get_instance(x_tenant_id, request.integration)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Integration not found: {request.integration}")
    
    if not hasattr(instance, "create_task"):
        raise HTTPException(status_code=400, detail=f"Integration does not support tasks")
    
    return await instance.create_task(
        title=request.title,
        description=request.description,
        project_id=request.project_id,
        **request.extra,
    )


@router.post("/tasks/update")
async def update_task(
    request: UpdateTaskRequest,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Update a task in an integration."""
    instance = await registry.get_instance(x_tenant_id, request.integration)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Integration not found: {request.integration}")
    
    if not hasattr(instance, "update_task"):
        raise HTTPException(status_code=400, detail=f"Integration does not support tasks")
    
    return await instance.update_task(request.task_id, **request.updates)


@router.post("/tasks/comment")
async def add_comment(
    request: CommentRequest,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Add a comment to a task."""
    instance = await registry.get_instance(x_tenant_id, request.integration)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Integration not found: {request.integration}")
    
    if not hasattr(instance, "add_comment"):
        raise HTTPException(status_code=400, detail=f"Integration does not support comments")
    
    return await instance.add_comment(request.task_id, request.comment)


@router.get("/tasks/{integration}/{task_id}")
async def get_task(
    integration: str,
    task_id: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Get a task from an integration."""
    instance = await registry.get_instance(x_tenant_id, integration)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Integration not found: {integration}")
    
    if not hasattr(instance, "get_task"):
        raise HTTPException(status_code=400, detail=f"Integration does not support tasks")
    
    return await instance.get_task(task_id)


# ============= Requirement Extraction =============

@router.post("/requirements/fetch")
async def fetch_requirements(
    request: RequirementFromSource,
    x_tenant_id: str = Header(default="default"),
) -> List[Dict[str, Any]]:
    """Fetch requirements from a source integration."""
    instance = await registry.get_instance(x_tenant_id, request.source)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Integration not found: {request.source}")
    
    # Get tasks/items based on integration type
    tasks = []
    
    if hasattr(instance, "get_new_tasks"):
        tasks = await instance.get_new_tasks()
    elif hasattr(instance, "search_tasks") and request.query:
        tasks = await instance.search_tasks(request.query, limit=request.limit)
    elif hasattr(instance, "get_tasks_from_project") and request.project_id:
        tasks = await instance.get_tasks_from_project(request.project_id)
    
    # Convert to requirements
    requirements = []
    if hasattr(instance, "to_requirement"):
        for task in tasks[:request.limit]:
            req = await instance.to_requirement(task)
            requirements.append({
                "id": req.id,
                "title": req.title,
                "description": req.description,
                "source_type": req.source_type,
                "source_id": req.source_id,
                "source_url": req.source_url,
                "type": req.type,
                "priority": req.priority,
            })
    
    return requirements


# ============= Communication =============

@router.post("/message/send")
async def send_message(
    integration: str,
    channel_id: str,
    message: str,
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Send a message to a communication channel."""
    instance = await registry.get_instance(x_tenant_id, integration)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Integration not found: {integration}")
    
    if not hasattr(instance, "send_message"):
        raise HTTPException(status_code=400, detail=f"Integration does not support messaging")
    
    return await instance.send_message(channel_id, message)


# ============= External Issue Tracker =============

# In-memory issue cache for configured trackers
_issues_cache: Dict[str, List[Dict[str, Any]]] = {}


class IssuesConfigRequest(BaseModel):
    """Configure which issue tracker to use."""
    provider: str  # "jira", "linear", "github"
    base_url: str = ""
    api_token: str = ""
    project_key: str = ""
    repo: str = ""


@router.post("/issues/configure")
async def configure_issues(request: IssuesConfigRequest):
    """Configure issue tracker credentials."""
    _issues_cache["__config__"] = [{
        "provider": request.provider,
        "base_url": request.base_url,
        "api_token": request.api_token,
        "project_key": request.project_key,
        "repo": request.repo,
    }]
    return {"status": "configured", "provider": request.provider}


@router.get("/issues")
async def list_issues(
    provider: str = Query("auto", description="jira, linear, github, or auto"),
    repo: str = Query("", description="GitHub repo (owner/name) for GitHub issues"),
    project_key: str = Query("", description="Jira project key"),
    limit: int = Query(25, description="Max issues to return"),
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, Any]:
    """Fetch open issues from the configured issue tracker.

    Supports Jira, Linear, and GitHub Issues. Falls back to GitHub
    if a token is available, or returns demo issues for development.
    """
    config = (_issues_cache.get("__config__") or [{}])[0] if "__config__" in _issues_cache else {}
    effective_provider = provider if provider != "auto" else config.get("provider", "github")

    if effective_provider == "github":
        return await _fetch_github_issues(repo or config.get("repo", ""), limit)

    if effective_provider == "jira":
        return await _fetch_jira_issues(
            base_url=config.get("base_url", ""),
            api_token=config.get("api_token", ""),
            project_key=project_key or config.get("project_key", ""),
            limit=limit,
        )

    if effective_provider == "linear":
        return await _fetch_linear_issues(
            api_token=config.get("api_token", ""),
            limit=limit,
        )

    return _demo_issues()


async def _fetch_github_issues(repo: str, limit: int) -> Dict[str, Any]:
    """Fetch issues from GitHub Issues API."""
    gh_token = ""
    try:
        from code4u.interfaces.api.routes.auth import get_github_token
        gh_token = get_github_token() or ""
    except Exception:
        pass

    if not gh_token:
        gh_token = os.environ.get("CODE4U_GITHUB_TOKEN", "")

    if not repo:
        if gh_token:
            import httpx
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://api.github.com/user/repos",
                    params={"sort": "updated", "per_page": 1},
                    headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
                    timeout=10,
                )
            if res.status_code == 200:
                repos = res.json()
                if repos:
                    repo = repos[0].get("full_name", "")

    if not repo:
        return _demo_issues()

    import httpx
    headers_gh: Dict[str, str] = {"Accept": "application/vnd.github+json"}
    if gh_token:
        headers_gh["Authorization"] = f"Bearer {gh_token}"

    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://api.github.com/repos/{repo}/issues",
            params={"state": "open", "per_page": limit, "sort": "updated"},
            headers=headers_gh,
            timeout=15,
        )

    if res.status_code != 200:
        return _demo_issues()

    raw_issues = res.json()
    issues = []
    for iss in raw_issues:
        if iss.get("pull_request"):
            continue
        labels = [l.get("name", "") for l in iss.get("labels", [])]
        priority = "high" if "bug" in labels else "medium" if "enhancement" in labels else "low"
        issues.append({
            "id": str(iss.get("number", "")),
            "key": f"#{iss['number']}",
            "title": iss.get("title", ""),
            "description": (iss.get("body") or "")[:300],
            "status": "open",
            "priority": priority,
            "type": "bug" if "bug" in labels else "feature" if "enhancement" in labels else "task",
            "assignee": (iss.get("assignee") or {}).get("login", ""),
            "labels": labels,
            "url": iss.get("html_url", ""),
            "provider": "github",
            "repo": repo,
            "created_at": iss.get("created_at", ""),
            "updated_at": iss.get("updated_at", ""),
        })

    return {"issues": issues[:limit], "total": len(issues), "provider": "github", "repo": repo}


async def _fetch_jira_issues(
    base_url: str, api_token: str, project_key: str, limit: int
) -> Dict[str, Any]:
    """Fetch issues from Jira REST API."""
    if not base_url or not api_token:
        return _demo_issues()

    import httpx

    jql = f"project={project_key} AND status != Done ORDER BY updated DESC" if project_key else "status != Done ORDER BY updated DESC"

    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{base_url.rstrip('/')}/rest/api/3/search",
            params={"jql": jql, "maxResults": limit, "fields": "summary,status,priority,issuetype,assignee,labels,created,updated"},
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json",
            },
            timeout=15,
        )

    if res.status_code != 200:
        return _demo_issues()

    data = res.json()
    issues = []
    for iss in data.get("issues", []):
        fields = iss.get("fields", {})
        issues.append({
            "id": iss.get("id", ""),
            "key": iss.get("key", ""),
            "title": fields.get("summary", ""),
            "description": "",
            "status": (fields.get("status") or {}).get("name", ""),
            "priority": (fields.get("priority") or {}).get("name", "Medium"),
            "type": (fields.get("issuetype") or {}).get("name", "Task"),
            "assignee": (fields.get("assignee") or {}).get("displayName", ""),
            "labels": fields.get("labels", []),
            "url": f"{base_url}/browse/{iss.get('key', '')}",
            "provider": "jira",
            "created_at": fields.get("created", ""),
            "updated_at": fields.get("updated", ""),
        })

    return {"issues": issues, "total": data.get("total", 0), "provider": "jira"}


async def _fetch_linear_issues(api_token: str, limit: int) -> Dict[str, Any]:
    """Fetch issues from Linear GraphQL API."""
    if not api_token:
        return _demo_issues()

    import httpx

    query = """
    query($first: Int!) {
      issues(first: $first, filter: { state: { type: { nin: ["completed", "canceled"] } } }, orderBy: updatedAt) {
        nodes {
          id identifier title description state { name } priority priorityLabel
          assignee { name } labels { nodes { name } } url createdAt updatedAt
        }
      }
    }
    """

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.linear.app/graphql",
            json={"query": query, "variables": {"first": limit}},
            headers={"Authorization": api_token, "Content-Type": "application/json"},
            timeout=15,
        )

    if res.status_code != 200:
        return _demo_issues()

    data = res.json()
    nodes = data.get("data", {}).get("issues", {}).get("nodes", [])
    issues = []
    for n in nodes:
        issues.append({
            "id": n.get("id", ""),
            "key": n.get("identifier", ""),
            "title": n.get("title", ""),
            "description": (n.get("description") or "")[:300],
            "status": (n.get("state") or {}).get("name", ""),
            "priority": n.get("priorityLabel", "Medium"),
            "type": "task",
            "assignee": (n.get("assignee") or {}).get("name", ""),
            "labels": [l.get("name", "") for l in (n.get("labels") or {}).get("nodes", [])],
            "url": n.get("url", ""),
            "provider": "linear",
            "created_at": n.get("createdAt", ""),
            "updated_at": n.get("updatedAt", ""),
        })

    return {"issues": issues, "total": len(issues), "provider": "linear"}


def _demo_issues() -> Dict[str, Any]:
    """Return demo issues for development when no tracker is configured."""
    return {
        "issues": [
            {"id": "1", "key": "DEMO-1", "title": "Fix login redirect loop on Safari", "description": "Users on Safari get stuck in a redirect loop after OAuth.", "status": "open", "priority": "high", "type": "bug", "assignee": "", "labels": ["bug", "auth"], "url": "", "provider": "demo", "created_at": "", "updated_at": ""},
            {"id": "2", "key": "DEMO-2", "title": "Add dark mode support to dashboard", "description": "Implement dark/light mode toggle in the settings page.", "status": "open", "priority": "medium", "type": "feature", "assignee": "", "labels": ["enhancement", "ui"], "url": "", "provider": "demo", "created_at": "", "updated_at": ""},
            {"id": "3", "key": "DEMO-3", "title": "API rate limiting for /api/v1/chat", "description": "The chat endpoint needs rate limiting to prevent abuse.", "status": "in_progress", "priority": "high", "type": "task", "assignee": "", "labels": ["security"], "url": "", "provider": "demo", "created_at": "", "updated_at": ""},
            {"id": "4", "key": "DEMO-4", "title": "Refactor UserService to use repository pattern", "description": "Extract database logic from UserService into a dedicated repository class.", "status": "open", "priority": "low", "type": "task", "assignee": "", "labels": ["refactor", "backend"], "url": "", "provider": "demo", "created_at": "", "updated_at": ""},
            {"id": "5", "key": "DEMO-5", "title": "Memory leak in file watcher on large repos", "description": "The watcher holds references to deleted files causing gradual memory growth.", "status": "open", "priority": "high", "type": "bug", "assignee": "", "labels": ["bug", "performance"], "url": "", "provider": "demo", "created_at": "", "updated_at": ""},
        ],
        "total": 5,
        "provider": "demo",
        "note": "These are demo issues. Configure a real issue tracker via POST /integrations/issues/configure.",
    }


# ============= Day 16: GitHub/GitLab PR Integration =============

logger = structlog.get_logger("integrations")


class PRCommentRequest(BaseModel):
    """Request to post Titan Audit Report to a PR."""
    repo: str = Field(..., description="owner/repo format")
    pr_number: int = Field(..., description="PR number")
    report: str = Field("", description="Markdown report to post. If empty, generates fresh scan.")
    provider: str = Field("github", description="github or gitlab")
    gitlab_url: str = Field("", description="GitLab instance URL")
    gitlab_token: str = Field("", description="GitLab personal access token")


class PRCommentResponse(BaseModel):
    status: str
    provider: str
    pr_number: int
    comment_id: int = 0
    comment_url: str = ""


def _get_github_token_for_pr() -> str:
    """Get GitHub token for PR operations."""
    try:
        from code4u.interfaces.api.routes.auth import get_github_token
        return get_github_token() or ""
    except Exception:
        pass
    return os.environ.get("CODE4U_GITHUB_TOKEN", "")


def _wrap_report_body(report: str) -> str:
    """Wrap report in branded header."""
    return f"## 🛡️ code4u.ai — Titan Security Audit\n\n{report}\n\n---\n*Generated by code4u.ai Guardian Fortress*"


@router.post("/pr/comment", response_model=PRCommentResponse)
async def post_pr_comment(request: PRCommentRequest) -> PRCommentResponse:
    """Post the Titan Audit Report as a markdown comment to a GitHub or GitLab PR."""
    report = request.report
    if not report:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        report = f"*Auto-generated summary at {ts}*\n\nNo scan data provided. Run a full scan to generate a detailed audit report."

    body = _wrap_report_body(report)

    if request.provider == "github":
        token = _get_github_token_for_pr()
        if not token:
            raise HTTPException(status_code=401, detail="GitHub token required. Set CODE4U_GITHUB_TOKEN or connect GitHub OAuth.")
        url = f"https://api.github.com/repos/{request.repo}/issues/{request.pr_number}/comments"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json={"body": body},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        if resp.status_code != 201:
            logger.warning("github_pr_comment_failed", status=resp.status_code, body=resp.text)
            raise HTTPException(status_code=resp.status_code, detail=resp.text or "Failed to post GitHub comment")
        data = resp.json()
        comment_url = data.get("html_url", "")
        comment_id = data.get("id", 0)
        return PRCommentResponse(
            status="posted",
            provider="github",
            pr_number=request.pr_number,
            comment_id=comment_id,
            comment_url=comment_url,
        )

    if request.provider == "gitlab":
        if not request.gitlab_url or not request.gitlab_token:
            raise HTTPException(status_code=400, detail="GitLab URL and token required for GitLab provider.")
        encoded_repo = quote(request.repo, safe="")
        base = request.gitlab_url.rstrip("/")
        url = f"{base}/api/v4/projects/{encoded_repo}/merge_requests/{request.pr_number}/notes"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json={"body": body},
                headers={"PRIVATE-TOKEN": request.gitlab_token},
            )
        if resp.status_code not in (200, 201):
            logger.warning("gitlab_pr_comment_failed", status=resp.status_code, body=resp.text)
            raise HTTPException(status_code=resp.status_code, detail=resp.text or "Failed to post GitLab comment")
        data = resp.json()
        comment_id = data.get("id", 0)
        comment_url = data.get("web_url", "")
        return PRCommentResponse(
            status="posted",
            provider="gitlab",
            pr_number=request.pr_number,
            comment_id=comment_id,
            comment_url=comment_url,
        )

    raise HTTPException(status_code=400, detail="provider must be github or gitlab")


@router.get("/pr/status/{provider}/{repo:path}/{pr_number}")
async def get_pr_status(
    provider: str = Path(..., description="github or gitlab"),
    repo: str = Path(..., description="owner/repo"),
    pr_number: int = Path(..., description="PR number"),
    gitlab_url: str = Query("", description="GitLab instance URL"),
    gitlab_token: str = Query("", description="GitLab personal access token"),
) -> Dict[str, Any]:
    """Get PR status (open/merged/closed) from GitHub or GitLab."""
    if provider == "github":
        token = _get_github_token_for_pr()
        headers: Dict[str, str] = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text or "Failed to fetch PR")
        data = resp.json()
        state = data.get("state", "unknown")
        if data.get("merged"):
            state = "merged"
        return {
            "status": state,
            "title": data.get("title", ""),
            "author": (data.get("user") or {}).get("login", ""),
            "labels": [l.get("name", "") for l in data.get("labels", [])],
            "url": data.get("html_url", ""),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
        }

    if provider == "gitlab":
        if not gitlab_url or not gitlab_token:
            raise HTTPException(status_code=400, detail="gitlab_url and gitlab_token query params required")
        encoded_repo = quote(repo, safe="")
        base = gitlab_url.rstrip("/")
        url = f"{base}/api/v4/projects/{encoded_repo}/merge_requests/{pr_number}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers={"PRIVATE-TOKEN": gitlab_token})
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text or "Failed to fetch MR")
        data = resp.json()
        state = data.get("state", "unknown")
        if data.get("merge_status") == "can_be_merged" and data.get("merged_at"):
            state = "merged"
        return {
            "status": state,
            "title": data.get("title", ""),
            "author": (data.get("author") or {}).get("username", ""),
            "labels": [l.get("name", "") for l in data.get("labels", [])],
            "url": data.get("web_url", ""),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
        }

    raise HTTPException(status_code=400, detail="provider must be github or gitlab")


class PRAutoCommentRequest(BaseModel):
    """Request to auto-generate and post audit report for a PR."""
    repo: str = Field(..., description="owner/repo format")
    pr_number: int = Field(..., description="PR number")
    code_map: Dict[str, str] = Field(default_factory=dict, description="filepath -> content to scan")
    provider: str = Field("github", description="github or gitlab")
    gitlab_url: str = Field("", description="GitLab instance URL")
    gitlab_token: str = Field("", description="GitLab personal access token")


@router.post("/pr/auto-comment")
async def post_pr_auto_comment(request: PRAutoCommentRequest) -> Dict[str, Any]:
    """Automatically generate and post audit report for a PR."""
    from code4u.security_compliance.security.fortress_swarm import FortressSwarm

    fortress = FortressSwarm()
    result = await fortress.run_full_scan(
        code_map=request.code_map,
        routes=[],
    )
    report = result.get("auditReport", "# No audit report generated")

    pr_comment_req = PRCommentRequest(
        repo=request.repo,
        pr_number=request.pr_number,
        report=report,
        provider=request.provider,
        gitlab_url=request.gitlab_url,
        gitlab_token=request.gitlab_token,
    )
    comment_resp = await post_pr_comment(pr_comment_req)

    return {
        "scan": result,
        "comment": comment_resp.model_dump(),
    }
