"""MCP Marketplace - Discovery and installation of MCP servers."""

from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MCPCategory(str, Enum):
    """Categories of MCP servers."""
    BROWSER = "browser"
    DATABASE = "database"
    API = "api"
    FILE_SYSTEM = "file_system"
    SEARCH = "search"
    MONITORING = "monitoring"
    SECURITY = "security"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    INTEGRATION = "integration"
    AI_ML = "ai_ml"
    DEVOPS = "devops"
    CUSTOM = "custom"


class InstallStatus(str, Enum):
    """Installation status."""
    AVAILABLE = "available"
    INSTALLING = "installing"
    INSTALLED = "installed"
    UPDATING = "updating"
    FAILED = "failed"


@dataclass
class MCPServerInfo:
    """Information about an MCP server in the marketplace."""
    id: str
    name: str
    description: str
    
    # Publisher
    publisher: str
    verified: bool = False
    
    # Classification
    category: MCPCategory = MCPCategory.CUSTOM
    tags: List[str] = field(default_factory=list)
    
    # Version
    version: str = "1.0.0"
    changelog: str = ""
    
    # Installation
    install_command: str = ""
    config_schema: Dict[str, Any] = field(default_factory=dict)
    
    # Resources
    icon_url: Optional[str] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None
    
    # Stats
    downloads: int = 0
    rating: float = 0.0
    reviews_count: int = 0
    
    # Capabilities
    tools: List[str] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)
    prompts: List[str] = field(default_factory=list)
    
    # Requirements
    requires_auth: bool = False
    required_env_vars: List[str] = field(default_factory=list)
    
    # Timestamps
    published_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class InstalledServer:
    """An installed MCP server."""
    server_id: str
    name: str
    version: str
    
    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    env_vars: Dict[str, str] = field(default_factory=dict)
    
    # Status
    status: InstallStatus = InstallStatus.INSTALLED
    enabled: bool = True
    
    # Runtime
    process_id: Optional[int] = None
    port: Optional[int] = None
    url: Optional[str] = None
    
    # Timestamps
    installed_at: datetime = field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None


