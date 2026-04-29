"""Tests for Day 13: Multi-LLM Switchboard.

Covers:
  - BaseLLMAdapter contract and UsageMetrics.
  - SmartRouter complexity classification.
  - SmartRouter failover between adapters.
  - TokenMonitor kill-switch at 10K tokens.
  - TokenMonitor cost budget enforcement.
  - Adapter availability checks.
  - Cost estimation accuracy.
"""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from code4u.ai_engine.llm.adapters.base import (
    AdapterResponse,
    BaseLLMAdapter,
    UsageMetrics,
    COST_TABLE,
)
from code4u.ai_engine.llm.adapters.openai_adapter import OpenAIAdapter
from code4u.ai_engine.llm.adapters.anthropic_adapter import AnthropicAdapter
from code4u.ai_engine.llm.adapters.ollama_adapter import OllamaAdapter
from code4u.ai_engine.llm.smart_router import (
    SmartRouter,
    RoutingDecision,
    classify_complexity,
    ComplexityLevel,
    CHEAP_MODELS,
    PREMIUM_MODELS,
)
from code4u.ai_engine.llm.token_monitor import (
    TokenMonitor,
    TokenBudgetExceeded,
    CostBudgetExceeded,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Fake adapter for testing
# ---------------------------------------------------------------------------

class FakeAdapter(BaseLLMAdapter):
    """In-memory adapter for testing router behavior."""

    def __init__(
        self,
        name: str = "fake",
        available: bool = True,
        response_content: str = "OK",
        fail_on_call: bool = False,
        output_tokens: int = 50,
    ):
        self._name = name
        self._available = available
        self._response_content = response_content
        self._fail_on_call = fail_on_call
        self._output_tokens = output_tokens
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._name

    async def is_available(self) -> bool:
        return self._available

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        stop: Optional[List[str]] = None,
    ) -> AdapterResponse:
        self.call_count += 1
        if self._fail_on_call:
            raise RuntimeError(f"{self._name} is down")
        return AdapterResponse(
            content=self._response_content,
            model=model or "fake-model",
            provider=self._name,
            usage=UsageMetrics(
                input_tokens=100,
                output_tokens=self._output_tokens,
                total_tokens=100 + self._output_tokens,
                estimated_cost_usd=UsageMetrics.estimate_cost(
                    model or "gpt-4o-mini", 100, self._output_tokens
                ),
                model=model or "fake-model",
                provider=self._name,
                latency_ms=10.0,
            ),
        )

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        yield self._response_content


# ---------------------------------------------------------------------------
# Test: UsageMetrics
# ---------------------------------------------------------------------------

class TestUsageMetrics:
    def test_cost_estimation_gpt4o(self):
        cost = UsageMetrics.estimate_cost("gpt-4o", 1000, 1000)
        assert cost == pytest.approx(0.0025 + 0.01, rel=0.01)

    def test_cost_estimation_gpt4o_mini(self):
        cost = UsageMetrics.estimate_cost("gpt-4o-mini", 1000, 1000)
        assert cost == pytest.approx(0.00015 + 0.0006, rel=0.01)

    def test_cost_estimation_local_is_zero(self):
        cost = UsageMetrics.estimate_cost("local", 5000, 5000)
        assert cost == 0.0

    def test_cost_estimation_unknown_model_is_zero(self):
        cost = UsageMetrics.estimate_cost("unknown-model-xyz", 1000, 1000)
        assert cost == 0.0

    def test_to_dict(self):
        u = UsageMetrics(
            input_tokens=100, output_tokens=200, total_tokens=300,
            estimated_cost_usd=0.005, model="gpt-4o", provider="openai",
            latency_ms=150.123,
        )
        d = u.to_dict()
        assert d["inputTokens"] == 100
        assert d["outputTokens"] == 200
        assert d["provider"] == "openai"
        assert d["latencyMs"] == 150.1


# ---------------------------------------------------------------------------
# Test: Complexity Classification
# ---------------------------------------------------------------------------

class TestComplexityClassification:
    def test_rename_is_cheap(self):
        assert classify_complexity("Rename foo to bar") == ComplexityLevel.CHEAP

    def test_health_is_cheap(self):
        assert classify_complexity("health check") == ComplexityLevel.CHEAP

    def test_unused_import_is_cheap(self):
        assert classify_complexity("fix unused imports") == ComplexityLevel.CHEAP

    def test_extract_is_premium(self):
        assert classify_complexity("Extract calculate_total to utils.py") == ComplexityLevel.PREMIUM

    def test_convert_to_class_is_premium(self):
        assert classify_complexity("Convert this function to class") == ComplexityLevel.PREMIUM

    def test_optimize_is_premium(self):
        assert classify_complexity("Optimize the loop for better performance") == ComplexityLevel.PREMIUM

    def test_rewrite_is_premium(self):
        assert classify_complexity("Rewrite the authentication module") == ComplexityLevel.PREMIUM

    def test_multi_file_is_always_premium(self):
        assert classify_complexity("Rename x to y", file_count=3) == ComplexityLevel.PREMIUM

    def test_short_generic_is_cheap(self):
        assert classify_complexity("fix typo") == ComplexityLevel.CHEAP

    def test_long_generic_is_premium(self):
        long = "Please restructure this entire module hierarchy and rearchitect the data flow"
        assert classify_complexity(long) == ComplexityLevel.PREMIUM


