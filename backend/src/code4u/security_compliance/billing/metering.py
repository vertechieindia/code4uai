from __future__ import annotations
"""Usage metering for code4u.ai.

Every request logs:
{
  "tenant": "acme",
  "model": "self-hosted",
  "tokens": 3120,
  "gpu_ms": 420,
  "fallback": false
}

You know:
- Exact margin per tenant
- Which customers burn GPU
- When to upsell or throttle
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Literal, Optional
import structlog

logger = structlog.get_logger("billing.metering")


@dataclass
class UsageEvent:
    """
    A single usage event for billing.
    
    Every request creates one of these.
    """
    # Identity
    event_id: str
    tenant_id: str
    user_id: str
    
    # Timestamp
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Event type (what we bill for)
    event_type: Literal[
        "refactor_executed",
        "api_added",
        "api_changed",
        "cross_repo_change",
        "premium_fallback",
        "explanation",
        "impact_analysis",
    ] = "refactor_executed"
    
    # Resource usage (internal cost tracking)
    model: str = "self_hosted"
    tokens_input: int = 0
    tokens_output: int = 0
    gpu_ms: int = 0
    
    # Outcome metrics
    files_changed: int = 0
    lines_changed: int = 0
    repos_affected: int = 1
    
    # Routing
    is_fallback: bool = False
    
    # State
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "model": self.model,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "gpu_ms": self.gpu_ms,
            "files_changed": self.files_changed,
            "lines_changed": self.lines_changed,
            "repos_affected": self.repos_affected,
            "is_fallback": self.is_fallback,
            "success": self.success,
        }


@dataclass
class TenantMetrics:
    """Aggregated metrics for a tenant."""
    tenant_id: str
    period_start: str
    period_end: str
    
    # Outcome counts (what we bill for)
    refactors_executed: int = 0
    apis_added: int = 0
    apis_changed: int = 0
    cross_repo_changes: int = 0
    explanations: int = 0
    
    # Premium usage
    premium_fallbacks: int = 0
    
    # Resource usage (internal)
    total_tokens: int = 0
    total_gpu_ms: int = 0
    self_hosted_tokens: int = 0
    premium_tokens: int = 0
    
    # Costs (internal)
    estimated_cogs_usd: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "outcomes": {
                "refactors": self.refactors_executed,
                "apis_added": self.apis_added,
                "apis_changed": self.apis_changed,
                "cross_repo_changes": self.cross_repo_changes,
                "explanations": self.explanations,
            },
            "premium_fallbacks": self.premium_fallbacks,
            "resource_usage": {
                "total_tokens": self.total_tokens,
                "total_gpu_ms": self.total_gpu_ms,
            },
            "estimated_cogs_usd": self.estimated_cogs_usd,
        }


class UsageMetering:
    """
    Meter usage for billing and cost tracking.
    
    Tracks:
    - Outcomes (what we bill customers for)
    - Resources (what we pay for internally)
    - Margins (outcomes vs resources)
    """
    
    # Internal cost estimates
    COST_PER_GPU_HOUR = 2.50  # USD, A100
    COST_PER_1K_PREMIUM_TOKENS = 0.015  # USD, Claude Sonnet
    
    def __init__(self):
        self._events: list[UsageEvent] = []
        self._tenant_metrics: dict[str, TenantMetrics] = {}
    
    def record_event(self, event: UsageEvent) -> None:
        """Record a usage event."""
        self._events.append(event)
        self._update_metrics(event)
        
        logger.info(
            "usage_recorded",
            tenant_id=event.tenant_id,
            event_type=event.event_type,
            model=event.model,
            tokens=event.tokens_input + event.tokens_output,
            gpu_ms=event.gpu_ms,
            fallback=event.is_fallback
        )
    
    def record_refactor(
        self,
        tenant_id: str,
        user_id: str,
        model: str,
        tokens: int,
        gpu_ms: int,
        files_changed: int,
        lines_changed: int,
        repos_affected: int = 1,
        is_fallback: bool = False
    ) -> UsageEvent:
        """Record a refactor execution."""
        event_type = "cross_repo_change" if repos_affected > 1 else "refactor_executed"
        
        event = UsageEvent(
            event_id=self._generate_id(),
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            model=model,
            tokens_output=tokens,
            gpu_ms=gpu_ms,
            files_changed=files_changed,
            lines_changed=lines_changed,
            repos_affected=repos_affected,
            is_fallback=is_fallback,
        )
        
        self.record_event(event)
        return event
    
    def record_api_change(
        self,
        tenant_id: str,
        user_id: str,
        is_add: bool,
        model: str,
        tokens: int,
        gpu_ms: int
    ) -> UsageEvent:
        """Record an API add/change."""
        event = UsageEvent(
            event_id=self._generate_id(),
            tenant_id=tenant_id,
            user_id=user_id,
            event_type="api_added" if is_add else "api_changed",
            model=model,
            tokens_output=tokens,
            gpu_ms=gpu_ms,
        )
        
        self.record_event(event)
        return event
    
    def record_premium_fallback(
        self,
        tenant_id: str,
        user_id: str,
        model: str,
        tokens: int
    ) -> UsageEvent:
        """Record a premium model fallback."""
        event = UsageEvent(
            event_id=self._generate_id(),
            tenant_id=tenant_id,
            user_id=user_id,
            event_type="premium_fallback",
            model=model,
            tokens_output=tokens,
            is_fallback=True,
        )
        
        self.record_event(event)
        return event
    
    def get_tenant_metrics(
        self,
        tenant_id: str,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None
    ) -> TenantMetrics:
        """Get metrics for a tenant."""
        key = f"{tenant_id}:{period_start}:{period_end}"
        return self._tenant_metrics.get(key, TenantMetrics(
            tenant_id=tenant_id,
            period_start=period_start or "",
            period_end=period_end or "",
        ))
    
    def get_margin_analysis(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get margin analysis for a tenant.
        
        Shows:
        - Revenue (outcome-based)
        - COGS (resource-based)
        - Margin
        """
        # This would be calculated based on pricing tier and actual usage
        return {
            "tenant_id": tenant_id,
            "analysis_type": "margin",
            "period": "current_month",
            "note": "Implement with actual pricing engine",
        }
    
    def _update_metrics(self, event: UsageEvent) -> None:
        """Update aggregated metrics."""
        today = datetime.utcnow().date().isoformat()
        key = f"{event.tenant_id}:{today}:{today}"
        
        if key not in self._tenant_metrics:
            self._tenant_metrics[key] = TenantMetrics(
                tenant_id=event.tenant_id,
                period_start=today,
                period_end=today,
            )
        
        metrics = self._tenant_metrics[key]
        
        # Update outcome counts
        if event.event_type == "refactor_executed":
            metrics.refactors_executed += 1
        elif event.event_type == "api_added":
            metrics.apis_added += 1
        elif event.event_type == "api_changed":
            metrics.apis_changed += 1
        elif event.event_type == "cross_repo_change":
            metrics.cross_repo_changes += 1
        elif event.event_type == "explanation":
            metrics.explanations += 1
        elif event.event_type == "premium_fallback":
            metrics.premium_fallbacks += 1
        
        # Update resource usage
        total_tokens = event.tokens_input + event.tokens_output
        metrics.total_tokens += total_tokens
        metrics.total_gpu_ms += event.gpu_ms
        
        if event.is_fallback:
            metrics.premium_tokens += total_tokens
        else:
            metrics.self_hosted_tokens += total_tokens
        
        # Estimate COGS
        gpu_cost = (event.gpu_ms / 3600000) * self.COST_PER_GPU_HOUR
        premium_cost = (metrics.premium_tokens / 1000) * self.COST_PER_1K_PREMIUM_TOKENS
        metrics.estimated_cogs_usd = gpu_cost + premium_cost
    
    def _generate_id(self) -> str:
        import uuid
        return str(uuid.uuid4())[:12]

