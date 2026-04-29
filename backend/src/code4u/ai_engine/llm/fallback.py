"""Premium model fallback system."""

from __future__ import annotations
import time
import asyncio
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta


class FallbackReason(str, Enum):
    """Reasons for fallback."""
    MODEL_UNAVAILABLE = "model_unavailable"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    QUALITY_THRESHOLD = "quality_threshold"
    RETRY_EXHAUSTED = "retry_exhausted"
    COMPLEXITY_THRESHOLD = "complexity_threshold"
    CONTEXT_TOO_LONG = "context_too_long"
    ERROR = "error"


@dataclass
class FallbackDecision:
    """Decision to fallback to premium model."""
    should_fallback: bool
    reason: Optional[FallbackReason] = None
    source_model: Optional[str] = None
    target_model: Optional[str] = None
    attempt_number: int = 0
    
    # Cost implications
    estimated_cost: float = 0.0
    
    # Audit
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tenant_id: str = "default"


@dataclass
class FallbackPolicy:
    """Policy for premium model fallback."""
    tenant_id: str
    
    # Enable/disable
    enabled: bool = True
    
    # Triggers
    max_retries_before_fallback: int = 2
    quality_threshold: float = 0.7  # Min acceptable quality
    latency_threshold_ms: float = 30000  # Max acceptable latency
    
    # Context limits for self-hosted
    max_context_self_hosted: int = 16000
    
    # Complexity routing
    complexity_threshold: float = 0.8  # Above this, use premium
    
    # Budget
    daily_premium_budget: float = 100.0
    monthly_premium_budget: float = 2000.0
    
    # Allowed premium models
    allowed_premium_models: List[str] = field(default_factory=lambda: [
        "gpt-4o",
        "claude-sonnet-4",
    ])
    
    # Premium model order (try in sequence)
    fallback_chain: List[str] = field(default_factory=lambda: [
        "gpt-4o",
        "claude-sonnet-4",
        "claude-opus-4",
    ])


@dataclass
class FallbackMetrics:
    """Metrics for fallback tracking."""
    tenant_id: str
    
    # Counts
    total_requests: int = 0
    self_hosted_success: int = 0
    premium_fallbacks: int = 0
    
    # By reason
    fallbacks_by_reason: Dict[str, int] = field(default_factory=dict)
    
    # Cost
    premium_cost_today: float = 0.0
    premium_cost_month: float = 0.0
    
    # Quality
    avg_quality_self_hosted: float = 0.0
    avg_quality_premium: float = 0.0
    
    # Time
    last_reset_day: Optional[datetime] = None
    last_reset_month: Optional[datetime] = None


