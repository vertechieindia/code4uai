"""Air-Gapped Mode API.

Provides endpoints to toggle and inspect air-gapped (offline) mode.
When air-gapped mode is active:
  - Only LOCAL / SELF_HOSTED model providers are permitted.
  - External HTTP calls (OpenAI, Anthropic, OSV.dev) are blocked at the
    routing layer.
  - Secrets resolve exclusively from local environment variables.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import structlog

logger = structlog.get_logger("airgap")

router = APIRouter()

# ---------------------------------------------------------------------------
# Runtime state — survives across requests; reset on server restart
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_air_gapped: bool = os.getenv("AIR_GAPPED_MODE", "").lower() in ("1", "true", "yes")

BLOCKED_DOMAINS = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.x.ai",
    "api.groq.com",
    "api.together.xyz",
    "osv.dev",
    "api.github.com",
    "hooks.slack.com",
]

ALLOWED_PROVIDERS = {"local", "self_hosted", "ollama"}


def is_air_gapped() -> bool:
    """Thread-safe check of air-gapped status."""
    with _lock:
        return _air_gapped


def set_air_gapped(enabled: bool) -> None:
    global _air_gapped
    with _lock:
        _air_gapped = enabled
    logger.info("air_gapped_mode_changed", enabled=enabled)


def guard_external_call(provider: str, url: str = "") -> None:
    """Raise if an external call is attempted in air-gapped mode."""
    if not is_air_gapped():
        return
    if provider.lower() in ALLOWED_PROVIDERS:
        return
    for domain in BLOCKED_DOMAINS:
        if domain in url:
            raise RuntimeError(
                f"Air-gapped mode is active. External call to {domain} blocked. "
                "Switch to a local provider or disable air-gapped mode."
            )
    raise RuntimeError(
        f"Air-gapped mode is active. Provider '{provider}' is not allowed. "
        f"Only {ALLOWED_PROVIDERS} are permitted."
    )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AirGapToggle(BaseModel):
    enabled: bool


class AirGapStatus(BaseModel):
    enabled: bool
    allowedProviders: List[str]
    blockedDomains: List[str]
    ollamaUrl: str
    vllmUrl: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/airgap/status")
async def airgap_status() -> AirGapStatus:
    """Return current air-gapped mode status and configuration."""
    from code4u.core import get_settings
    s = get_settings()
    return AirGapStatus(
        enabled=is_air_gapped(),
        allowedProviders=sorted(ALLOWED_PROVIDERS),
        blockedDomains=BLOCKED_DOMAINS,
        ollamaUrl=s.ollama_base_url,
        vllmUrl=s.vllm_base_url,
    )


@router.post("/airgap/toggle")
async def airgap_toggle(body: AirGapToggle) -> Dict[str, Any]:
    """Enable or disable air-gapped mode at runtime."""
    set_air_gapped(body.enabled)
    return {
        "status": "ok",
        "airGapped": body.enabled,
        "message": (
            "Air-gapped mode enabled. Only local models will be used."
            if body.enabled
            else "Air-gapped mode disabled. Cloud providers are available."
        ),
    }


@router.get("/airgap/providers")
async def airgap_providers() -> Dict[str, Any]:
    """List models available under current mode (air-gapped vs cloud)."""
    from code4u.ai_engine.model_picker.registry import ModelRegistry
    from code4u.ai_engine.model_picker.models import ModelProvider

    registry = ModelRegistry()
    models = registry.list_all()

    if is_air_gapped():
        models = [
            m for m in models
            if m.provider in (ModelProvider.LOCAL, ModelProvider.SELF_HOSTED)
        ]

    return {
        "airGapped": is_air_gapped(),
        "modelCount": len(models),
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "provider": m.provider.value,
                "cost": m.input_cost_per_million + m.output_cost_per_million,
                "tags": m.tags,
            }
            for m in models
        ],
    }
