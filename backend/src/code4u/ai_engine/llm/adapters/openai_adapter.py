"""OpenAI Adapter — GPT-4o and GPT-4o-mini."""

from __future__ import annotations

import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import structlog

from .base import AdapterResponse, BaseLLMAdapter, UsageMetrics

logger = structlog.get_logger("adapter.openai")

_DEFAULT_MODEL = "gpt-4o"
_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI Chat Completions API (GPT-4o / GPT-4o-mini)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: str = _DEFAULT_MODEL,
        timeout: int = 120,
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url or _DEFAULT_BASE_URL
        self._default_model = default_model
        self._client: Optional[httpx.AsyncClient] = None
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "openai"

    async def is_available(self) -> bool:
        return bool(self._api_key)

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        stop: Optional[List[str]] = None,
    ) -> AdapterResponse:
        client = self._ensure_client()
        model = model or self._default_model
        t0 = time.perf_counter()

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stop:
            payload["stop"] = stop

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        usage_raw = data.get("usage", {})
        input_tokens = usage_raw.get("prompt_tokens", 0)
        output_tokens = usage_raw.get("completion_tokens", 0)
        latency = (time.perf_counter() - t0) * 1000

        usage = UsageMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=UsageMetrics.estimate_cost(model, input_tokens, output_tokens),
            model=model,
            provider="openai",
            latency_ms=latency,
        )

        return AdapterResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", model),
            provider="openai",
            usage=usage,
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
            raw=data,
        )

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        client = self._ensure_client()
        model = model or self._default_model

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:]
                if chunk == "[DONE]":
                    break
                import json
                data = json.loads(chunk)
                delta = data.get("choices", [{}])[0].get("delta", {})
                text = delta.get("content", "")
                if text:
                    yield text

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
