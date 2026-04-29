"""
code4u.ai Model Picker & Intelligent Routing

Features:
- Multi-model support (OpenAI, Anthropic, Google, xAI, Self-hosted)
- Intelligent routing based on task complexity
- Cost-aware model selection
- Latency-optimized routing
- Tenant-specific model policies
"""

from .models import (
    ModelProvider,
    ModelConfig,
    ModelCapability,
    RoutingStrategy,
    ModelSelection,
)
from .registry import ModelRegistry
from .router import ModelRouter
from .picker import ModelPicker

__all__ = [
    "ModelProvider",
    "ModelConfig",
    "ModelCapability",
    "RoutingStrategy",
    "ModelSelection",
    "ModelRegistry",
    "ModelRouter",
    "ModelPicker",
]

