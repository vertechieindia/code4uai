from __future__ import annotations
"""Prompt engineering for deterministic code generation."""
from dataclasses import dataclass
from typing import Any


@dataclass
class Prompt:
    """Structured prompt for LLM."""
    system: str
    user: str


class PromptBuilder:
    """
    Build constrained prompts for code4u.ai LLM.
    
    Key principles:
    - LLM is NOT a brain, it fills in code
    - All outputs must be structured (unified diff)
    - Constraints are explicit and enforced
    - No open-ended generation
    """
    
    SYSTEM_DIFF = """You are a DETERMINISTIC code refactoring engine for code4u.ai.

RULES (MUST FOLLOW):
1. Output ONLY unified diff format. No explanations.
2. Preserve existing code style, indentation, naming conventions.
3. Never introduce new dependencies unless explicitly requested.
4. Never break public APIs without flagging "BREAKING CHANGE".
5. If you cannot complete the task with confidence, output "INSUFFICIENT_CONTEXT".
6. All changes must be minimal and surgical.

OUTPUT FORMAT:
```diff
--- a/path/to/file
+++ b/path/to/file
@@ -line,count +line,count @@
 context line
-removed line
+added line
 context line
```
---END---"""

    SYSTEM_SCHEMA = """You are a SCHEMA VALIDATOR for code4u.ai.

RULES:
1. Analyze schema compatibility between versions.
2. Flag breaking changes: removed fields, type changes, required field additions.
3. Output structured JSON only.

OUTPUT FORMAT:
{
  "compatible": boolean,
  "breaking_changes": [...],
  "warnings": [...],
  "suggestions": [...]
}"""

    SYSTEM_EXPLAIN = """You are a CODE CHANGE EXPLAINER for code4u.ai.

RULES:
1. Explain what the diff does in 1-3 sentences.
2. List affected components.
3. Flag any risks.
4. Be concise and technical.

OUTPUT FORMAT:
{
  "summary": "...",
  "affected_components": [...],
  "risks": [...],
  "breaking_change": boolean
}"""

    @classmethod
    def build_diff_prompt(
        cls,
        instruction: str,
        context: Dict[str, Any],
        input_code: str,
        constraints: List[str]
    ) -> Prompt:
        """Build prompt for diff generation."""
        user_content = f"""INSTRUCTION:
{instruction}

CONTEXT:
- Language: {context.get('language', 'unknown')}
- Frameworks: {', '.join(context.get('frameworks', []))}
- File: {context.get('file_path', 'unknown')}

CONSTRAINTS:
{chr(10).join(f'- {c}' for c in constraints) if constraints else '- None specified'}

AFFECTED COMPONENTS:
{chr(10).join(f'- {c}' for c in context.get('affected_components', [])) if context.get('affected_components') else '- To be determined'}

INPUT CODE:
```{context.get('language', '')}
{input_code}
```

Generate the unified diff:"""
        
        return Prompt(system=cls.SYSTEM_DIFF, user=user_content)
    
    @classmethod
    def build_schema_validation_prompt(
        cls,
        old_schema: str,
        new_schema: str,
        schema_type: str = "pydantic"
    ) -> Prompt:
        """Build prompt for schema compatibility check."""
        user_content = f"""SCHEMA TYPE: {schema_type}

OLD SCHEMA:
```
{old_schema}
```

NEW SCHEMA:
```
{new_schema}
```

Analyze compatibility and output JSON:"""
        
        return Prompt(system=cls.SYSTEM_SCHEMA, user=user_content)
    
    @classmethod
    def build_explain_prompt(cls, diff: str, context: Dict[str, Any]) -> Prompt:
        """Build prompt for change explanation."""
        user_content = f"""DIFF:
```diff
{diff}
```

CONTEXT:
- Repository: {context.get('repository', 'unknown')}
- Service: {context.get('service', 'unknown')}
- Owner Team: {context.get('owner_team', 'unknown')}

Explain this change:"""
        
        return Prompt(system=cls.SYSTEM_EXPLAIN, user=user_content)
    
    @classmethod
    def build_refactor_prompt(
        cls,
        refactor_type: str,
        target: str,
        input_code: str,
        context: Dict[str, Any]
    ) -> Prompt:
        """Build prompt for specific refactoring operations."""
        instruction_map = {
            "rename": f"Rename '{target}' according to the naming convention",
            "extract_function": f"Extract the selected code into a new function named '{target}'",
            "extract_component": f"Extract the selected JSX into a new React component named '{target}'",
            "inline": f"Inline the function/variable '{target}'",
            "move": f"Move '{target}' to the specified location",
        }
        
        instruction = instruction_map.get(refactor_type, f"Perform {refactor_type} on '{target}'")
        
        return cls.build_diff_prompt(
            instruction=instruction,
            context=context,
            input_code=input_code,
            constraints=[
                "Preserve all existing functionality",
                "Update all references",
                "Maintain type safety"
            ]
        )

