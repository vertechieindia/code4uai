from __future__ import annotations
"""Cost protection guardrails for code4u.ai.

Prevents surprise bills and controls cloud model usage.

Guardrails:
- Daily token caps
- Per-tenant premium ceiling
- Kill-switch for cloud models
- Alerting on abnormal fallback rates
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import structlog

logger = structlog.get_logger("routing.cost")


@dataclass
class CostGuardrails:
    """Cost guardrails configuration."""
    # Daily limits
    daily_token_cap: int = 1_000_000
    daily_premium_token_cap: int = 100_000
    
    # Per-request limits
    max_tokens_per_request: int = 8192
    max_premium_requests_per_hour: int = 100
    
    # Kill switches
    premium_enabled: bool = True
    emergency_cloud_disable: bool = False
    
    # Alert thresholds
    premium_fallback_rate_alert: float = 0.2  # Alert if >20% go to premium
    daily_cost_alert_threshold: float = 100.0  # USD


@dataclass
class TenantUsage:
    """Usage tracking for a tenant."""
    tenant_id: str
    date: str = field(default_factory=lambda: datetime.utcnow().date().isoformat())
    
    # Token counts
    self_hosted_tokens: int = 0
    premium_tokens: int = 0
    
    # Request counts
    self_hosted_requests: int = 0
    premium_requests: int = 0
    
    # Cost tracking
    estimated_cost_usd: float = 0.0
    
    # Fallback tracking
    fallback_count: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.self_hosted_tokens + self.premium_tokens
    
    @property
    def total_requests(self) -> int:
        return self.self_hosted_requests + self.premium_requests
    
    @property
    def fallback_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.premium_requests / self.total_requests


class CostController:
    """
    Control and monitor costs for model usage.
    
    Every fallback is:
    - Logged
    - Attributed to cost center
    - Visible to admins
    """
    
    # Cost per 1K tokens (approximate)
    COST_PER_1K = {
        "self_hosted": 0.0,      # Free (already paid for GPU)
        "gpt-4": 0.03,
        "gpt-4-turbo": 0.01,
        "claude-3-opus": 0.015,
        "claude-3-sonnet": 0.003,
    }
    
    def __init__(self, guardrails: CostGuardrails | None = None):
        self.guardrails = guardrails or CostGuardrails()
        self._usage: dict[str, TenantUsage] = {}
        self._hourly_premium: Dict[str, int] = {}
    
    def check_allowed(
        self,
        tenant_id: str,
        is_premium: bool,
        estimated_tokens: int
    ) -> tuple[bool, str]:
        """
        Check if a request is allowed under cost controls.
        
        Returns (allowed, reason).
        """
        # Emergency kill switch
        if self.guardrails.emergency_cloud_disable and is_premium:
            logger.warning("cloud_disabled_emergency", tenant_id=tenant_id)
            return False, "Cloud models temporarily disabled"
        
        # Premium disabled
        if not self.guardrails.premium_enabled and is_premium:
            return False, "Premium models disabled for tenant"
        
        usage = self._get_usage(tenant_id)
        
        # Daily token cap
        if usage.total_tokens + estimated_tokens > self.guardrails.daily_token_cap:
            logger.warning("daily_cap_exceeded", tenant_id=tenant_id)
            return False, "Daily token cap exceeded"
        
        # Premium token cap
        if is_premium:
            if usage.premium_tokens + estimated_tokens > self.guardrails.daily_premium_token_cap:
                logger.warning("premium_cap_exceeded", tenant_id=tenant_id)
                return False, "Daily premium token cap exceeded"
            
            # Hourly rate limit
            hour_key = f"{tenant_id}:{datetime.utcnow().hour}"
            hourly = self._hourly_premium.get(hour_key, 0)
            if hourly >= self.guardrails.max_premium_requests_per_hour:
                return False, "Hourly premium request limit exceeded"
        
        # Per-request limit
        if estimated_tokens > self.guardrails.max_tokens_per_request:
            return False, f"Request exceeds max tokens ({self.guardrails.max_tokens_per_request})"
        
        return True, "Allowed"
    
    def record_usage(
        self,
        tenant_id: str,
        model: str,
        tokens_used: int,
        is_fallback: bool = False
    ) -> TenantUsage:
        """
        Record token usage for a request.
        
        Returns updated usage.
        """
        usage = self._get_usage(tenant_id)
        is_premium = model != "self_hosted" and "self" not in model.lower()
        
        if is_premium:
            usage.premium_tokens += tokens_used
            usage.premium_requests += 1
            
            # Update hourly counter
            hour_key = f"{tenant_id}:{datetime.utcnow().hour}"
            self._hourly_premium[hour_key] = self._hourly_premium.get(hour_key, 0) + 1
            
            # Calculate cost
            cost_per_1k = self.COST_PER_1K.get(model, 0.01)
            usage.estimated_cost_usd += (tokens_used / 1000) * cost_per_1k
        else:
            usage.self_hosted_tokens += tokens_used
            usage.self_hosted_requests += 1
        
        if is_fallback:
            usage.fallback_count += 1
        
        # Check alerts
        self._check_alerts(tenant_id, usage)
        
        logger.info(
            "usage_recorded",
            tenant_id=tenant_id,
            model=model,
            tokens=tokens_used,
            is_premium=is_premium,
            is_fallback=is_fallback,
            total_cost=usage.estimated_cost_usd
        )
        
        return usage
    
    def get_usage(self, tenant_id: str) -> TenantUsage:
        """Get current usage for a tenant."""
        return self._get_usage(tenant_id)
    
    def get_cost_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get cost summary for a tenant."""
        usage = self._get_usage(tenant_id)
        
        return {
            "date": usage.date,
            "self_hosted": {
                "tokens": usage.self_hosted_tokens,
                "requests": usage.self_hosted_requests,
                "cost_usd": 0.0,
            },
            "premium": {
                "tokens": usage.premium_tokens,
                "requests": usage.premium_requests,
                "cost_usd": usage.estimated_cost_usd,
            },
            "totals": {
                "tokens": usage.total_tokens,
                "requests": usage.total_requests,
                "cost_usd": usage.estimated_cost_usd,
            },
            "limits": {
                "daily_token_cap": self.guardrails.daily_token_cap,
                "daily_premium_cap": self.guardrails.daily_premium_token_cap,
                "tokens_remaining": self.guardrails.daily_token_cap - usage.total_tokens,
            },
            "fallback_rate": usage.fallback_rate,
        }
    
    def _get_usage(self, tenant_id: str) -> TenantUsage:
        """Get or create usage record for today."""
        today = datetime.utcnow().date().isoformat()
        key = f"{tenant_id}:{today}"
        
        if key not in self._usage:
            self._usage[key] = TenantUsage(tenant_id=tenant_id, date=today)
        
        return self._usage[key]
    
    def _check_alerts(self, tenant_id: str, usage: TenantUsage) -> None:
        """Check and trigger alerts."""
        # Fallback rate alert
        if (usage.total_requests >= 10 and 
            usage.fallback_rate > self.guardrails.premium_fallback_rate_alert):
            logger.warning(
                "high_fallback_rate",
                tenant_id=tenant_id,
                rate=usage.fallback_rate
            )
        
        # Cost alert
        if usage.estimated_cost_usd > self.guardrails.daily_cost_alert_threshold:
            logger.warning(
                "daily_cost_threshold_exceeded",
                tenant_id=tenant_id,
                cost=usage.estimated_cost_usd
            )
    
    def set_emergency_disable(self, disabled: bool) -> None:
        """Set emergency cloud disable."""
        self.guardrails.emergency_cloud_disable = disabled
        logger.warning("cloud_kill_switch", disabled=disabled)

