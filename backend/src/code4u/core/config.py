from __future__ import annotations
"""Configuration management for code4u.ai."""
from functools import lru_cache
from typing import List, Literal, Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    app_name: str = "code4u.ai"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/code4u"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    openai_api_key: Optional[SecretStr] = None
    anthropic_api_key: Optional[SecretStr] = None
    default_llm_provider: Literal["openai", "anthropic", "local"] = "anthropic"
    default_llm_model: str = "claude-3-5-sonnet-20241022"
    jwt_secret_key: SecretStr = SecretStr("change-me-in-production")
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    github_client_id: str = ""
    github_client_secret: SecretStr = SecretStr("")
    github_redirect_uri: str = "http://localhost:5173/api/v1/auth/github/callback"
    repo_clone_base: str = "/tmp/code4u-repos"

    # Air-gapped mode — blocks all external API calls, forces local models
    air_gapped_mode: bool = False
    ollama_base_url: str = "http://localhost:11434"
    vllm_base_url: str = "http://localhost:8000/v1"
    local_vector_search: bool = False

@lru_cache
def get_settings() -> Settings:
    return Settings()

