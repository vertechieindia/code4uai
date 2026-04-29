from __future__ import annotations
"""LLM configuration for code4u.ai.

Supports multiple providers via environment variables:
  - OPENAI_API_KEY      → OpenAI (GPT-4o, GPT-4o-mini)
  - ANTHROPIC_API_KEY   → Anthropic (Claude 3.5 Sonnet)
  - LLM_VLLM_HOST      → Self-hosted vLLM
  - (none)              → Local fallback (AST-based, no network)

Provider auto-detection order: OpenAI → Anthropic → vLLM → local.
"""
import os
from typing import Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseModel):
    """Configuration for a single model."""
    name: str
    endpoint: str
    max_tokens: int = 8192
    temperature: float = 0.0
    supports_lora: bool = True
    cost_per_1k_tokens: float = 0.0


class LLMSettings(BaseSettings):
    """LLM infrastructure settings."""
    model_config = SettingsConfigDict(env_prefix="LLM_", case_sensitive=False)

    # Provider (auto-detected if empty): openai | anthropic | vllm | local
    provider: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # vLLM server configuration
    vllm_host: str = "localhost"
    vllm_port: int = 8001
    vllm_api_key: str = "code4u-internal"

    # Primary model (Qwen2.5-Coder 32B)
    primary_model: str = "Qwen/Qwen2.5-Coder-32B"
    primary_lora_path: Optional[str] = "./lora-adapters/code4u-v1"

    # Fallback model (Mixtral for cheaper ops)
    fallback_model: str = "mistralai/Mixtral-8x7B-Instruct-v0.1"

    # Embedding model (self-hosted)
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_endpoint: str = "http://localhost:8002"

    # Inference settings
    max_batch_size: int = 32
    max_concurrent_requests: int = 100
    request_timeout_seconds: int = 120

    # Cost routing thresholds
    use_fallback_for_simple_tasks: bool = True
    simple_task_token_threshold: int = 1000

    @property
    def vllm_base_url(self) -> str:
        return f"http://{self.vllm_host}:{self.vllm_port}/v1"

    @property
    def resolved_provider(self) -> str:
        """Auto-detect the best available provider."""
        if self.provider:
            return self.provider

        openai_key = self.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            return "openai"

        anthropic_key = self.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            return "anthropic"

        return "local"

    @property
    def resolved_api_key(self) -> str:
        """Return the API key for the resolved provider."""
        provider = self.resolved_provider
        if provider == "openai":
            return self.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        if provider == "anthropic":
            return self.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if provider == "vllm":
            return self.vllm_api_key
        return ""

    @property
    def resolved_model(self) -> str:
        """Return the model name for the resolved provider."""
        provider = self.resolved_provider
        if provider == "openai":
            return self.openai_model
        if provider == "anthropic":
            return self.anthropic_model
        if provider == "vllm":
            return self.primary_model
        return "local"

    @property
    def resolved_base_url(self) -> str:
        """Return the base URL for the resolved provider."""
        provider = self.resolved_provider
        if provider == "openai":
            return self.openai_base_url
        if provider == "anthropic":
            return "https://api.anthropic.com"
        if provider == "vllm":
            return self.vllm_base_url
        return ""


def get_llm_settings() -> LLMSettings:
    return LLMSettings()
