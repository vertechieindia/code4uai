from __future__ import annotations
"""LLM Executor with rejection, retry, and fallback for code4u.ai.

Execution flow:
1st attempt → Self-hosted model
2nd attempt → Self-hosted (with feedback)
3rd attempt → Premium fallback (GPT/Claude)

Day 4 additions:
  - ``execute_refactor_with_context`` — sends a surgically focused
    prompt (target symbol + callers from DependencyMap) and receives
    hunk-based edits instead of whole-file rewrites.
  - Multi-provider support via updated ``LLMClient``.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

from code4u.ai_engine.llm.client import LLMClient, LLMRequest
from code4u.ai_engine.llm.context_builder import (
    build_refactor_prompt,
    build_system_message,
)
from code4u.ai_engine.llm.hunk_parser import HunkResult, parse_and_apply
from code4u.ai_engine.llm.rejection import (
    RejectionPolicy,
    RetryManager,
    Rejection,
    RejectionType,
)
from code4u.ai_engine.compiler.prompt_compiler import PromptBundle

logger = structlog.get_logger("llm.executor")


@dataclass
class ExecutionResult:
    """Result of LLM execution."""
    success: bool
    response: Optional[str]
    parsed_output: Optional[Dict[str, Any]] = None
    
    # Execution metadata
    model_used: str = ""
    attempts: int = 1
    total_latency_ms: float = 0
    tokens_used: int = 0
    
    # Fallback tracking
    used_fallback: bool = False
    fallback_reason: Optional[str] = None
    
    # Rejection info
    final_rejection: Optional[Rejection] = None
    attempt_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Audit
    execution_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class LLMExecutor:
    """
    Execute LLM requests with full rejection/retry/fallback handling.
    
    The LLM is NEVER in control.
    """
    
    def __init__(
        self,
        client: Optional[LLMClient] = None,
        max_retries: int = 2,
        enable_fallback: bool = True
    ):
        self.client = client
        self.max_retries = max_retries
        self.enable_fallback = enable_fallback

    async def execute_refactor_simple(self, file_content: str, instruction: str) -> str:
        """
        Day-2: Call LLM with real file content and simple instruction.
        No schema enforcement, no retry. Returns raw response; raises on failure.
        """
        messages = [
            {"role": "system", "content": "You are a code refactoring assistant. Reply with the refactored code only when asked to change code."},
            {"role": "user", "content": f"Instruction: {instruction}\n\nFile content:\n```\n{file_content}\n```"},
        ]
        request = LLMRequest(messages=messages, temperature=0.0, max_tokens=4096)
        if self.client is None:
            self.client = LLMClient()
        response = await self.client.generate(request)
        return response.content

    async def execute_refactor_with_context(
        self,
        intent: str,
        file_path: str,
        file_content: str,
        symbol_name: str,
        language: str,
        caller_files: Optional[List[str]] = None,
    ) -> HunkResult:
        """Context-aware refactoring with hunk-based editing.

        Builds a surgically focused prompt containing only the target
        symbol and its callers, asks the LLM to return specific code
        hunks, and merges them into the original file.

        This method saves ~80% on tokens compared to whole-file rewrites
        and produces more accurate results because the LLM sees exactly
        how the symbol is used across the codebase.

        Args:
            intent: User's refactoring intent.
            file_path: Path to the file being refactored.
            file_content: Full content of the target file.
            symbol_name: Name of the symbol to refactor.
            language: Programming language (python, typescript, etc.).
            caller_files: Absolute paths of files that import the symbol.

        Returns:
            A ``HunkResult`` with the merged file content and hunk details.
        """
        prompt = build_refactor_prompt(
            intent=intent,
            file_path=file_path,
            file_content=file_content,
            symbol_name=symbol_name,
            language=language,
            caller_files=caller_files or [],
        )
        system_msg = build_system_message()

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ]
        request = LLMRequest(messages=messages, temperature=0.0, max_tokens=4096)

        if self.client is None:
            self.client = LLMClient()

        logger.info(
            "context_refactor_start",
            symbol=symbol_name,
            file=file_path,
            callers=len(caller_files or []),
            provider=self.client.provider,
        )

        response = await self.client.generate(request)

        result = parse_and_apply(response.content, file_content)

        logger.info(
            "context_refactor_complete",
            symbol=symbol_name,
            success=result.success,
            hunks=len(result.hunks),
            provider=response.provider,
            latency_ms=round(response.latency_ms, 1),
        )

        return result

    async def execute(
        self,
        bundle: PromptBundle,
        forbidden_paths: Optional[List[str]] = None
    ) -> ExecutionResult:
        """
        Execute compiled prompt with full rejection/retry handling.
        
        Flow:
        1. Try self-hosted model
        2. On soft rejection: retry with feedback
        3. On max retries: try fallback if enabled
        4. Return result with full audit trail
        """
        import uuid
        
        execution_id = str(uuid.uuid4())[:8]
        rejection_policy = RejectionPolicy(forbidden_paths)
        retry_manager = RetryManager(self.max_retries)
        
        # Set scope for rejection checking
        file_paths = [f.get("path", "") for f in bundle.scope_summary.get("files", [])]
        symbols = bundle.scope_summary.get("symbols", [])
        rejection_policy.set_scope(file_paths, symbols, forbidden_paths)
        
        total_latency = 0
        total_tokens = 0
        attempt = 0
        last_rejection: Optional[Rejection] = None
        
        messages = bundle.to_messages()
        
        logger.info(
            "execution_started",
            execution_id=execution_id,
            version=bundle.version
        )
        
        while attempt <= self.max_retries:
            attempt += 1
            
            # Add retry context if not first attempt
            if attempt > 1 and last_rejection:
                retry_context = retry_manager.build_retry_context(
                    last_rejection, attempt - 1
                )
                messages = self._add_retry_context(messages, retry_context)
            
            try:
                # Execute request
                request = LLMRequest(
                    messages=messages,
                    temperature=0.0,
                    max_tokens=4096,
                    lora_adapter="code4u"
                )
                
                if self.client is None:
                    # Mock for testing
                    from code4u.ai_engine.llm.client import LLMClient
                    self.client = LLMClient()
                
                response = await self.client.generate(request)
                total_latency += response.latency_ms
                total_tokens += response.usage.get("total_tokens", 0)
                
                # Evaluate response
                rejection = rejection_policy.evaluate(
                    response.content,
                    expected_format="json"
                )
                
                if rejection is None:
                    # Success!
                    logger.info(
                        "execution_success",
                        execution_id=execution_id,
                        attempt=attempt,
                        model=response.model
                    )
                    
                    return ExecutionResult(
                        success=True,
                        response=response.content,
                        parsed_output=self._parse_response(response.content),
                        model_used=response.model,
                        attempts=attempt,
                        total_latency_ms=total_latency,
                        tokens_used=total_tokens,
                        execution_id=execution_id,
                        attempt_log=retry_manager.get_attempt_log()
                    )
                
                # Handle rejection
                last_rejection = rejection
                
                if not retry_manager.should_retry(rejection, attempt):
                    # Hard rejection or max retries
                    break
                
                logger.warning(
                    "soft_rejection_retry",
                    execution_id=execution_id,
                    attempt=attempt,
                    reason=rejection.reason.value
                )
                
            except Exception as e:
                logger.error(
                    "execution_error",
                    execution_id=execution_id,
                    attempt=attempt,
                    error=str(e)
                )
                last_rejection = Rejection(
                    rejection_type=RejectionType.SOFT,
                    reason="execution_error",
                    message=str(e)
                )
        
        # All retries exhausted - try fallback if enabled
        if self.enable_fallback and last_rejection:
            fallback_result = await self._try_fallback(
                messages, bundle, execution_id
            )
            if fallback_result.success:
                fallback_result.attempt_log = retry_manager.get_attempt_log()
                return fallback_result
        
        # Complete failure
        logger.error(
            "execution_failed",
            execution_id=execution_id,
            attempts=attempt,
            final_reason=last_rejection.reason.value if last_rejection else "unknown"
        )
        
        return ExecutionResult(
            success=False,
            response=None,
            model_used="",
            attempts=attempt,
            total_latency_ms=total_latency,
            tokens_used=total_tokens,
            final_rejection=last_rejection,
            execution_id=execution_id,
            attempt_log=retry_manager.get_attempt_log()
        )
    
    async def _try_fallback(
        self,
        messages: list[Dict[str, str]],
        bundle: PromptBundle,
        execution_id: str
    ) -> ExecutionResult:
        """
        Try premium fallback model (GPT/Claude).
        
        This is:
        - Logged
        - Metered
        - Audited
        """
        logger.warning(
            "fallback_triggered",
            execution_id=execution_id,
            bundle_version=bundle.version
        )
        
        # In production, this would call OpenAI/Anthropic
        # For now, return failure
        return ExecutionResult(
            success=False,
            response=None,
            used_fallback=True,
            fallback_reason="Premium fallback not configured",
            execution_id=execution_id
        )
    
    def _add_retry_context(
        self,
        messages: list[Dict[str, str]],
        retry_context: "RetryContext"
    ) -> list[Dict[str, str]]:
        """Add retry context to messages."""
        # Insert retry context before the user message
        new_messages = messages[:-1]
        new_messages.append({
            "role": "system",
            "content": retry_context.to_prompt_addition()
        })
        new_messages.append(messages[-1])
        return new_messages
    
    def _parse_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse response content to dict."""
        import json
        import re
        
        try:
            return json.loads(content)
        except:
            pass
        
        # Try extracting from code block
        match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        return None

