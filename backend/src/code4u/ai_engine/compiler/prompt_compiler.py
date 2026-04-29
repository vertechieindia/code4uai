from __future__ import annotations
"""Context → Prompt Compiler (CPC) for code4u.ai.

The LLM must comply with the compiled contract or gets rejected.
"""
from dataclasses import dataclass, field
from typing import Any
import structlog
import hashlib
import json

from code4u.ai_engine.compiler.types import (
    CompilerInput,
    CompiledScope,
    IntentType,
)
from code4u.ai_engine.compiler.constraints import ConstraintEncoder, Constraint
from code4u.ai_engine.compiler.scope_reducer import ScopeReducer, ScopeConfig

logger = structlog.get_logger("compiler.prompt")


@dataclass
class OutputSchema:
    """Expected output schema from LLM."""
    type: str
    properties: Dict[str, Any]
    required: List[str]
    
    def to_json(self) -> str:
        return json.dumps({
            "type": self.type,
            "properties": self.properties,
            "required": self.required
        }, indent=2)


@dataclass
class ValidationRule:
    """Post-generation validation rule."""
    name: str
    check: str
    severity: str = "error"


@dataclass
class PromptBundle:
    """
    Complete LLM execution contract.
    
    The LLM must comply or gets rejected.
    """
    # Prompts
    system_prompt: str
    developer_prompt: str
    user_prompt: str
    
    # Schema
    output_schema: OutputSchema
    
    # Validation
    validation_rules: list[ValidationRule]
    
    # Metadata
    version: str
    input_hash: str
    scope_summary: Dict[str, Any]
    constraints_encoded: Dict[str, Any]
    
    def to_messages(self) -> list[Dict[str, str]]:
        """Convert to chat messages format."""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        if self.developer_prompt:
            messages.append({"role": "assistant", "content": self.developer_prompt})
        messages.append({"role": "user", "content": self.user_prompt})
        return messages


# Output schemas
DIFF_OUTPUT_SCHEMA = OutputSchema(
    type="object",
    properties={
        "diffs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "diff": {"type": "string"},
                },
                "required": ["file_path", "diff"]
            }
        },
        "breaking_change": {"type": "boolean"},
        "summary": {"type": "string"}
    },
    required=["diffs"]
)

EXPLAIN_OUTPUT_SCHEMA = OutputSchema(
    type="object",
    properties={
        "explanation": {"type": "string"},
        "affected_components": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}}
    },
    required=["explanation"]
)