# ---------------------------------------------------------------------------
# Test: SmartRouter — basic routing
# ---------------------------------------------------------------------------

class TestSmartRouterBasic:
    def test_routes_to_available_adapter(self):
        adapter = FakeAdapter(name="openai")
        router = SmartRouter(adapters=[adapter])

        async def _do():
            resp, decision = await router.route(
                messages=[{"role": "user", "content": "hello"}],
                intent="Rename foo to bar",
            )
            return resp, decision

        resp, decision = _run(_do())
        assert resp.provider == "openai"
        assert decision.complexity == ComplexityLevel.CHEAP
        assert decision.fallback_used is False

    def test_skips_unavailable_adapter(self):
        unavailable = FakeAdapter(name="openai", available=False)
        available = FakeAdapter(name="anthropic")
        router = SmartRouter(adapters=[unavailable, available])

        async def _do():
            resp, decision = await router.route(
                messages=[{"role": "user", "content": "hello"}],
                intent="Rename foo to bar",
            )
            return resp, decision

        resp, decision = _run(_do())
        assert resp.provider == "anthropic"
        assert unavailable.call_count == 0
        assert available.call_count == 1


# ---------------------------------------------------------------------------
# Test: SmartRouter — failover
# ---------------------------------------------------------------------------

class TestSmartRouterFailover:
    def test_failover_on_error(self):
        failing = FakeAdapter(name="openai", fail_on_call=True)
        backup = FakeAdapter(name="anthropic")
        router = SmartRouter(adapters=[failing, backup])

        async def _do():
            resp, decision = await router.route(
                messages=[{"role": "user", "content": "extract logic"}],
                intent="Extract function to new file",
            )
            return resp, decision

        resp, decision = _run(_do())
        assert resp.provider == "anthropic"
        assert decision.fallback_used is True
        assert failing.call_count == 1
        assert backup.call_count == 1

    def test_all_adapters_fail_raises_runtime(self):
        a1 = FakeAdapter(name="openai", fail_on_call=True)
        a2 = FakeAdapter(name="anthropic", fail_on_call=True)
        router = SmartRouter(adapters=[a1, a2])

        async def _do():
            with pytest.raises(RuntimeError, match="All.*adapters failed"):
                await router.route(
                    messages=[{"role": "user", "content": "hello"}],
                    intent="test",
                )

        _run(_do())

    def test_no_adapters_raises_runtime(self):
        router = SmartRouter(adapters=[])

        async def _do():
            with pytest.raises(RuntimeError):
                await router.route(
                    messages=[{"role": "user", "content": "hello"}],
                    intent="test",
                )

        _run(_do())


# ---------------------------------------------------------------------------
# Test: SmartRouter — cumulative tracking
# ---------------------------------------------------------------------------

class TestSmartRouterCumulative:
    def test_tracks_cumulative_cost(self):
        adapter = FakeAdapter(name="openai", output_tokens=200)
        router = SmartRouter(adapters=[adapter])

        async def _do():
            await router.route(
                messages=[{"role": "user", "content": "a"}], intent="Rename a to b",
            )
            await router.route(
                messages=[{"role": "user", "content": "b"}], intent="Rename c to d",
            )

        _run(_do())
        assert router.cumulative_tokens == 600  # 2 calls × 300 tokens
        assert router.cumulative_cost > 0

    def test_force_provider(self):
        a1 = FakeAdapter(name="openai")
        a2 = FakeAdapter(name="anthropic")
        router = SmartRouter(adapters=[a1, a2])

        async def _do():
            resp, _ = await router.route(
                messages=[{"role": "user", "content": "x"}],
                intent="test",
                force_provider="anthropic",
            )
            return resp

        resp = _run(_do())
        assert resp.provider == "anthropic"


# ---------------------------------------------------------------------------
# Test: TokenMonitor
# ---------------------------------------------------------------------------