class PremiumFallbackManager:
    """
    Manages fallback from self-hosted to premium models.
    
    Key principles:
    1. Self-hosted first - always try self-hosted models
    2. Fallback only when necessary - not for convenience
    3. Budget-aware - respect cost limits
    4. Auditable - log all fallback decisions
    5. Tenant-isolated - per-tenant policies
    """
    
    def __init__(self):
        """Initialize fallback manager."""
        self._policies: Dict[str, FallbackPolicy] = {}
        self._metrics: Dict[str, FallbackMetrics] = {}
        self._callbacks: List[Callable[[FallbackDecision], None]] = []
    
    def set_policy(self, policy: FallbackPolicy) -> None:
        """Set fallback policy for a tenant."""
        self._policies[policy.tenant_id] = policy
        if policy.tenant_id not in self._metrics:
            self._metrics[policy.tenant_id] = FallbackMetrics(tenant_id=policy.tenant_id)
    
    def get_policy(self, tenant_id: str) -> FallbackPolicy:
        """Get fallback policy for a tenant."""
        if tenant_id not in self._policies:
            self._policies[tenant_id] = FallbackPolicy(tenant_id=tenant_id)
        return self._policies[tenant_id]
    
    def should_fallback(
        self,
        tenant_id: str,
        attempt_number: int,
        context_tokens: int,
        complexity_score: float,
        last_error: Optional[str] = None,
        last_quality_score: Optional[float] = None,
        last_latency_ms: Optional[float] = None,
    ) -> FallbackDecision:
        """Determine if we should fallback to premium model.
        
        Args:
            tenant_id: Tenant identifier
            attempt_number: Current attempt number
            context_tokens: Number of context tokens
            complexity_score: Task complexity (0-1)
            last_error: Error from last attempt
            last_quality_score: Quality score from last attempt
            last_latency_ms: Latency from last attempt
            
        Returns:
            FallbackDecision
        """
        policy = self.get_policy(tenant_id)
        metrics = self._get_metrics(tenant_id)
        
        # Check if fallback is enabled
        if not policy.enabled:
            return FallbackDecision(
                should_fallback=False,
                tenant_id=tenant_id,
            )
        
        # Check budget
        if not self._within_budget(policy, metrics):
            return FallbackDecision(
                should_fallback=False,
                reason=FallbackReason.RATE_LIMITED,
                tenant_id=tenant_id,
            )
        
        # Check complexity threshold
        if complexity_score > policy.complexity_threshold:
            return FallbackDecision(
                should_fallback=True,
                reason=FallbackReason.COMPLEXITY_THRESHOLD,
                target_model=policy.fallback_chain[0] if policy.fallback_chain else None,
                tenant_id=tenant_id,
            )
        
        # Check context length
        if context_tokens > policy.max_context_self_hosted:
            return FallbackDecision(
                should_fallback=True,
                reason=FallbackReason.CONTEXT_TOO_LONG,
                target_model=policy.fallback_chain[0] if policy.fallback_chain else None,
                tenant_id=tenant_id,
            )
        
        # Check retry exhaustion
        if attempt_number >= policy.max_retries_before_fallback:
            return FallbackDecision(
                should_fallback=True,
                reason=FallbackReason.RETRY_EXHAUSTED,
                attempt_number=attempt_number,
                target_model=policy.fallback_chain[0] if policy.fallback_chain else None,
                tenant_id=tenant_id,
            )
        
        # Check quality threshold
        if last_quality_score is not None and last_quality_score < policy.quality_threshold:
            return FallbackDecision(
                should_fallback=True,
                reason=FallbackReason.QUALITY_THRESHOLD,
                target_model=policy.fallback_chain[0] if policy.fallback_chain else None,
                tenant_id=tenant_id,
            )
        
        # Check latency threshold
        if last_latency_ms is not None and last_latency_ms > policy.latency_threshold_ms:
            return FallbackDecision(
                should_fallback=True,
                reason=FallbackReason.TIMEOUT,
                target_model=policy.fallback_chain[0] if policy.fallback_chain else None,
                tenant_id=tenant_id,
            )
        
        # Check for errors
        if last_error:
            return FallbackDecision(
                should_fallback=True,
                reason=FallbackReason.ERROR,
                target_model=policy.fallback_chain[0] if policy.fallback_chain else None,
                tenant_id=tenant_id,
            )
        
        # No fallback needed
        return FallbackDecision(
            should_fallback=False,
            tenant_id=tenant_id,
        )
    
    def get_next_fallback_model(
        self,
        tenant_id: str,
        failed_models: List[str],
    ) -> Optional[str]:
        """Get next model in fallback chain.
        
        Args:
            tenant_id: Tenant identifier
            failed_models: Models that have already failed
            
        Returns:
            Next model to try, or None
        """
        policy = self.get_policy(tenant_id)
        
        for model in policy.fallback_chain:
            if model not in failed_models:
                return model
        
        return None
    
    def record_fallback(
        self,
        tenant_id: str,
        reason: FallbackReason,
        cost: float = 0.0,
    ) -> None:
        """Record a fallback for metrics.
        
        Args:
            tenant_id: Tenant identifier
            reason: Reason for fallback
            cost: Cost of premium request
        """
        metrics = self._get_metrics(tenant_id)
        
        metrics.premium_fallbacks += 1
        metrics.premium_cost_today += cost
        metrics.premium_cost_month += cost
        
        reason_key = reason.value
        metrics.fallbacks_by_reason[reason_key] = (
            metrics.fallbacks_by_reason.get(reason_key, 0) + 1
        )
        
        # Notify callbacks
        decision = FallbackDecision(
            should_fallback=True,
            reason=reason,
            tenant_id=tenant_id,
        )
        for callback in self._callbacks:
            try:
                callback(decision)
            except:
                pass
    
    def record_success(
        self,
        tenant_id: str,
        is_premium: bool,
        quality_score: float,
    ) -> None:
        """Record a successful request.
        
        Args:
            tenant_id: Tenant identifier
            is_premium: Whether premium model was used
            quality_score: Quality score of result
        """
        metrics = self._get_metrics(tenant_id)
        metrics.total_requests += 1
        
        if is_premium:
            # Update premium quality average
            n = metrics.premium_fallbacks
            metrics.avg_quality_premium = (
                (metrics.avg_quality_premium * (n - 1) + quality_score) / n
                if n > 0 else quality_score
            )
        else:
            metrics.self_hosted_success += 1
            # Update self-hosted quality average
            n = metrics.self_hosted_success
            metrics.avg_quality_self_hosted = (
                (metrics.avg_quality_self_hosted * (n - 1) + quality_score) / n
            )
    
    def get_metrics(self, tenant_id: str) -> FallbackMetrics:
        """Get fallback metrics for a tenant."""
        return self._get_metrics(tenant_id)
    
    def _get_metrics(self, tenant_id: str) -> FallbackMetrics:
        """Get or create metrics for tenant."""
        if tenant_id not in self._metrics:
            self._metrics[tenant_id] = FallbackMetrics(tenant_id=tenant_id)
        
        # Reset daily/monthly counters if needed
        metrics = self._metrics[tenant_id]
        now = datetime.utcnow()
        
        if metrics.last_reset_day is None or metrics.last_reset_day.date() < now.date():
            metrics.premium_cost_today = 0.0
            metrics.last_reset_day = now
        
        if metrics.last_reset_month is None or metrics.last_reset_month.month < now.month:
            metrics.premium_cost_month = 0.0
            metrics.last_reset_month = now
        
        return metrics
    
    def _within_budget(self, policy: FallbackPolicy, metrics: FallbackMetrics) -> bool:
        """Check if within budget limits."""
        if metrics.premium_cost_today >= policy.daily_premium_budget:
            return False
        if metrics.premium_cost_month >= policy.monthly_premium_budget:
            return False
        return True
    
    def add_fallback_callback(
        self, 
        callback: Callable[[FallbackDecision], None]
    ) -> None:
        """Add callback for fallback events (for alerting)."""
        self._callbacks.append(callback)
    
    def get_fallback_rate(self, tenant_id: str) -> float:
        """Get fallback rate for a tenant."""
        metrics = self._get_metrics(tenant_id)
        if metrics.total_requests == 0:
            return 0.0
        return metrics.premium_fallbacks / metrics.total_requests