class PromptCompiler:
    """
    Compile deterministic context into constrained LLM prompts.
    
    Phases:
    1. Scope Reduction - Max 5-12 files, 20 symbols
    2. Constraint Encoding - Machine rules, not English
    3. Structured Assembly - No conversational tone
    """
    
    VERSION = "1.0.0"
    
    def __init__(
        self,
        scope_config: ScopeConfig | None = None,
    ):
        self.scope_reducer = ScopeReducer(scope_config)
        self.constraint_encoder = ConstraintEncoder()
    
    def compile(self, input: CompilerInput) -> PromptBundle:
        """
        Compile input into LLM execution contract.
        
        This is versioned. If prompts regress → rollback.
        """
        logger.info(
            "compiling_prompt",
            intent=input.intent.value,
            target=input.target_node_id,
            constraint_count=len(input.constraints)
        )
        
        # Phase 1: Scope Reduction
        scope = self.scope_reducer.reduce(input)
        
        # Phase 2: Constraint Encoding
        encoded_constraints = self.constraint_encoder.encode(
            constraints=input.constraints,
            intent=input.intent.value,
            ownership=input.ownership
        )
        
        # Phase 3: Structured Assembly
        system_prompt = self._build_system_prompt(input)
        developer_prompt = self._build_developer_prompt(input, scope)
        user_prompt = self._build_user_prompt(input, scope, encoded_constraints)
        
        # Select output schema
        output_schema = self._select_output_schema(input.intent)
        
        # Build validation rules
        validation_rules = self._build_validation_rules(encoded_constraints)
        
        # Calculate input hash for caching/versioning
        input_hash = self._hash_input(input)
        
        bundle = PromptBundle(
            system_prompt=system_prompt,
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
            output_schema=output_schema,
            validation_rules=validation_rules,
            version=self.VERSION,
            input_hash=input_hash,
            scope_summary={
                "file_count": len(scope.files),
                "symbol_count": len(scope.symbols_in_scope),
                "estimated_tokens": scope.total_tokens_estimate,
            },
            constraints_encoded=encoded_constraints,
        )
        
        logger.info(
            "prompt_compiled",
            version=self.VERSION,
            scope_files=len(scope.files),
            estimated_tokens=scope.total_tokens_estimate
        )
        
        return bundle
    
    def _build_system_prompt(self, input: CompilerInput) -> str:
        """Build the system prompt - sets the execution context."""
        language = input.language_profile.language
        frameworks = ", ".join(input.language_profile.frameworks) or "none"
        
        return f"""You are a DETERMINISTIC code refactoring engine for code4u.ai.

IDENTITY:
- You are NOT a general assistant
- You are NOT conversational
- You ONLY modify provided code
- You do NOT invent APIs, imports, or types

LANGUAGE CONTEXT:
- Primary language: {language}
- Frameworks: {frameworks}
- Type system: {input.language_profile.type_system}

EXECUTION RULES:
1. Output ONLY the required format (unified diff or JSON)
2. Do NOT add explanations unless explicitly requested
3. Do NOT modify files not in your scope
4. STOP and output "INSUFFICIENT_CONTEXT" if you cannot complete with confidence

REJECTION TRIGGERS (your output will be rejected if):
- Invalid JSON/diff format
- Touching forbidden files
- Inventing APIs or symbols
- Exceeding scope
- Violating ownership boundaries"""

    def _build_developer_prompt(
        self,
        input: CompilerInput,
        scope: CompiledScope
    ) -> str:
        """Build developer context prompt."""
        lines = ["CONTEXT SUMMARY:"]
        lines.append(f"- Files in scope: {len(scope.files)}")
        lines.append(f"- Primary file: {scope.primary_file_id}")
        lines.append(f"- Symbols: {', '.join(scope.symbols_in_scope[:10])}")
        
        if input.ownership:
            owners = [o.team_name for o in input.ownership]
            lines.append(f"- Code owners: {', '.join(owners)}")
        
        if input.change_plan.breaking_change:
            lines.append("- ⚠️ BREAKING CHANGE EXPECTED")
        
        return "\n".join(lines)
    
    def _build_user_prompt(
        self,
        input: CompilerInput,
        scope: CompiledScope,
        constraints: Dict[str, Any]
    ) -> str:
        """Build the user prompt with task and files."""
        lines = []
        
        # Task section
        lines.append(f"TASK: {input.intent.value.upper()}")
        if input.user_instruction:
            lines.append(f"INSTRUCTION: {input.user_instruction}")
        lines.append("")
        
        # Files section
        lines.append("FILES:")
        for i, file in enumerate(scope.files):
            readonly_marker = " [READONLY]" if file.is_readonly else ""
            primary_marker = " [PRIMARY]" if file.is_primary else ""
            lines.append(f'<file id="{i}" path="{file.path}"{primary_marker}{readonly_marker}>')
            if file.content:
                lines.append(file.content[:4000])  # Truncate long files
            lines.append("</file>")
            lines.append("")
        
        # Constraints section
        lines.append(self.constraint_encoder.to_prompt_section(constraints))
        lines.append("")
        
        # Output format section
        lines.append("OUTPUT FORMAT:")
        lines.append("Return ONLY a JSON object matching this schema:")
        lines.append("```json")
        lines.append(self._select_output_schema(input.intent).to_json())
        lines.append("```")
        
        return "\n".join(lines)
    
    def _select_output_schema(self, intent: IntentType) -> OutputSchema:
        """Select appropriate output schema for intent."""
        if intent == IntentType.EXPLAIN:
            return EXPLAIN_OUTPUT_SCHEMA
        return DIFF_OUTPUT_SCHEMA
    
    def _build_validation_rules(
        self,
        constraints: Dict[str, Any]
    ) -> list[ValidationRule]:
        """Build post-generation validation rules."""
        rules = []
        
        for validation in constraints.get("required_validations", []):
            rules.append(ValidationRule(
                name=validation,
                check=validation,
                severity="error" if validation != "detect_breaking_changes" else "warning"
            ))
        
        # Always validate output format
        rules.append(ValidationRule(
            name="validate_json_format",
            check="json.loads",
            severity="error"
        ))
        
        return rules
    
    def _hash_input(self, input: CompilerInput) -> str:
        """Generate hash of input for caching/versioning."""
        content = json.dumps({
            "intent": input.intent.value,
            "target": input.target_node_id,
            "constraints": [c.constraint_type.value for c in input.constraints],
            "version": self.VERSION,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

