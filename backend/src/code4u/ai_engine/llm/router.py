from __future__ import annotations
"""Cost-aware model routing for code4u.ai."""
from enum import Enum
from typing import Any
import structlog

from code4u.ai_engine.llm.config import get_llm_settings

logger = structlog.get_logger("llm.router")


class TaskComplexity(str, Enum):
    """Task complexity levels for routing."""
    TRIVIAL = "trivial"      # Simple renames, formatting
    SIMPLE = "simple"        # Single-file changes
    MODERATE = "moderate"    # Multi-file, single repo
    COMPLEX = "complex"      # Cross-repo, schema changes
    CRITICAL = "critical"    # Breaking changes, API evolution


class ModelRouter:
    """
    Route requests to appropriate models based on:
    - Task complexity
    - Cost optimization
    - LoRA adapter availability
    
    This is NOT about picking the "smartest" model.
    It's about using the RIGHT model for determinism + cost.
    """
    
    def __init__(self):
        self.settings = get_llm_settings()
    
    def route(
        self,
        task_type: str,
        context: Dict[str, Any],
        estimated_tokens: int = 0
    ) -> Dict[str, Any]:
        """
        Determine model configuration for a task.
        
        Returns:
            {
                "model": str,
                "lora_adapter": Optional[str],
                "temperature": float,
                "max_tokens": int,
                "reason": str
            }
        """
        complexity = self._assess_complexity(task_type, context)
        
        logger.info(
            "routing_request",
            task_type=task_type,
            complexity=complexity,
            estimated_tokens=estimated_tokens
        )
        
        # Critical tasks: Always use primary model with LoRA
        if complexity == TaskComplexity.CRITICAL:
            return {
                "model": self.settings.primary_model,
                "lora_adapter": "code4u",
                "temperature": 0.0,
                "max_tokens": 8192,
                "reason": "Critical task requires primary model with fine-tuning"
            }
        
        # Complex tasks: Primary model, may skip LoRA for flexibility
        if complexity == TaskComplexity.COMPLEX:
            return {
                "model": self.settings.primary_model,
                "lora_adapter": "code4u",
                "temperature": 0.0,
                "max_tokens": 6144,
                "reason": "Complex task requires primary model"
            }
        
        # Moderate tasks: Primary model
        if complexity == TaskComplexity.MODERATE:
            return {
                "model": self.settings.primary_model,
                "lora_adapter": "code4u",
                "temperature": 0.0,
                "max_tokens": 4096,
                "reason": "Moderate task uses primary model"
            }
        
        # Simple/Trivial: Use fallback if configured for cost savings
        if (
            self.settings.use_fallback_for_simple_tasks and
            estimated_tokens < self.settings.simple_task_token_threshold
        ):
            return {
                "model": self.settings.fallback_model,
                "lora_adapter": None,
                "temperature": 0.0,
                "max_tokens": 2048,
                "reason": "Simple task routed to fallback model for cost"
            }
        
        # Default: Primary model
        return {
            "model": self.settings.primary_model,
            "lora_adapter": "code4u",
            "temperature": 0.0,
            "max_tokens": 4096,
            "reason": "Default routing to primary model"
        }
    
    def _assess_complexity(
        self,
        task_type: str,
        context: Dict[str, Any]
    ) -> TaskComplexity:
        """Assess task complexity from context."""
        
        # Breaking change = Critical
        if context.get("breaking_change"):
            return TaskComplexity.CRITICAL
        
        # Schema/API changes = Critical
        if task_type in ["schema_evolution", "api_migration"]:
            return TaskComplexity.CRITICAL
        
        # Cross-repo = Complex
        affected_repos = context.get("affected_repositories", [])
        if len(affected_repos) > 1:
            return TaskComplexity.COMPLEX
        
        # Multi-file = Moderate to Complex
        affected_files = context.get("affected_files", [])
        if len(affected_files) > 5:
            return TaskComplexity.COMPLEX
        if len(affected_files) > 1:
            return TaskComplexity.MODERATE
        
        # Single file operations
        if task_type in ["rename", "format", "add_comment"]:
            return TaskComplexity.TRIVIAL
        
        if task_type in ["extract_function", "inline", "move"]:
            return TaskComplexity.SIMPLE
        
        return TaskComplexity.MODERATE

