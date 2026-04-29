"""Anthropic Adapter — Claude 3.5 Sonnet with XML-style prompting."""

from __future__ import annotations

import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import structlog

from .base import AdapterResponse, BaseLLMAdapter, UsageMetrics

logger = structlog.get_logger("adapter.anthropic")

_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_BASE_URL = "https://api.anthropic.com"


class AnthropicAdapter(BaseLLMAdapter):
    """Adapter for Anthropic Messages API (Claude 3.5 Sonnet).

    Tuned for XML-style prompting — wraps code blocks in ``<code>``
    tags and structures instructions with ``<task>`` / ``<context>``
    elements when the message content is plain text.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = _DEFAULT_MODEL,
        timeout: int = 120,
    ):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._default_model = default_model
        self._client: Optional[httpx.AsyncClient] = None
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def is_available(self) -> bool:
        return bool(self._api_key)

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=_BASE_URL,
                timeout=httpx.Timeout(self._timeout),
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            )
        return self._client

    @staticmethod
    def _split_system(messages: List[Dict[str, str]]):
        """Separate the system message (Anthropic uses a top-level field)."""
        system = ""
        user_msgs: List[Dict[str, str]] = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_msgs.append({"role": m["role"], "content": m["content"]})
        return system, user_msgs

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

        system, user_msgs = self._split_system(messages)

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": user_msgs,
        }
        if system:
            payload["system"] = system
        if temperature > 0:
            payload["temperature"] = temperature
        if stop:
            payload["stop_sequences"] = stop

        response = await client.post("/v1/messages", json=payload)
        response.raise_for_status()
        data = response.json()

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage_raw = data.get("usage", {})
        input_tokens = usage_raw.get("input_tokens", 0)
        output_tokens = usage_raw.get("output_tokens", 0)
        latency = (time.perf_counter() - t0) * 1000

        usage = UsageMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=UsageMetrics.estimate_cost(model, input_tokens, output_tokens),
            model=model,
            provider="anthropic",
            latency_ms=latency,
        )

        return AdapterResponse(
            content=content,
            model=data.get("model", model),
            provider="anthropic",
            usage=usage,
            finish_reason=data.get("stop_reason", "end_turn"),
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
        system, user_msgs = self._split_system(messages)

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": user_msgs,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if temperature > 0:
            payload["temperature"] = temperature

        async with client.stream("POST", "/v1/messages", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                import json
                data = json.loads(line[6:])
                if data.get("type") == "content_block_delta":
                    text = data.get("delta", {}).get("text", "")
                    if text:
                        yield text

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
