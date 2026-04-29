"""Model router for intelligent model selection."""

from __future__ import annotations
from typing import Optional, List, Dict
import random

from .models import (
    ModelProvider,
    ModelConfig,
    ModelCapability,
    ModelSelection,
    RoutingStrategy,
    RoutingContext,
)
from .registry import ModelRegistry


class ModelRouter:
    """
    Intelligent model router.
    
    Selects the best model based on:
    - Task requirements
    - Cost constraints
    - Latency requirements
    - Tenant policies
    - Model availability
    """
    
    def __init__(self, registry: ModelRegistry):
        """Initialize router.
        
        Args:
            registry: Model registry to use
        """
        self.registry = registry
    
    def route(self, context: RoutingContext) -> ModelSelection:
        """Route a request to the best model.
        
        Args:
            context: Routing context with requirements
            
        Returns:
            ModelSelection with chosen model
        """
        # Get available models for tenant
        candidates = self.registry.list_for_tenant(context.tenant_id)
        
        # Filter by requirements
        candidates = self._filter_by_requirements(candidates, context)
        
        # Filter out failed models
        candidates = [m for m in candidates if m.id not in context.failed_models]
        
        if not candidates:
            raise ValueError("No suitable model available")
        
        # Apply routing strategy
        strategy = self._get_strategy(context)
        
        if strategy == RoutingStrategy.PERFORMANCE:
            selected = self._route_performance(candidates, context)
        elif strategy == RoutingStrategy.COST:
            selected = self._route_cost(candidates, context)
        elif strategy == RoutingStrategy.LATENCY:
            selected = self._route_latency(candidates, context)
        elif strategy == RoutingStrategy.SELF_HOSTED_FIRST:
            selected = self._route_self_hosted_first(candidates, context)
        else:  # BALANCED
            selected = self._route_balanced(candidates, context)
        
        # Build alternatives list
        alternatives = [m for m in candidates if m.id != selected.id][:3]
        
        return ModelSelection(
            model=selected,
            reason=self._get_selection_reason(selected, strategy, context),
            alternatives=alternatives,
            strategy_used=strategy,
            fallback_available=len(alternatives) > 0,
            estimated_cost=selected.cost_estimate(
                context.estimated_input_tokens,
                context.estimated_output_tokens
            ),
            estimated_latency_ms=selected.avg_latency_ms,
        )
    
    def _get_strategy(self, context: RoutingContext) -> RoutingStrategy:
        """Determine routing strategy from context."""
        # Check tenant policy
        policy = self.registry.get_tenant_policy(context.tenant_id)
        if policy:
            if policy.self_hosted_only:
                return RoutingStrategy.SELF_HOSTED_FIRST
            return policy.default_strategy
        
        # Infer from context
        if context.max_cost is not None and context.max_cost < 0.01:
            return RoutingStrategy.COST
        if context.max_latency_ms is not None and context.max_latency_ms < 500:
            return RoutingStrategy.LATENCY
        if context.complexity_score > 0.8:
            return RoutingStrategy.PERFORMANCE
        
        return RoutingStrategy.BALANCED
    
    def _filter_by_requirements(
        self, 
        models: List[ModelConfig], 
        context: RoutingContext
    ) -> List[ModelConfig]:
        """Filter models by requirements."""
        filtered = []
        
        for model in models:
            # Check capabilities
            if context.required_capabilities:
                if not all(model.supports(cap) for cap in context.required_capabilities):
                    continue
            
            # Check context size
            if model.max_context_tokens < context.min_context_tokens:
                continue
            
            # Check latency requirement
            if context.max_latency_ms and model.avg_latency_ms > context.max_latency_ms:
                continue
            
            # Check cost requirement
            if context.max_cost:
                estimated_cost = model.cost_estimate(
                    context.estimated_input_tokens,
                    context.estimated_output_tokens
                )
                if estimated_cost > context.max_cost:
                    continue
            
            # Check preferred provider
            if context.preferred_provider and model.provider != context.preferred_provider:
                continue
            
            # Check preferred model
            if context.preferred_model_id and model.id != context.preferred_model_id:
                continue
            
            filtered.append(model)
        
        return filtered
    
    def _route_performance(
        self, 
        models: List[ModelConfig], 
        context: RoutingContext
    ) -> ModelConfig:
        """Select highest quality model."""
        return max(models, key=lambda m: m.code_quality_score)
    
    def _route_cost(
        self, 
        models: List[ModelConfig], 
        context: RoutingContext
    ) -> ModelConfig:
        """Select lowest cost model."""
        return min(models, key=lambda m: m.cost_estimate(
            context.estimated_input_tokens,
            context.estimated_output_tokens
        ))
    
    def _route_latency(
        self, 
        models: List[ModelConfig], 
        context: RoutingContext
    ) -> ModelConfig:
        """Select fastest model."""
        return min(models, key=lambda m: m.avg_latency_ms)
    
    def _route_self_hosted_first(
        self, 
        models: List[ModelConfig], 
        context: RoutingContext
    ) -> ModelConfig:
        """Prefer self-hosted models."""
        self_hosted = [m for m in models if m.provider == ModelProvider.SELF_HOSTED]
        if self_hosted:
            return max(self_hosted, key=lambda m: m.code_quality_score)
        # Fallback to balanced if no self-hosted available
        return self._route_balanced(models, context)
    
    def _route_balanced(
        self, 
        models: List[ModelConfig], 
        context: RoutingContext
    ) -> ModelConfig:
        """Balance quality, cost, and latency."""
        def score(model: ModelConfig) -> float:
            # Normalize scores to 0-1
            quality = model.code_quality_score
            
            # Invert cost (lower is better)
            max_cost = max(m.cost_estimate(
                context.estimated_input_tokens,
                context.estimated_output_tokens
            ) for m in models) or 0.01
            cost_score = 1 - (model.cost_estimate(
                context.estimated_input_tokens,
                context.estimated_output_tokens
            ) / max_cost)
            
            # Invert latency (lower is better)
            max_latency = max(m.avg_latency_ms for m in models) or 1
            latency_score = 1 - (model.avg_latency_ms / max_latency)
            
            # Weight based on task complexity
            if context.complexity_score > 0.7:
                return 0.6 * quality + 0.2 * cost_score + 0.2 * latency_score
            elif context.complexity_score < 0.3:
                return 0.2 * quality + 0.4 * cost_score + 0.4 * latency_score
            else:
                return 0.4 * quality + 0.3 * cost_score + 0.3 * latency_score
        
        return max(models, key=score)
    
    def _get_selection_reason(
        self, 
        model: ModelConfig, 
        strategy: RoutingStrategy,
        context: RoutingContext
    ) -> str:
        """Generate explanation for model selection."""
        reasons = []
        
        if strategy == RoutingStrategy.PERFORMANCE:
            reasons.append(f"Highest quality score ({model.code_quality_score:.0%})")
        elif strategy == RoutingStrategy.COST:
            cost = model.cost_estimate(
                context.estimated_input_tokens,
                context.estimated_output_tokens
            )
            reasons.append(f"Lowest cost (${cost:.4f})")
        elif strategy == RoutingStrategy.LATENCY:
            reasons.append(f"Fastest response ({model.avg_latency_ms:.0f}ms)")
        elif strategy == RoutingStrategy.SELF_HOSTED_FIRST:
            if model.provider == ModelProvider.SELF_HOSTED:
                reasons.append("Self-hosted (no data leaves your infrastructure)")
            else:
                reasons.append("No self-hosted available, using cloud fallback")
        else:
            reasons.append("Balanced quality/cost/latency")
        
        if model.provider == ModelProvider.SELF_HOSTED:
            reasons.append("Data stays on-premise")
        
        return "; ".join(reasons)
    
    def get_fallback_model(
        self, 
        context: RoutingContext, 
        exclude_model_id: str
    ) -> Optional[ModelSelection]:
        """Get a fallback model after failure.
        
        Args:
            context: Original routing context
            exclude_model_id: Model that failed
            
        Returns:
            Alternative model selection or None
        """
        # Add failed model to exclusion list
        context.failed_models = list(context.failed_models) + [exclude_model_id]
        
        try:
            return self.route(context)
        except ValueError:
            return None

