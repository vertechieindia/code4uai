from __future__ import annotations
"""Constraint encoding for the Prompt Compiler.

Constraints are MACHINE LANGUAGE, not English fluff.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any
import structlog

logger = structlog.get_logger("compiler.constraints")


class ConstraintType(str, Enum):
    """Types of constraints the LLM must respect."""
    # Scope constraints
    DO_NOT_CREATE_NEW_FILES = "DO_NOT_CREATE_NEW_FILES"
    DO_NOT_DELETE_FILES = "DO_NOT_DELETE_FILES"
    MODIFY_ONLY_PROVIDED_FILES = "MODIFY_ONLY_PROVIDED_FILES"
    
    # API constraints
    DO_NOT_MODIFY_PUBLIC_API = "DO_NOT_MODIFY_PUBLIC_API"
    DO_NOT_ADD_NEW_EXPORTS = "DO_NOT_ADD_NEW_EXPORTS"
    DO_NOT_REMOVE_EXPORTS = "DO_NOT_REMOVE_EXPORTS"
    
    # Output constraints
    RETURN_UNIFIED_DIFF_ONLY = "RETURN_UNIFIED_DIFF_ONLY"
    RETURN_JSON_ONLY = "RETURN_JSON_ONLY"
    NO_EXPLANATIONS = "NO_EXPLANATIONS"
    
    # Style constraints
    PRESERVE_EXISTING_FORMATTING = "PRESERVE_EXISTING_FORMATTING"
    PRESERVE_COMMENTS = "PRESERVE_COMMENTS"
    FOLLOW_STYLE_GUIDE = "FOLLOW_STYLE_GUIDE"
    
    # Safety constraints
    NO_NEW_DEPENDENCIES = "NO_NEW_DEPENDENCIES"
    NO_UNSAFE_OPERATIONS = "NO_UNSAFE_OPERATIONS"
    PRESERVE_TYPE_SAFETY = "PRESERVE_TYPE_SAFETY"
    
    # Ownership constraints
    NO_CROSS_OWNER_EDITS = "NO_CROSS_OWNER_EDITS"
    REQUIRE_OWNER_APPROVAL = "REQUIRE_OWNER_APPROVAL"
    
    # Breaking change constraints
    FLAG_BREAKING_CHANGES = "FLAG_BREAKING_CHANGES"
    REQUIRE_MIGRATION_PLAN = "REQUIRE_MIGRATION_PLAN"


@dataclass
class Constraint:
    """A single constraint for LLM execution."""
    constraint_type: ConstraintType
    severity: str = "error"  # error, warning, info
    message: Optional[str] = None
    metadata: Dict[str, Any] | None = None
    
    def to_rule(self) -> str:
        """Convert to machine-readable rule."""
        return self.constraint_type.value


class ConstraintEncoder:
    """
    Encode constraints into machine-readable format.
    
    This is NOT English prose. It's a specification.
    """
    
    # Default constraints for all operations
    DEFAULT_CONSTRAINTS = [
        Constraint(ConstraintType.RETURN_UNIFIED_DIFF_ONLY),
        Constraint(ConstraintType.MODIFY_ONLY_PROVIDED_FILES),
        Constraint(ConstraintType.PRESERVE_EXISTING_FORMATTING),
        Constraint(ConstraintType.PRESERVE_TYPE_SAFETY),
    ]
    
    # Intent-specific constraint presets
    INTENT_CONSTRAINTS = {
        "refactor": [
            Constraint(ConstraintType.DO_NOT_CREATE_NEW_FILES),
            Constraint(ConstraintType.PRESERVE_COMMENTS),
        ],
        "rename": [
            Constraint(ConstraintType.DO_NOT_CREATE_NEW_FILES),
            Constraint(ConstraintType.DO_NOT_MODIFY_PUBLIC_API, severity="warning"),
        ],
        "add_api": [
            Constraint(ConstraintType.FLAG_BREAKING_CHANGES),
            Constraint(ConstraintType.REQUIRE_MIGRATION_PLAN, severity="warning"),
        ],
        "delete": [
            Constraint(ConstraintType.FLAG_BREAKING_CHANGES),
            Constraint(ConstraintType.DO_NOT_REMOVE_EXPORTS, severity="warning"),
        ],
    }
    
    def encode(
        self,
        constraints: list[Constraint],
        intent: str,
        ownership: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        Encode constraints into structured format.
        
        Returns:
            {
                "rules": [...],
                "forbidden_paths": [...],
                "required_validations": [...],
                "severity_map": {...}
            }
        """
        # Combine default + intent + custom constraints
        all_constraints = list(self.DEFAULT_CONSTRAINTS)
        all_constraints.extend(self.INTENT_CONSTRAINTS.get(intent, []))
        all_constraints.extend(constraints)
        
        # Add ownership constraints if applicable
        if ownership:
            all_constraints.append(
                Constraint(ConstraintType.NO_CROSS_OWNER_EDITS)
            )
        
        # Deduplicate
        seen = set()
        unique = []
        for c in all_constraints:
            if c.constraint_type not in seen:
                seen.add(c.constraint_type)
                unique.append(c)
        
        # Encode
        rules = [c.to_rule() for c in unique]
        severity_map = {c.to_rule(): c.severity for c in unique}
        
        # Extract forbidden paths
        forbidden_paths = self._extract_forbidden_paths(unique, ownership)
        
        # Required validations
        required_validations = self._get_required_validations(unique)
        
        logger.info(
            "constraints_encoded",
            rule_count=len(rules),
            error_rules=sum(1 for s in severity_map.values() if s == "error")
        )
        
        return {
            "rules": rules,
            "forbidden_paths": forbidden_paths,
            "required_validations": required_validations,
            "severity_map": severity_map,
        }
    
    def _extract_forbidden_paths(
        self,
        constraints: list[Constraint],
        ownership: Optional[List]
    ) -> List[str]:
        """Extract paths that are forbidden from modification."""
        forbidden = []
        
        # Cross-owner files
        if ownership and any(
            c.constraint_type == ConstraintType.NO_CROSS_OWNER_EDITS 
            for c in constraints
        ):
            # Would need knowledge graph integration here
            pass
        
        return forbidden
    
    def _get_required_validations(
        self,
        constraints: list[Constraint]
    ) -> List[str]:
        """Get list of required post-generation validations."""
        validations = []
        
        for c in constraints:
            if c.constraint_type == ConstraintType.RETURN_UNIFIED_DIFF_ONLY:
                validations.append("validate_diff_format")
            elif c.constraint_type == ConstraintType.PRESERVE_TYPE_SAFETY:
                validations.append("validate_types")
            elif c.constraint_type == ConstraintType.FLAG_BREAKING_CHANGES:
                validations.append("detect_breaking_changes")
            elif c.constraint_type == ConstraintType.DO_NOT_MODIFY_PUBLIC_API:
                validations.append("validate_public_api_unchanged")
        
        return list(set(validations))
    
    def to_prompt_section(self, encoded: Dict[str, Any]) -> str:
        """Convert encoded constraints to prompt section."""
        lines = ["CONSTRAINTS:"]
        for rule in encoded["rules"]:
            lines.append(f"- {rule}")
        
        if encoded["forbidden_paths"]:
            lines.append("\nFORBIDDEN PATHS:")
            for path in encoded["forbidden_paths"]:
                lines.append(f"- {path}")
        
        return "\n".join(lines)

