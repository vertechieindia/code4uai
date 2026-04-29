from __future__ import annotations
"""Routing engine for Self-Hosted ↔ Cloud decisions.

This logic is CODE, not config.

Flow:
Intent → Graph Impact Analysis → Complexity Score → Routing Engine
                                                     ├── Self-hosted LLM
                                                     └── Premium API (logged + metered)
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
import structlog

from code4u.ai_engine.routing.complexity import ComplexityScorer, ComplexityScore, RiskLevel
from code4u.ai_engine.routing.cost_controls import CostController, CostGuardrails

logger = structlog.get_logger("routing.engine")


@dataclass
class RoutingDecision:
    """
    Deterministic routing decision.
    
    Every request is scored before touching a model.
    """
    # Decision
    target: Literal["self_hosted", "premium"]
    model: str
    
    # Scoring
    complexity_score: ComplexityScore
    
    # Metadata
    reason: str
    retry_count: int = 0
    is_fallback: bool = False
    
    # Tenant policy
    tenant_policy: str = "default"
    
    # Cost tracking
    estimated_tokens: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "model": self.model,
            "complexity": self.complexity_score.to_dict(),
            "reason": self.reason,
            "retry_count": self.retry_count,
            "is_fallback": self.is_fallback,
        }


class TenantRoutingPolicy:
    """Tenant-specific routing policy."""
    
    POLICIES = {
        "default": {
            "allow_premium": True,
            "premium_for_breaking": True,
            "max_retries_before_fallback": 2,
        },
        "air_gapped": {
            "allow_premium": False,  # NEVER use cloud
            "premium_for_breaking": False,
            "max_retries_before_fallback": 3,
        },
        "premium_first": {
            "allow_premium": True,
            "premium_for_breaking": True,
            "max_retries_before_fallback": 1,
            "prefer_premium": True,
        },
        "cost_optimized": {
            "allow_premium": True,
            "premium_for_breaking": False,
            "max_retries_before_fallback": 3,
        },
    }
    
    @classmethod
    def get(cls, policy_name: str) -> Dict[str, Any]:
        return cls.POLICIES.get(policy_name, cls.POLICIES["default"])


class RoutingEngine:
    """
    Route requests to self-hosted or premium models.
    
    Routing Rules (Hard Policy):
    - IF complexity < threshold → Self-hosted model
    - IF retry_count >= 2 → Premium fallback
    - IF breaking_change AND schema-heavy → Premium (optional)
    - IF tenant_policy = "air-gapped" → Self-hosted ONLY
    """
    
    # Model endpoints
    MODELS = {
        "self_hosted": {
            "primary": "Qwen/Qwen2.5-Coder-32B",
            "fallback": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        },
        "premium": {
            "primary": "claude-3-sonnet",
            "fallback": "gpt-4-turbo",
        },
    }
    
    def __init__(
        self,
        complexity_scorer: ComplexityScorer | None = None,
        cost_controller: CostController | None = None
    ):
        self.scorer = complexity_scorer or ComplexityScorer()
        self.cost_controller = cost_controller or CostController()
    
    def route(
        self,
        tenant_id: str,
        impacted_nodes: list[Any],
        context: Dict[str, Any],
        retry_count: int = 0,
        tenant_policy: str = "default"
    ) -> RoutingDecision:
        """
        Make a routing decision for a request.
        
        This is DETERMINISTIC - same inputs always produce same routing.
        """
        # Get tenant policy
        policy = TenantRoutingPolicy.get(tenant_policy)
        
        # Score complexity
        complexity = self.scorer.score(impacted_nodes, context)
        
        # Default to self-hosted
        target: Literal["self_hosted", "premium"] = "self_hosted"
        model = self.MODELS["self_hosted"]["primary"]
        reason = "Default: self-hosted model"
        is_fallback = False
        
        # Rule 1: Air-gapped tenants ALWAYS use self-hosted
        if tenant_policy == "air_gapped":
            target = "self_hosted"
            model = self.MODELS["self_hosted"]["primary"]
            reason = "Air-gapped policy: self-hosted only"
            
        # Rule 2: Retry threshold triggers fallback
        elif retry_count >= policy.get("max_retries_before_fallback", 2):
            if policy.get("allow_premium", True):
                target = "premium"
                model = self.MODELS["premium"]["primary"]
                reason = f"Retry threshold reached ({retry_count} retries)"
                is_fallback = True
            else:
                # Use self-hosted fallback model
                model = self.MODELS["self_hosted"]["fallback"]
                reason = f"Retry threshold, using fallback self-hosted model"
        
        # Rule 3: Premium for complex breaking changes
        elif (complexity.breaking_change and 
              complexity.schema_involvement and
              policy.get("premium_for_breaking", True) and
              policy.get("allow_premium", True)):
            target = "premium"
            model = self.MODELS["premium"]["primary"]
            reason = "Breaking change with schema: using premium"
        
        # Rule 4: Complexity-based routing
        elif complexity.requires_premium and policy.get("allow_premium", True):
            target = "premium"
            model = self.MODELS["premium"]["primary"]
            reason = f"High complexity ({complexity.total_score:.2f}): using premium"
        
        # Rule 5: Premium-first policy
        elif policy.get("prefer_premium", False):
            target = "premium"
            model = self.MODELS["premium"]["primary"]
            reason = "Premium-first policy"
        
        # Check cost controls
        if target == "premium":
            allowed, cost_reason = self.cost_controller.check_allowed(
                tenant_id=tenant_id,
                is_premium=True,
                estimated_tokens=complexity.prompt_token_estimate
            )
            if not allowed:
                # Fall back to self-hosted
                target = "self_hosted"
                model = self.MODELS["self_hosted"]["primary"]
                reason = f"Cost control: {cost_reason}"
                logger.warning(
                    "premium_blocked_by_cost",
                    tenant_id=tenant_id,
                    reason=cost_reason
                )
        
        decision = RoutingDecision(
            target=target,
            model=model,
            complexity_score=complexity,
            reason=reason,
            retry_count=retry_count,
            is_fallback=is_fallback,
            tenant_policy=tenant_policy,
            estimated_tokens=complexity.prompt_token_estimate,
        )
        
        logger.info(
            "routing_decision",
            tenant_id=tenant_id,
            target=target,
            model=model,
            complexity=complexity.total_score,
            risk_level=complexity.risk_level.value,
            is_fallback=is_fallback,
            reason=reason
        )
        
        return decision
    
    def record_completion(
        self,
        tenant_id: str,
        decision: RoutingDecision,
        tokens_used: int
    ) -> None:
        """Record completion for cost tracking."""
        self.cost_controller.record_usage(
            tenant_id=tenant_id,
            model=decision.model if decision.target == "premium" else "self_hosted",
            tokens_used=tokens_used,
            is_fallback=decision.is_fallback
        )