class TestTokenMonitor:
    def test_normal_usage_passes(self):
        monitor = TokenMonitor()
        usage = UsageMetrics(input_tokens=100, output_tokens=500, total_tokens=600)
        monitor.check(usage)
        assert monitor.total_tokens == 600
        assert not monitor.aborted

    def test_kills_on_10k_output_tokens(self):
        monitor = TokenMonitor(max_response_tokens=10_000)
        usage = UsageMetrics(input_tokens=100, output_tokens=10_001, total_tokens=10_101)
        with pytest.raises(TokenBudgetExceeded) as exc_info:
            monitor.check(usage)
        assert exc_info.value.tokens == 10_001
        assert exc_info.value.limit == 10_000
        assert monitor.aborted
        assert monitor.abort_reason == "token_budget_exceeded"

    def test_passes_at_exactly_10k(self):
        monitor = TokenMonitor(max_response_tokens=10_000)
        usage = UsageMetrics(input_tokens=100, output_tokens=10_000, total_tokens=10_100)
        monitor.check(usage)
        assert not monitor.aborted

    def test_kills_on_cost_exceeded(self):
        monitor = TokenMonitor(max_session_cost_usd=0.05)
        u1 = UsageMetrics(estimated_cost_usd=0.03, output_tokens=100, total_tokens=200)
        u2 = UsageMetrics(estimated_cost_usd=0.03, output_tokens=100, total_tokens=200)
        monitor.check(u1)
        with pytest.raises(CostBudgetExceeded) as exc_info:
            monitor.check(u2)
        assert exc_info.value.cost > 0.05
        assert monitor.aborted
        assert monitor.abort_reason == "cost_budget_exceeded"

    def test_summary_structure(self):
        monitor = TokenMonitor()
        u = UsageMetrics(
            input_tokens=100, output_tokens=200, total_tokens=300,
            estimated_cost_usd=0.002,
        )
        monitor.check(u)
        s = monitor.summary
        assert s["totalCalls"] == 1
        assert s["totalInputTokens"] == 100
        assert s["totalOutputTokens"] == 200
        assert s["totalCostUsd"] == 0.002
        assert s["aborted"] is False

    def test_multiple_calls_accumulate(self):
        monitor = TokenMonitor()
        for _ in range(5):
            monitor.check(UsageMetrics(
                input_tokens=50, output_tokens=100, total_tokens=150,
                estimated_cost_usd=0.001,
            ))
        assert monitor.total_tokens == 750
        assert len(monitor.calls) == 5
        assert monitor.total_cost_usd == pytest.approx(0.005, rel=0.01)


# ---------------------------------------------------------------------------
# Test: Adapter availability
# ---------------------------------------------------------------------------

class TestAdapterAvailability:
    def test_openai_available_with_key(self):
        adapter = OpenAIAdapter(api_key="sk-test-key")
        assert _run(adapter.is_available()) is True

    def test_openai_unavailable_without_key(self):
        adapter = OpenAIAdapter(api_key="")
        assert _run(adapter.is_available()) is False

    def test_anthropic_available_with_key(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        assert _run(adapter.is_available()) is True

    def test_anthropic_unavailable_without_key(self):
        adapter = AnthropicAdapter(api_key="")
        assert _run(adapter.is_available()) is False

    def test_ollama_unavailable_without_server(self):
        adapter = OllamaAdapter(base_url="http://localhost:99999")
        assert _run(adapter.is_available()) is False

    def test_provider_names(self):
        assert OpenAIAdapter(api_key="k").provider_name == "openai"
        assert AnthropicAdapter(api_key="k").provider_name == "anthropic"
        assert OllamaAdapter().provider_name == "ollama"


# ---------------------------------------------------------------------------
# Test: Routing decision metadata
# ---------------------------------------------------------------------------

class TestRoutingDecision:
    def test_to_dict_basic(self):
        d = RoutingDecision(
            complexity="cheap",
            chosen_provider="openai",
            chosen_model="gpt-4o-mini",
        )
        result = d.to_dict()
        assert result["complexity"] == "cheap"
        assert result["chosenProvider"] == "openai"
        assert "fallbackUsed" not in result

    def test_to_dict_with_fallback(self):
        d = RoutingDecision(
            complexity="premium",
            chosen_provider="anthropic",
            chosen_model="claude-sonnet-4-20250514",
            fallback_used=True,
            fallback_provider="anthropic",
        )
        result = d.to_dict()
        assert result["fallbackUsed"] is True
        assert result["fallbackProvider"] == "anthropic"


# ---------------------------------------------------------------------------
# Test: E2E — router + monitor integration
# ---------------------------------------------------------------------------

class TestRouterMonitorIntegration:
    def test_monitor_catches_hallucination_from_router(self):
        """Adapter returns 15K tokens — monitor kills the job."""
        hallucinator = FakeAdapter(name="openai", output_tokens=15_000)
        router = SmartRouter(adapters=[hallucinator])
        monitor = TokenMonitor(max_response_tokens=10_000)

        async def _do():
            resp, decision = await router.route(
                messages=[{"role": "user", "content": "rewrite everything"}],
                intent="Rewrite the entire module",
            )
            with pytest.raises(TokenBudgetExceeded):
                monitor.check(resp.usage)
            assert monitor.aborted

        _run(_do())

    def test_normal_request_passes_monitor(self):
        adapter = FakeAdapter(name="openai", output_tokens=200)
        router = SmartRouter(adapters=[adapter])
        monitor = TokenMonitor()

        async def _do():
            resp, _ = await router.route(
                messages=[{"role": "user", "content": "rename x"}],
                intent="Rename x to y",
            )
            monitor.check(resp.usage)
            assert not monitor.aborted
            assert monitor.total_tokens == 300

        _run(_do())
