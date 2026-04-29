from __future__ import annotations
"""Multi-provider LLM client for code4u.ai.

Supports four providers:
  - **openai**     — OpenAI Chat Completions API (GPT-4o, etc.)
  - **anthropic**  — Anthropic Messages API (Claude 3.5 Sonnet, etc.)
  - **vllm**       — Self-hosted vLLM (OpenAI-compatible)
  - **local**      — Offline fallback; returns the input file unchanged
                     for whole-file requests, or echoes a deterministic
                     hunk response for hunk-based requests.

Provider is auto-detected from environment variables.
See ``LLMSettings.resolved_provider`` for detection order.
"""
import ast
import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
import httpx
import structlog

from code4u.ai_engine.llm.config import get_llm_settings, LLMSettings

logger = structlog.get_logger("llm.client")


class LLMResponse(BaseModel):
    """Structured response from LLM inference."""
    content: str
    model: str
    usage: Dict[str, int]
    latency_ms: float
    cached: bool = False
    lora_adapter: Optional[str] = None
    provider: str = ""


class LLMRequest(BaseModel):
    """Structured request for LLM inference."""
    messages: list[Dict[str, str]]
    model: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 4096
    stop: Optional[List[str]] = None
    lora_adapter: Optional[str] = None


class LLMClient:
    """Multi-provider LLM client.

    Detects the best available provider from environment variables
    and routes requests accordingly.  Falls back to ``local`` mode
    when no API key is configured — this mode applies deterministic
    AST-based transformations so the full pipeline can be tested
    without network access.
    """

    def __init__(self, settings: Optional[LLMSettings] = None):
        self.settings = settings or get_llm_settings()
        self._provider = self.settings.resolved_provider
        self._client: Optional[httpx.AsyncClient] = None
        self._request_cache: dict[str, LLMResponse] = {}
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_requests)

        if self._provider != "local":
            self._client = self._build_http_client()

        logger.info(
            "llm_client_init",
            provider=self._provider,
            model=self.settings.resolved_model,
        )

    @property
    def provider(self) -> str:
        return self._provider

    def _build_http_client(self) -> httpx.AsyncClient:
        base_url = self.settings.resolved_base_url
        api_key = self.settings.resolved_api_key
        headers: Dict[str, str] = {}

        if self._provider == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
            headers["content-type"] = "application/json"
        else:
            headers["Authorization"] = f"Bearer {api_key}"

        return httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(self.settings.request_timeout_seconds),
            headers=headers,
        )

    # -- generate -----------------------------------------------------------

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion using the resolved provider."""
        cache_key = self._cache_key(request)
        if cache_key in self._request_cache:
            cached = self._request_cache[cache_key]
            return LLMResponse(
                content=cached.content,
                model=cached.model,
                usage=cached.usage,
                latency_ms=cached.latency_ms,
                cached=True,
                provider=cached.provider,
            )

        async with self._semaphore:
            if self._provider == "local":
                return self._generate_local(request)
            if self._provider == "anthropic":
                return await self._generate_anthropic(request)
            return await self._generate_openai_compat(request)

    # -- OpenAI-compatible (OpenAI + vLLM) ----------------------------------

    async def _generate_openai_compat(self, request: LLMRequest) -> LLMResponse:
        assert self._client is not None
        start = time.perf_counter()

        model = request.model or self.settings.resolved_model
        if request.lora_adapter and self._provider == "vllm":
            model = f"{model}:{request.lora_adapter}"

        payload: Dict[str, Any] = {
            "model": model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.stop:
            payload["stop"] = request.stop

        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            result = LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data.get("model", model),
                usage=data.get("usage", {}),
                latency_ms=(time.perf_counter() - start) * 1000,
                lora_adapter=request.lora_adapter,
                provider=self._provider,
            )

            if request.temperature == 0.0:
                self._request_cache[self._cache_key(request)] = result

            logger.info(
                "llm_request_complete",
                provider=self._provider,
                model=result.model,
                latency_ms=round(result.latency_ms, 1),
                tokens=result.usage.get("total_tokens", 0),
            )
            return result

        except httpx.HTTPStatusError as e:
            logger.error("llm_request_failed", provider=self._provider, status=e.response.status_code)
            raise
        except Exception as e:
            logger.error("llm_request_error", provider=self._provider, error=str(e))
            raise

    # -- Anthropic native ---------------------------------------------------

    async def _generate_anthropic(self, request: LLMRequest) -> LLMResponse:
        assert self._client is not None
        start = time.perf_counter()

        model = request.model or self.settings.resolved_model
        system_msg = ""
        messages: List[Dict[str, str]] = []
        for m in request.messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                messages.append({"role": m["role"], "content": m["content"]})

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }
        if system_msg:
            payload["system"] = system_msg
        if request.temperature > 0:
            payload["temperature"] = request.temperature

        try:
            response = await self._client.post("/v1/messages", json=payload)
            response.raise_for_status()
            data = response.json()

            content_blocks = data.get("content", [])
            content = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    content += block.get("text", "")

            usage_data = data.get("usage", {})
            result = LLMResponse(
                content=content,
                model=data.get("model", model),
                usage={
                    "prompt_tokens": usage_data.get("input_tokens", 0),
                    "completion_tokens": usage_data.get("output_tokens", 0),
                    "total_tokens": usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
                },
                latency_ms=(time.perf_counter() - start) * 1000,
                provider="anthropic",
            )

            if request.temperature == 0.0:
                self._request_cache[self._cache_key(request)] = result

            logger.info(
                "llm_request_complete",
                provider="anthropic",
                model=result.model,
                latency_ms=round(result.latency_ms, 1),
                tokens=result.usage.get("total_tokens", 0),
            )
            return result

        except httpx.HTTPStatusError as e:
            logger.error("llm_request_failed", provider="anthropic", status=e.response.status_code)
            raise
        except Exception as e:
            logger.error("llm_request_error", provider="anthropic", error=str(e))
            raise

    # -- Local fallback (no network) ----------------------------------------

    def _generate_local(self, request: LLMRequest) -> LLMResponse:
        """Deterministic local fallback.

        Analyses the user message to decide what to return:
          - If the prompt asks for JSON hunks, return a valid hunk
            response based on AST analysis of the code.
          - Otherwise, return the original file content unchanged.
        """
        start = time.perf_counter()
        user_msg = ""
        for m in request.messages:
            if m["role"] == "user":
                user_msg = m["content"]

        if '"hunks"' in user_msg or "start_line" in user_msg:
            content = self._local_hunk_response(user_msg)
        else:
            content = self._local_whole_file_response(user_msg)

        return LLMResponse(
            content=content,
            model="local",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            latency_ms=(time.perf_counter() - start) * 1000,
            provider="local",
        )

    def _local_hunk_response(self, prompt: str) -> str:
        """Generate a hunk response by analysing the code in the prompt."""
        code_match = re.search(
            r"## Full File Content\s*```\w*\n(.*?)```",
            prompt,
            re.DOTALL,
        )
        if not code_match:
            return json.dumps({"hunks": []})

        numbered_code = code_match.group(1)
        lines: List[str] = []
        for raw_line in numbered_code.splitlines():
            m = re.match(r"\s*\d+\s*\|\s?(.*)", raw_line)
            if m:
                lines.append(m.group(1))
            else:
                lines.append(raw_line)

        code = "\n".join(lines)
        intent_match = re.search(r'## User Intent\s*"([^"]*)"', prompt)
        intent = intent_match.group(1).lower() if intent_match else ""

        hunks = self._find_optimizations(code, intent)
        return json.dumps({"hunks": hunks}, indent=2)

    def _find_optimizations(
        self, code: str, intent: str
    ) -> List[Dict[str, Any]]:
        """AST-based local optimization for Python code."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        code_lines = code.splitlines()
        hunks: List[Dict[str, Any]] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            func_start = node.lineno
            func_end = getattr(node, "end_lineno", node.lineno)
            func_lines = code_lines[func_start - 1 : func_end]
            func_body = "\n".join(func_lines)

            if any(kw in intent for kw in ("optim", "simplif", "performance", "faster", "rewrite", "improve")):
                optimized = self._optimize_function(node, func_body, code_lines)
                if optimized and optimized != func_body:
                    hunks.append({
                        "start_line": func_start,
                        "end_line": func_end,
                        "replacement": optimized,
                        "explanation": f"Optimized '{node.name}': simplified logic",
                    })

        return hunks

    def _optimize_function(
        self,
        node: ast.AST,
        func_source: str,
        all_lines: List[str],
    ) -> Optional[str]:
        """Apply mechanical optimizations to a Python function.

        Detected patterns:
          1. ``var = expr; return var`` → ``return expr``
          2. ``var = expr; return f(var)`` → ``return f(expr)``
             (inline intermediate variable into return expression)
        """
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return None

        body = node.body
        doc_nodes = []
        assign_nodes = []
        return_node = None

        for child in body:
            if isinstance(child, ast.Expr) and isinstance(child.value, (ast.Constant, ast.Str)):
                doc_nodes.append(child)
            elif isinstance(child, ast.Assign):
                assign_nodes.append(child)
            elif isinstance(child, ast.Return):
                return_node = child

        if (
            len(assign_nodes) == 1
            and return_node is not None
            and len(body) == len(doc_nodes) + 2
        ):
            assign = assign_nodes[0]
            if len(assign.targets) != 1 or not isinstance(assign.targets[0], ast.Name):
                return None

            var_name = assign.targets[0].id

            # Check if the return expression uses this variable
            return_source = self._get_source_segment(
                all_lines, return_node, node.lineno
            )
            if var_name not in return_source:
                return None

            func_start = node.lineno - 1
            func_end = getattr(node, "end_lineno", node.lineno)
            original_lines = all_lines[func_start:func_end]

            sig_line = original_lines[0]
            indent = "    "

            new_lines = [sig_line]
            for dn in doc_nodes:
                ds = dn.lineno - node.lineno
                de = getattr(dn, "end_lineno", dn.lineno) - node.lineno + 1
                new_lines.extend(original_lines[ds:de])

            # Get the RHS of the assignment
            assign_source = self._get_source_segment(
                all_lines, assign, node.lineno
            )
            eq_pos = assign_source.find("=")
            if eq_pos < 0:
                return None
            rhs = assign_source[eq_pos + 1:].strip()

            # Get the return expression source
            ret_source = return_source.strip()
            if ret_source.startswith("return "):
                ret_expr = ret_source[7:].strip()
            else:
                return None

            # Inline: replace the variable with the RHS expression
            inlined = re.sub(
                rf"\b{re.escape(var_name)}\b", rhs, ret_expr
            )
            new_lines.append(f"{indent}return {inlined}\n")

            return "\n".join(line.rstrip() for line in new_lines)

        return None

    @staticmethod
    def _get_source_segment(
        all_lines: List[str], node: ast.AST, func_lineno: int
    ) -> str:
        """Get source text of an AST node from the full-file lines."""
        start = node.lineno - 1
        end = getattr(node, "end_lineno", node.lineno)
        return " ".join(all_lines[start:end]).strip()

    def _local_whole_file_response(self, prompt: str) -> str:
        """For non-hunk requests, extract and return the file content."""
        code_match = re.search(r"```\n(.*?)```", prompt, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        return ""

    # -- utilities ----------------------------------------------------------

    def _cache_key(self, request: LLMRequest) -> str:
        import hashlib
        content = json.dumps({
            "messages": request.messages,
            "model": request.model,
            "temperature": request.temperature,
            "lora": request.lora_adapter,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
