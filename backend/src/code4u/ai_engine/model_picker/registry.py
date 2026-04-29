"""Model registry for managing available models."""

from __future__ import annotations
from typing import Optional, List, Dict, Set
import threading

from .models import (
    ModelProvider,
    ModelConfig,
    ModelCapability,
    TenantModelPolicy,
)


class ModelRegistry:
    """
    Registry of available models.
    
    Manages:
    - Model configurations
    - Provider credentials
    - Availability status
    - Tenant policies
    """
    
    def __init__(self):
        """Initialize model registry with default models."""
        self._models: Dict[str, ModelConfig] = {}
        self._tenant_policies: Dict[str, TenantModelPolicy] = {}
        self._lock = threading.RLock()
        
        # Register default models
        self._register_default_models()
    
    def _register_default_models(self) -> None:
        """Register default model configurations."""
        
        # OpenAI Models
        self.register(ModelConfig(
            id="gpt-4o",
            name="GPT-4o",
            provider=ModelProvider.OPENAI,
            model_id="gpt-4o",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.CODE_REFACTORING,
                ModelCapability.REASONING,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.VISION,
            },
            max_context_tokens=128000,
            max_output_tokens=16384,
            tokens_per_second=80,
            avg_latency_ms=800,
            input_cost_per_million=2.50,
            output_cost_per_million=10.00,
            code_quality_score=0.92,
            reasoning_score=0.90,
            tags=["premium", "recommended"],
        ))
        
        self.register(ModelConfig(
            id="gpt-4o-mini",
            name="GPT-4o Mini",
            provider=ModelProvider.OPENAI,
            model_id="gpt-4o-mini",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.FAST_INFERENCE,
                ModelCapability.LOW_COST,
            },
            max_context_tokens=128000,
            max_output_tokens=16384,
            tokens_per_second=150,
            avg_latency_ms=400,
            input_cost_per_million=0.15,
            output_cost_per_million=0.60,
            code_quality_score=0.82,
            reasoning_score=0.78,
            tags=["fast", "cost-effective"],
        ))
        
        self.register(ModelConfig(
            id="o1",
            name="o1 (Reasoning)",
            provider=ModelProvider.OPENAI,
            model_id="o1",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_REFACTORING,
                ModelCapability.REASONING,
            },
            max_context_tokens=200000,
            max_output_tokens=100000,
            tokens_per_second=20,
            avg_latency_ms=5000,
            input_cost_per_million=15.00,
            output_cost_per_million=60.00,
            code_quality_score=0.98,
            reasoning_score=0.99,
            tags=["premium", "reasoning", "complex-tasks"],
        ))
        
        # Anthropic Models
        self.register(ModelConfig(
            id="claude-sonnet-4",
            name="Claude Sonnet 4",
            provider=ModelProvider.ANTHROPIC,
            model_id="claude-sonnet-4-20250514",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.CODE_REFACTORING,
                ModelCapability.CODE_EXPLANATION,
                ModelCapability.REASONING,
                ModelCapability.LONG_CONTEXT,
            },
            max_context_tokens=200000,
            max_output_tokens=64000,
            tokens_per_second=60,
            avg_latency_ms=900,
            input_cost_per_million=3.00,
            output_cost_per_million=15.00,
            code_quality_score=0.94,
            reasoning_score=0.92,
            tags=["premium", "recommended", "long-context"],
        ))
        
        self.register(ModelConfig(
            id="claude-opus-4",
            name="Claude Opus 4",
            provider=ModelProvider.ANTHROPIC,
            model_id="claude-opus-4-20250514",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_REFACTORING,
                ModelCapability.REASONING,
                ModelCapability.LONG_CONTEXT,
            },
            max_context_tokens=200000,
            max_output_tokens=64000,
            tokens_per_second=30,
            avg_latency_ms=2000,
            input_cost_per_million=15.00,
            output_cost_per_million=75.00,
            code_quality_score=0.97,
            reasoning_score=0.98,
            tags=["premium", "complex-tasks"],
        ))
        
        # Google Models
        self.register(ModelConfig(
            id="gemini-2-flash",
            name="Gemini 2.0 Flash",
            provider=ModelProvider.GOOGLE,
            model_id="gemini-2.0-flash",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.FAST_INFERENCE,
                ModelCapability.LONG_CONTEXT,
            },
            max_context_tokens=1000000,
            max_output_tokens=8192,
            tokens_per_second=200,
            avg_latency_ms=300,
            input_cost_per_million=0.10,
            output_cost_per_million=0.40,
            code_quality_score=0.85,
            reasoning_score=0.82,
            tags=["fast", "cost-effective", "long-context"],
        ))
        
        # xAI Models
        self.register(ModelConfig(
            id="grok-3",
            name="Grok 3",
            provider=ModelProvider.XAI,
            model_id="grok-3",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.REASONING,
            },
            max_context_tokens=131072,
            max_output_tokens=8192,
            tokens_per_second=100,
            avg_latency_ms=600,
            input_cost_per_million=3.00,
            output_cost_per_million=15.00,
            code_quality_score=0.88,
            reasoning_score=0.87,
            tags=["premium"],
        ))
        
        # Self-hosted Models
        self.register(ModelConfig(
            id="codellama-70b",
            name="CodeLlama 70B (Self-hosted)",
            provider=ModelProvider.SELF_HOSTED,
            model_id="codellama-70b-instruct",
            api_base="http://localhost:8080/v1",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.LOW_COST,
            },
            max_context_tokens=16384,
            max_output_tokens=4096,
            tokens_per_second=40,
            avg_latency_ms=1500,
            input_cost_per_million=0.0,  # Self-hosted = no API cost
            output_cost_per_million=0.0,
            code_quality_score=0.78,
            reasoning_score=0.70,
            tags=["self-hosted", "no-data-sharing"],
        ))
        
        self.register(ModelConfig(
            id="deepseek-coder-v2",
            name="DeepSeek Coder V2 (Self-hosted)",
            provider=ModelProvider.SELF_HOSTED,
            model_id="deepseek-coder-v2",
            api_base="http://localhost:8080/v1",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.CODE_REFACTORING,
                ModelCapability.LOW_COST,
            },
            max_context_tokens=32768,
            max_output_tokens=8192,
            tokens_per_second=50,
            avg_latency_ms=1200,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            code_quality_score=0.85,
            reasoning_score=0.75,
            tags=["self-hosted", "no-data-sharing", "recommended"],
        ))
        
        # Groq (Fast inference)
        self.register(ModelConfig(
            id="llama-3-70b-groq",
            name="Llama 3 70B (Groq)",
            provider=ModelProvider.GROQ,
            model_id="llama3-70b-8192",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.FAST_INFERENCE,
                ModelCapability.LOW_COST,
            },
            max_context_tokens=8192,
            max_output_tokens=4096,
            tokens_per_second=500,
            avg_latency_ms=150,
            input_cost_per_million=0.59,
            output_cost_per_million=0.79,
            code_quality_score=0.80,
            reasoning_score=0.75,
            tags=["fast", "cost-effective"],
        ))

        # Ollama / Local models (zero API cost)
        self.register(ModelConfig(
            id="ollama-llama3",
            name="Llama 3.1 (Ollama)",
            provider=ModelProvider.LOCAL,
            model_id="llama3.1",
            api_base="http://localhost:11434",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.CODE_REFACTORING,
                ModelCapability.LOW_COST,
            },
            max_context_tokens=128000,
            max_output_tokens=8192,
            tokens_per_second=30,
            avg_latency_ms=2000,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            code_quality_score=0.80,
            reasoning_score=0.75,
            tags=["local", "offline", "no-data-sharing", "air-gapped"],
        ))

        self.register(ModelConfig(
            id="ollama-codellama",
            name="CodeLlama 34B (Ollama)",
            provider=ModelProvider.LOCAL,
            model_id="codellama:34b",
            api_base="http://localhost:11434",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.LOW_COST,
            },
            max_context_tokens=16384,
            max_output_tokens=4096,
            tokens_per_second=25,
            avg_latency_ms=3000,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            code_quality_score=0.78,
            reasoning_score=0.68,
            tags=["local", "offline", "no-data-sharing", "air-gapped"],
        ))

        self.register(ModelConfig(
            id="ollama-deepseek-coder",
            name="DeepSeek Coder V2 (Ollama)",
            provider=ModelProvider.LOCAL,
            model_id="deepseek-coder-v2",
            api_base="http://localhost:11434",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.CODE_REFACTORING,
                ModelCapability.LOW_COST,
            },
            max_context_tokens=32768,
            max_output_tokens=8192,
            tokens_per_second=35,
            avg_latency_ms=1800,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            code_quality_score=0.84,
            reasoning_score=0.76,
            tags=["local", "offline", "no-data-sharing", "air-gapped", "recommended"],
        ))

        self.register(ModelConfig(
            id="ollama-qwen-coder",
            name="Qwen 2.5 Coder 32B (Ollama)",
            provider=ModelProvider.LOCAL,
            model_id="qwen2.5-coder:32b",
            api_base="http://localhost:11434",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.CODE_REFACTORING,
                ModelCapability.REASONING,
                ModelCapability.LOW_COST,
            },
            max_context_tokens=32768,
            max_output_tokens=8192,
            tokens_per_second=30,
            avg_latency_ms=2200,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            code_quality_score=0.87,
            reasoning_score=0.82,
            tags=["local", "offline", "no-data-sharing", "air-gapped"],
        ))

        # vLLM endpoint (self-hosted, OpenAI-compatible)
        self.register(ModelConfig(
            id="vllm-local",
            name="vLLM Local Server",
            provider=ModelProvider.SELF_HOSTED,
            model_id="default",
            api_base="http://localhost:8000/v1",
            capabilities={
                ModelCapability.CODE_GENERATION,
                ModelCapability.CODE_COMPLETION,
                ModelCapability.CODE_REFACTORING,
                ModelCapability.LOW_COST,
            },
            max_context_tokens=32768,
            max_output_tokens=8192,
            tokens_per_second=60,
            avg_latency_ms=1200,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            code_quality_score=0.82,
            reasoning_score=0.75,
            tags=["self-hosted", "no-data-sharing", "air-gapped"],
        ))
    
    def register(self, model: ModelConfig) -> None:
        """Register a model configuration."""
        with self._lock:
            self._models[model.id] = model
    
    def unregister(self, model_id: str) -> bool:
        """Unregister a model."""
        with self._lock:
            if model_id in self._models:
                del self._models[model_id]
                return True
            return False
    
    def get(self, model_id: str) -> Optional[ModelConfig]:
        """Get a model by ID."""
        return self._models.get(model_id)
    
    def list_all(self) -> List[ModelConfig]:
        """List all registered models."""
        return list(self._models.values())
    
    def list_available(self) -> List[ModelConfig]:
        """List all available models."""
        return [m for m in self._models.values() if m.is_available]
    
    def list_by_provider(self, provider: ModelProvider) -> List[ModelConfig]:
        """List models by provider."""
        return [m for m in self._models.values() if m.provider == provider]
    
    def list_by_capability(self, capability: ModelCapability) -> List[ModelConfig]:
        """List models with a specific capability."""
        return [m for m in self._models.values() if m.supports(capability)]
    
    def list_for_tenant(self, tenant_id: str) -> List[ModelConfig]:
        """List models available for a tenant."""
        policy = self._tenant_policies.get(tenant_id)
        models = []
        
        for model in self._models.values():
            if not model.is_available:
                continue
            
            # Check model-level restrictions
            if model.allowed_tenants and tenant_id not in model.allowed_tenants:
                continue
            if tenant_id in model.blocked_tenants:
                continue
            
            # Check policy restrictions
            if policy:
                if policy.blocked_models and model.id in policy.blocked_models:
                    continue
                if policy.allowed_models and model.id not in policy.allowed_models:
                    continue
                if policy.self_hosted_only and model.provider != ModelProvider.SELF_HOSTED:
                    continue
            
            models.append(model)
        
        return models
    
    def set_tenant_policy(self, policy: TenantModelPolicy) -> None:
        """Set model policy for a tenant."""
        with self._lock:
            self._tenant_policies[policy.tenant_id] = policy
    
    def get_tenant_policy(self, tenant_id: str) -> Optional[TenantModelPolicy]:
        """Get model policy for a tenant."""
        return self._tenant_policies.get(tenant_id)
    
    def set_availability(self, model_id: str, available: bool) -> bool:
        """Set model availability."""
        with self._lock:
            if model_id in self._models:
                self._models[model_id].is_available = available
                return True
            return False

