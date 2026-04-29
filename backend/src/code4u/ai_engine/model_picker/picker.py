"""Model picker UI data and API."""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .models import (
    ModelProvider,
    ModelConfig,
    ModelCapability,
    RoutingStrategy,
    ModelUsageMetrics,
)
from .registry import ModelRegistry
from .router import ModelRouter, RoutingContext


@dataclass
class ModelPickerOption:
    """Option for model picker UI."""
    id: str
    name: str
    provider: str
    
    # Display
    description: str = ""
    icon: str = ""
    badge: Optional[str] = None  # "recommended", "fast", "premium"
    
    # Capabilities
    capabilities: List[str] = field(default_factory=list)
    
    # Stats
    quality_score: float = 0.0
    speed_score: float = 0.0
    cost_per_request: float = 0.0
    
    # Availability
    is_available: bool = True
    is_premium: bool = False
    requires_key: bool = False


@dataclass
class ModelPickerConfig:
    """Configuration for model picker UI."""
    show_self_hosted: bool = True
    show_premium: bool = True
    allow_auto_routing: bool = True
    default_model_id: Optional[str] = None
    default_strategy: RoutingStrategy = RoutingStrategy.BALANCED


class ModelPicker:
    """
    Model picker for UI integration.
    
    Provides:
    - Model list for dropdowns
    - Suggestions based on task
    - Usage statistics
    """
    
    PROVIDER_ICONS = {
        ModelProvider.OPENAI: "🟢",
        ModelProvider.ANTHROPIC: "🟠",
        ModelProvider.GOOGLE: "🔵",
        ModelProvider.XAI: "⚫",
        ModelProvider.SELF_HOSTED: "🏠",
        ModelProvider.GROQ: "⚡",
    }
    
    def __init__(self, registry: Optional[ModelRegistry] = None):
        """Initialize model picker.
        
        Args:
            registry: Model registry (creates default if None)
        """
        self.registry = registry or ModelRegistry()
        self.router = ModelRouter(self.registry)
        self._usage_metrics: Dict[str, ModelUsageMetrics] = {}
    
    def get_options(
        self, 
        tenant_id: str = "default",
        task_type: Optional[str] = None,
    ) -> List[ModelPickerOption]:
        """Get model options for picker UI.
        
        Args:
            tenant_id: Tenant identifier
            task_type: Optional task type to filter by
            
        Returns:
            List of picker options
        """
        models = self.registry.list_for_tenant(tenant_id)
        options = []
        
        for model in models:
            # Determine badge
            badge = None
            if "recommended" in model.tags:
                badge = "recommended"
            elif "fast" in model.tags:
                badge = "fast"
            elif "premium" in model.tags:
                badge = "premium"
            
            # Calculate speed score (inverse of latency)
            max_latency = 5000
            speed_score = max(0, 1 - (model.avg_latency_ms / max_latency))
            
            # Estimate cost for typical request
            typical_cost = model.cost_estimate(2000, 1000)
            
            option = ModelPickerOption(
                id=model.id,
                name=model.name,
                provider=model.provider.value,
                description=self._get_description(model),
                icon=self.PROVIDER_ICONS.get(model.provider, "🤖"),
                badge=badge,
                capabilities=[c.value for c in model.capabilities],
                quality_score=model.code_quality_score,
                speed_score=speed_score,
                cost_per_request=typical_cost,
                is_available=model.is_available,
                is_premium="premium" in model.tags,
                requires_key=model.provider != ModelProvider.SELF_HOSTED,
            )
            options.append(option)
        
        # Sort: recommended first, then by quality
        options.sort(key=lambda o: (
            o.badge != "recommended",
            -o.quality_score,
        ))
        
        return options
    
    def _get_description(self, model: ModelConfig) -> str:
        """Generate description for model."""
        parts = []
        
        if model.provider == ModelProvider.SELF_HOSTED:
            parts.append("Self-hosted")
        else:
            parts.append(model.provider.value.replace("_", " ").title())
        
        if model.max_context_tokens >= 100000:
            parts.append(f"{model.max_context_tokens // 1000}K context")
        
        if ModelCapability.FAST_INFERENCE in model.capabilities:
            parts.append("Fast")
        
        if ModelCapability.REASONING in model.capabilities:
            parts.append("Advanced reasoning")
        
        return " • ".join(parts)
    
    def get_suggested_model(
        self,
        tenant_id: str,
        task_type: str,
        complexity: float = 0.5,
        code_length: int = 1000,
    ) -> ModelPickerOption:
        """Get suggested model for a task.
        
        Args:
            tenant_id: Tenant identifier
            task_type: Type of task (refactor, complete, explain)
            complexity: Task complexity (0-1)
            code_length: Approximate code length
            
        Returns:
            Suggested model option
        """
        # Build routing context
        context = RoutingContext(
            task_type=task_type,
            complexity_score=complexity,
            estimated_input_tokens=code_length + 500,
            estimated_output_tokens=code_length,
            tenant_id=tenant_id,
        )
        
        # Add required capabilities based on task
        if task_type == "refactor":
            context.required_capabilities.add(ModelCapability.CODE_REFACTORING)
        elif task_type == "complete":
            context.required_capabilities.add(ModelCapability.CODE_COMPLETION)
        elif task_type == "explain":
            context.required_capabilities.add(ModelCapability.CODE_EXPLANATION)
        
        # Route to get selection
        selection = self.router.route(context)
        model = selection.model
        
        return ModelPickerOption(
            id=model.id,
            name=model.name,
            provider=model.provider.value,
            description=selection.reason,
            icon=self.PROVIDER_ICONS.get(model.provider, "🤖"),
            badge="suggested",
            capabilities=[c.value for c in model.capabilities],
            quality_score=model.code_quality_score,
            speed_score=1 - (model.avg_latency_ms / 5000),
            cost_per_request=selection.estimated_cost,
            is_available=model.is_available,
        )
    
    def get_routing_strategies(self) -> List[Dict[str, Any]]:
        """Get available routing strategies for UI."""
        return [
            {
                "id": RoutingStrategy.BALANCED.value,
                "name": "Auto (Balanced)",
                "description": "Automatically select based on task complexity",
                "icon": "⚖️",
            },
            {
                "id": RoutingStrategy.PERFORMANCE.value,
                "name": "Best Quality",
                "description": "Use the highest quality model",
                "icon": "🏆",
            },
            {
                "id": RoutingStrategy.COST.value,
                "name": "Cost Optimized",
                "description": "Minimize API costs",
                "icon": "💰",
            },
            {
                "id": RoutingStrategy.LATENCY.value,
                "name": "Fastest",
                "description": "Minimize response time",
                "icon": "⚡",
            },
            {
                "id": RoutingStrategy.SELF_HOSTED_FIRST.value,
                "name": "Self-Hosted First",
                "description": "Prefer on-premise models",
                "icon": "🏠",
            },
        ]
    
    def record_usage(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        success: bool,
    ) -> None:
        """Record model usage for analytics.
        
        Args:
            model_id: Model that was used
            input_tokens: Input token count
            output_tokens: Output token count
            latency_ms: Request latency
            success: Whether request succeeded
        """
        if model_id not in self._usage_metrics:
            self._usage_metrics[model_id] = ModelUsageMetrics(model_id=model_id)
        
        metrics = self._usage_metrics[model_id]
        metrics.total_requests += 1
        
        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1
        
        metrics.total_input_tokens += input_tokens
        metrics.total_output_tokens += output_tokens
        
        # Calculate cost
        model = self.registry.get(model_id)
        if model:
            metrics.total_cost += model.cost_estimate(input_tokens, output_tokens)
        
        # Update latency (rolling average)
        n = metrics.total_requests
        metrics.avg_latency_ms = (
            (metrics.avg_latency_ms * (n - 1) + latency_ms) / n
        )
    
    def get_usage_stats(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics.
        
        Args:
            model_id: Specific model or None for all
            
        Returns:
            Usage statistics
        """
        if model_id:
            metrics = self._usage_metrics.get(model_id)
            if not metrics:
                return {}
            return {
                "model_id": metrics.model_id,
                "total_requests": metrics.total_requests,
                "success_rate": metrics.successful_requests / max(1, metrics.total_requests),
                "total_tokens": metrics.total_input_tokens + metrics.total_output_tokens,
                "total_cost": metrics.total_cost,
                "avg_latency_ms": metrics.avg_latency_ms,
            }
        
        # Aggregate all
        return {
            "models": {
                mid: self.get_usage_stats(mid)
                for mid in self._usage_metrics
            },
            "total_requests": sum(m.total_requests for m in self._usage_metrics.values()),
            "total_cost": sum(m.total_cost for m in self._usage_metrics.values()),
        }

