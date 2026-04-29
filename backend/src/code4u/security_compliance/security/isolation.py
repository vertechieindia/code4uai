from __future__ import annotations
"""Model isolation for code4u.ai.

Isolation Options:
- Option A: Shared Base Model + Tenant LoRA (cheap, fast, safe)
- Option B: Dedicated Model Per Tenant (expensive, ultra-secure, regulated)
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List
import structlog

logger = structlog.get_logger("security.isolation")


class IsolationLevel(str, Enum):
    """Model isolation levels."""
    SHARED = "shared"           # Shared model, tenant LoRA
    DEDICATED = "dedicated"     # Dedicated model instance
    HYBRID = "hybrid"           # Shared for simple, dedicated for sensitive


@dataclass
class IsolationPolicy:
    """
    Isolation policy for a tenant.
    
    Determines how compute resources are allocated.
    """
    tenant_id: str
    level: IsolationLevel
    
    # Shared isolation config
    shared_model_endpoint: str = "http://vllm:8001"
    tenant_lora_adapter: Optional[str] = None
    
    # Dedicated isolation config
    dedicated_endpoint: Optional[str] = None
    dedicated_gpu_allocation: int = 0
    
    # Hybrid config
    sensitive_patterns: List[str] | None = None
    
    def get_endpoint(self, is_sensitive: bool = False) -> str:
        """Get the appropriate model endpoint."""
        if self.level == IsolationLevel.DEDICATED:
            if not self.dedicated_endpoint:
                raise ValueError("Dedicated endpoint not configured")
            return self.dedicated_endpoint
        
        if self.level == IsolationLevel.HYBRID and is_sensitive:
            if self.dedicated_endpoint:
                return self.dedicated_endpoint
        
        return self.shared_model_endpoint
    
    def get_lora_adapter(self) -> str | None:
        """Get tenant-specific LoRA adapter."""
        if self.level == IsolationLevel.SHARED:
            return self.tenant_lora_adapter
        return None


class IsolationManager:
    """
    Manage compute isolation for tenants.
    
    Ensures:
    - No model state shared between tenants
    - Dedicated resources for sensitive tenants
    - Cost optimization for shared tenants
    """
    
    def __init__(self):
        self._policies: dict[str, IsolationPolicy] = {}
    
    def set_policy(self, policy: IsolationPolicy) -> None:
        """Set isolation policy for a tenant."""
        self._policies[policy.tenant_id] = policy
        
        logger.info(
            "isolation_policy_set",
            tenant_id=policy.tenant_id,
            level=policy.level.value
        )
    
    def get_policy(self, tenant_id: str) -> IsolationPolicy:
        """Get isolation policy for a tenant."""
        policy = self._policies.get(tenant_id)
        
        if not policy:
            # Default to shared isolation
            policy = IsolationPolicy(
                tenant_id=tenant_id,
                level=IsolationLevel.SHARED
            )
        
        return policy
    
    def route_request(
        self,
        tenant_id: str,
        file_paths: List[str] | None = None
    ) -> Dict[str, Any]:
        """
        Route a request to the appropriate model endpoint.
        
        Returns routing configuration.
        """
        policy = self.get_policy(tenant_id)
        
        # Check if any files are sensitive (for hybrid)
        is_sensitive = False
        if policy.level == IsolationLevel.HYBRID and policy.sensitive_patterns:
            is_sensitive = self._check_sensitive(
                file_paths or [], 
                policy.sensitive_patterns
            )
        
        endpoint = policy.get_endpoint(is_sensitive)
        lora = policy.get_lora_adapter()
        
        logger.info(
            "request_routed",
            tenant_id=tenant_id,
            level=policy.level.value,
            is_sensitive=is_sensitive,
            endpoint=endpoint[:50] if endpoint else None
        )
        
        return {
            "endpoint": endpoint,
            "lora_adapter": lora,
            "isolation_level": policy.level.value,
            "is_sensitive": is_sensitive,
        }
    
    def _check_sensitive(
        self,
        file_paths: List[str],
        patterns: List[str]
    ) -> bool:
        """Check if any files match sensitive patterns."""
        import re
        for path in file_paths:
            for pattern in patterns:
                if re.search(pattern, path):
                    return True
        return False