class MCPMarketplace:
    """
    MCP Marketplace for code4u.ai.
    
    Features:
    - Browse available MCP servers
    - One-click installation
    - Configuration management
    - Version updates
    - Enterprise private registry
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize marketplace."""
        self.tenant_id = tenant_id
        self._catalog: Dict[str, MCPServerInfo] = {}
        self._installed: Dict[str, InstalledServer] = {}
        
        # Initialize with built-in servers
        self._init_catalog()
    
    def _init_catalog(self) -> None:
        """Initialize with built-in MCP servers."""
        built_in = [
            MCPServerInfo(
                id="browser",
                name="Browser Agent",
                description="Control web browsers for automation and testing",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.BROWSER,
                tags=["browser", "automation", "testing", "web"],
                version="1.0.0",
                tools=["navigate", "click", "type", "screenshot", "evaluate"],
                resources=["page_content", "console_logs"],
            ),
            MCPServerInfo(
                id="filesystem",
                name="File System",
                description="Read and write files in the workspace",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.FILE_SYSTEM,
                tags=["files", "read", "write", "search"],
                tools=["read_file", "write_file", "list_dir", "search"],
            ),
            MCPServerInfo(
                id="github",
                name="GitHub",
                description="Interact with GitHub repositories, issues, and PRs",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.INTEGRATION,
                tags=["github", "git", "pr", "issues"],
                requires_auth=True,
                required_env_vars=["GITHUB_TOKEN"],
                tools=["create_pr", "list_issues", "create_issue", "review_pr"],
            ),
            MCPServerInfo(
                id="postgres",
                name="PostgreSQL",
                description="Query and manage PostgreSQL databases",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.DATABASE,
                tags=["database", "sql", "postgres"],
                requires_auth=True,
                required_env_vars=["DATABASE_URL"],
                tools=["query", "schema", "insert", "update"],
            ),
            MCPServerInfo(
                id="slack",
                name="Slack",
                description="Send messages and interact with Slack",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.INTEGRATION,
                tags=["slack", "chat", "notification"],
                requires_auth=True,
                required_env_vars=["SLACK_BOT_TOKEN"],
                tools=["send_message", "list_channels", "search"],
            ),
            MCPServerInfo(
                id="jira",
                name="Jira",
                description="Manage Jira issues and projects",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.INTEGRATION,
                tags=["jira", "issues", "project"],
                requires_auth=True,
                required_env_vars=["JIRA_URL", "JIRA_API_TOKEN"],
                tools=["create_issue", "update_issue", "search", "transition"],
            ),
            MCPServerInfo(
                id="docker",
                name="Docker",
                description="Manage Docker containers and images",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.DEVOPS,
                tags=["docker", "containers", "devops"],
                tools=["list_containers", "run", "stop", "logs", "build"],
            ),
            MCPServerInfo(
                id="kubernetes",
                name="Kubernetes",
                description="Manage Kubernetes clusters",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.DEVOPS,
                tags=["kubernetes", "k8s", "devops"],
                requires_auth=True,
                tools=["get_pods", "apply", "delete", "logs", "exec"],
            ),
            MCPServerInfo(
                id="sentry",
                name="Sentry",
                description="Monitor errors and performance",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.MONITORING,
                tags=["sentry", "errors", "monitoring"],
                requires_auth=True,
                required_env_vars=["SENTRY_AUTH_TOKEN"],
                tools=["list_issues", "resolve_issue", "search"],
            ),
            MCPServerInfo(
                id="datadog",
                name="Datadog",
                description="Monitor infrastructure and logs",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.MONITORING,
                tags=["datadog", "monitoring", "logs"],
                requires_auth=True,
                required_env_vars=["DD_API_KEY", "DD_APP_KEY"],
                tools=["query_logs", "get_metrics", "create_dashboard"],
            ),
            MCPServerInfo(
                id="openapi",
                name="OpenAPI",
                description="Generate and validate OpenAPI specs",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.API,
                tags=["openapi", "swagger", "api"],
                tools=["generate", "validate", "mock"],
            ),
            MCPServerInfo(
                id="puppeteer",
                name="Puppeteer",
                description="Headless browser automation",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.TESTING,
                tags=["testing", "browser", "e2e"],
                tools=["navigate", "screenshot", "pdf", "evaluate"],
            ),
            MCPServerInfo(
                id="notion",
                name="Notion",
                description="Manage Notion pages and databases",
                publisher="code4u.ai",
                verified=True,
                category=MCPCategory.DOCUMENTATION,
                tags=["notion", "docs", "wiki"],
                requires_auth=True,
                required_env_vars=["NOTION_TOKEN"],
                tools=["create_page", "update_page", "query_database"],
            ),
            MCPServerInfo(
                id="linear",
                name="Linear",
                description="Manage Linear issues and projects",
                publisher="community",
                verified=False,
                category=MCPCategory.INTEGRATION,
                tags=["linear", "issues", "project"],
                requires_auth=True,
                tools=["create_issue", "update_issue", "search"],
            ),
            MCPServerInfo(
                id="stripe",
                name="Stripe",
                description="Manage Stripe payments and subscriptions",
                publisher="community",
                verified=False,
                category=MCPCategory.INTEGRATION,
                tags=["stripe", "payments", "billing"],
                requires_auth=True,
                tools=["list_customers", "create_payment", "list_subscriptions"],
            ),
        ]
        
        for server in built_in:
            self._catalog[server.id] = server
    
    def list_servers(
        self,
        category: Optional[MCPCategory] = None,
        search: Optional[str] = None,
        verified_only: bool = False,
    ) -> List[MCPServerInfo]:
        """List available MCP servers.
        
        Args:
            category: Filter by category
            search: Search query
            verified_only: Only show verified
            
        Returns:
            List of matching servers
        """
        servers = list(self._catalog.values())
        
        if category:
            servers = [s for s in servers if s.category == category]
        
        if verified_only:
            servers = [s for s in servers if s.verified]
        
        if search:
            search_lower = search.lower()
            servers = [
                s for s in servers
                if search_lower in s.name.lower()
                or search_lower in s.description.lower()
                or any(search_lower in tag for tag in s.tags)
            ]
        
        return sorted(servers, key=lambda s: s.downloads, reverse=True)
    
    def get_server(self, server_id: str) -> Optional[MCPServerInfo]:
        """Get server details."""
        return self._catalog.get(server_id)
    
    async def install(
        self,
        server_id: str,
        config: Optional[Dict[str, Any]] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> InstalledServer:
        """Install an MCP server.
        
        Args:
            server_id: Server to install
            config: Configuration
            env_vars: Environment variables
            
        Returns:
            Installed server
        """
        server = self._catalog.get(server_id)
        if not server:
            raise ValueError(f"Server not found: {server_id}")
        
        # Check required env vars
        if server.required_env_vars:
            env_vars = env_vars or {}
            missing = [v for v in server.required_env_vars if v not in env_vars]
            if missing:
                raise ValueError(f"Missing required env vars: {missing}")
        
        # Create installed record
        installed = InstalledServer(
            server_id=server_id,
            name=server.name,
            version=server.version,
            config=config or {},
            env_vars=env_vars or {},
            status=InstallStatus.INSTALLED,
        )
        
        self._installed[server_id] = installed
        
        # Update download count
        server.downloads += 1
        
        return installed
    
    async def uninstall(self, server_id: str) -> bool:
        """Uninstall an MCP server."""
        if server_id in self._installed:
            del self._installed[server_id]
            return True
        return False
    
    def list_installed(self) -> List[InstalledServer]:
        """List installed servers."""
        return list(self._installed.values())
    
    def get_installed(self, server_id: str) -> Optional[InstalledServer]:
        """Get an installed server."""
        return self._installed.get(server_id)
    
    async def enable(self, server_id: str) -> bool:
        """Enable an installed server."""
        installed = self._installed.get(server_id)
        if installed:
            installed.enabled = True
            return True
        return False
    
    async def disable(self, server_id: str) -> bool:
        """Disable an installed server."""
        installed = self._installed.get(server_id)
        if installed:
            installed.enabled = False
            return True
        return False
    
    async def update_config(
        self,
        server_id: str,
        config: Dict[str, Any],
    ) -> InstalledServer:
        """Update server configuration."""
        installed = self._installed.get(server_id)
        if not installed:
            raise ValueError(f"Server not installed: {server_id}")
        
        installed.config.update(config)
        return installed
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories with counts."""
        counts: Dict[MCPCategory, int] = {}
        for server in self._catalog.values():
            counts[server.category] = counts.get(server.category, 0) + 1
        
        return [
            {"category": cat.value, "count": count}
            for cat, count in sorted(counts.items(), key=lambda x: -x[1])
        ]
    
    def add_to_catalog(self, server: MCPServerInfo) -> None:
        """Add a custom server to catalog (enterprise feature)."""
        self._catalog[server.id] = server

