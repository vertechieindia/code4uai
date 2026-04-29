"""Data models for Model Picker."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from enum import Enum
from datetime import datetime


class ModelProvider(str, Enum):
    """Supported model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    XAI = "xai"
    SELF_HOSTED = "self_hosted"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    TOGETHER = "together"
    GROQ = "groq"
    LOCAL = "local"


class ModelCapability(str, Enum):
    """Model capabilities."""
    CODE_GENERATION = "code_generation"
    CODE_COMPLETION = "code_completion"
    CODE_REFACTORING = "code_refactoring"
    CODE_EXPLANATION = "code_explanation"
    CODE_REVIEW = "code_review"
    CHAT = "chat"
    REASONING = "reasoning"
    LONG_CONTEXT = "long_context"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    FAST_INFERENCE = "fast_inference"
    LOW_COST = "low_cost"


class RoutingStrategy(str, Enum):
    """Model routing strategies."""
    PERFORMANCE = "performance"      # Best quality
    COST = "cost"                    # Lowest cost
    BALANCED = "balanced"            # Balance quality/cost
    LATENCY = "latency"              # Fastest response
    SELF_HOSTED_FIRST = "self_hosted_first"  # Prefer self-hosted
    FALLBACK_CHAIN = "fallback_chain"  # Try in order


@dataclass
class ModelConfig:
    """Configuration for a model."""
    id: str
    name: str
    provider: ModelProvider
    
    # Model identifiers
    model_id: str  # e.g., "gpt-4o", "claude-3-5-sonnet"
    api_base: Optional[str] = None
    api_version: Optional[str] = None
    
    # Capabilities
    capabilities: Set[ModelCapability] = field(default_factory=set)
    
    # Context limits
    max_context_tokens: int = 8192
    max_output_tokens: int = 4096
    
    # Performance
    tokens_per_second: float = 50.0
    avg_latency_ms: float = 1000.0
    
    # Cost (per 1M tokens)
    input_cost_per_million: float = 0.0
    output_cost_per_million: float = 0.0
    
    # Quality scores (0-1)
    code_quality_score: float = 0.8
    reasoning_score: float = 0.8
    
    # Availability
    is_available: bool = True
    rate_limit_rpm: int = 100
    
    # Tenant restrictions
    allowed_tenants: List[str] = field(default_factory=list)  # Empty = all
    blocked_tenants: List[str] = field(default_factory=list)
    
    # Tags
    tags: List[str] = field(default_factory=list)
    
    def supports(self, capability: ModelCapability) -> bool:
        """Check if model supports a capability."""
        return capability in self.capabilities
    
    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request."""
        input_cost = (input_tokens / 1_000_000) * self.input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * self.output_cost_per_million
        return input_cost + output_cost


@dataclass
class ModelSelection:
    """Result of model selection."""
    model: ModelConfig
    reason: str
    alternatives: List[ModelConfig] = field(default_factory=list)
    
    # Routing metadata
    strategy_used: RoutingStrategy = RoutingStrategy.BALANCED
    fallback_available: bool = True
    
    # Cost estimate
    estimated_cost: float = 0.0
    estimated_latency_ms: float = 0.0


@dataclass
class RoutingContext:
    """Context for routing decision."""
    # Task info
    task_type: str  # refactor, complete, explain, etc.
    complexity_score: float = 0.5  # 0-1
    
    # Token estimates
    estimated_input_tokens: int = 1000
    estimated_output_tokens: int = 500
    
    # Requirements
    required_capabilities: Set[ModelCapability] = field(default_factory=set)
    min_context_tokens: int = 0
    max_latency_ms: Optional[float] = None
    max_cost: Optional[float] = None
    
    # Tenant context
    tenant_id: str = "default"
    tenant_tier: str = "developer"  # developer, team, enterprise
    
    # User preferences
    preferred_provider: Optional[ModelProvider] = None
    preferred_model_id: Optional[str] = None
    
    # Previous attempts
    failed_models: List[str] = field(default_factory=list)


@dataclass
class ModelUsageMetrics:
    """Usage metrics for a model."""
    model_id: str
    
    # Counts
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Tokens
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    
    # Cost
    total_cost: float = 0.0
    
    # Performance
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    
    # Time
    last_used: Optional[datetime] = None
    period_start: Optional[datetime] = None


@dataclass
class TenantModelPolicy:
    """Model policy for a tenant."""
    tenant_id: str
    
    # Allowed models
    allowed_models: List[str] = field(default_factory=list)  # Empty = all
    blocked_models: List[str] = field(default_factory=list)
    
    # Routing
    default_strategy: RoutingStrategy = RoutingStrategy.BALANCED
    
    # Limits
    daily_token_limit: Optional[int] = None
    daily_cost_limit: Optional[float] = None
    max_requests_per_minute: int = 100
    
    # Premium access
    premium_models_enabled: bool = False
    self_hosted_only: bool = False
    
    # Fallback
    allow_premium_fallback: bool = True
    fallback_threshold_retries: int = 2

