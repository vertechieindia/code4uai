from __future__ import annotations
"""Tenant isolation for code4u.ai.

Each tenant has:
- Separate Knowledge Graph
- Separate embeddings
- Separate LoRA adapters (optional)
- Separate storage buckets

NO SHARED STATE. EVER.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger("security.tenant")


@dataclass
class TenantConfig:
    """Configuration for a tenant."""
    tenant_id: str
    name: str
    
    # Resource allocation
    knowledge_graph_id: str
    embedding_collection: str
    storage_bucket: str
    
    # Model configuration
    use_dedicated_model: bool = False
    dedicated_model_endpoint: Optional[str] = None
    lora_adapter_id: Optional[str] = None
    
    # Feature flags
    enable_cross_repo: bool = True
    enable_training_opt_in: bool = False
    
    # Limits
    max_concurrent_requests: int = 100
    max_tokens_per_request: int = 8192
    max_files_per_request: int = 12
    
    # Security
    allowed_domains: List[str] = field(default_factory=list)
    ip_allowlist: List[str] = field(default_factory=list)
    require_mfa: bool = False


@dataclass
class TenantContext:
    """
    Runtime context for tenant operations.
    
    This context is passed through ALL operations
    to ensure tenant isolation.
    """
    tenant_id: str
    config: TenantConfig
    
    # Session info
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Request context
    request_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Derived paths
    @property
    def graph_namespace(self) -> str:
        return f"kg_{self.tenant_id}"
    
    @property
    def embedding_namespace(self) -> str:
        return f"emb_{self.tenant_id}"
    
    @property
    def storage_prefix(self) -> str:
        return f"tenants/{self.tenant_id}/"
    
    def to_headers(self) -> Dict[str, str]:
        """Convert context to HTTP headers for internal services."""
        return {
            "X-Tenant-ID": self.tenant_id,
            "X-Request-ID": self.request_id or "",
            "X-User-ID": self.user_id or "",
            "X-Session-ID": self.session_id or "",
        }


class TenantManager:
    """
    Manage tenant lifecycle and context.
    
    Ensures hard tenant boundaries:
    - No data leakage between tenants
    - No resource sharing
    - Full audit trail
    """
    
    def __init__(self):
        self._tenants: dict[str, TenantConfig] = {}
        self._active_contexts: dict[str, TenantContext] = {}
    
    def register_tenant(self, config: TenantConfig) -> None:
        """Register a new tenant."""
        if config.tenant_id in self._tenants:
            raise ValueError(f"Tenant {config.tenant_id} already exists")
        
        self._tenants[config.tenant_id] = config
        
        logger.info(
            "tenant_registered",
            tenant_id=config.tenant_id,
            name=config.name,
            dedicated_model=config.use_dedicated_model
        )
    
    def get_tenant(self, tenant_id: str) -> TenantConfig | None:
        """Get tenant configuration."""
        return self._tenants.get(tenant_id)
    
    def create_context(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> TenantContext:
        """
        Create a tenant context for an operation.
        
        This context MUST be passed through all operations
        to ensure tenant isolation.
        """
        config = self._tenants.get(tenant_id)
        if not config:
            raise ValueError(f"Unknown tenant: {tenant_id}")
        
        import uuid
        request_id = request_id or str(uuid.uuid4())[:8]
        
        context = TenantContext(
            tenant_id=tenant_id,
            config=config,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
        )
        
        # Track active context
        self._active_contexts[request_id] = context
        
        logger.info(
            "context_created",
            tenant_id=tenant_id,
            request_id=request_id
        )
        
        return context
    
    def validate_access(
        self,
        context: TenantContext,
        resource_tenant_id: str
    ) -> bool:
        """
        Validate that context has access to resource.
        
        Cross-tenant access is ALWAYS denied.
        """
        if context.tenant_id != resource_tenant_id:
            logger.warning(
                "cross_tenant_access_denied",
                requesting_tenant=context.tenant_id,
                resource_tenant=resource_tenant_id,
                request_id=context.request_id
            )
            return False
        
        return True
    
    def end_context(self, request_id: str) -> None:
        """End a tenant context."""
        if request_id in self._active_contexts:
            del self._active_contexts[request_id]

