"""Ollama Adapter — local, offline refactoring with Llama 3.1.

Enables privacy-conscious users to run refactoring entirely on their
own machine using Ollama-served models.  No data leaves the network.
"""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import structlog

from .base import AdapterResponse, BaseLLMAdapter, UsageMetrics

logger = structlog.get_logger("adapter.ollama")

_DEFAULT_MODEL = "llama3.1"
_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaAdapter(BaseLLMAdapter):
    """Adapter for Ollama (local LLM server).

    Uses the OpenAI-compatible ``/v1/chat/completions`` endpoint
    exposed by Ollama.  Cost is always $0.00.
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        default_model: str = _DEFAULT_MODEL,
        timeout: int = 300,
    ):
        self._base_url = base_url
        self._default_model = default_model
        self._client: Optional[httpx.AsyncClient] = None
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def is_available(self) -> bool:
        """Check if Ollama is running by hitting /api/tags."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                r = await client.get(f"{self._base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
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
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if stop:
            payload["options"]["stop"] = stop

        response = await client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        content = data.get("message", {}).get("content", "")
        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)
        latency = (time.perf_counter() - t0) * 1000

        usage = UsageMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=0.0,
            model=model,
            provider="ollama",
            latency_ms=latency,
        )

        return AdapterResponse(
            content=content,
            model=model,
            provider="ollama",
            usage=usage,
            finish_reason="stop",
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

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            import json
            async for line in resp.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                text = data.get("message", {}).get("content", "")
                if text:
                    yield text
                if data.get("done"):
                    break

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
