from __future__ import annotations
"""Type definitions for the Prompt Compiler."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class IntentType(str, Enum):
    """Supported intent types."""
    REFACTOR = "refactor"
    ADD_API = "add_api"
    FIX_BUG = "fix_bug"
    EXPLAIN = "explain"
    RENAME = "rename"
    EXTRACT = "extract"
    DELETE = "delete"
    MIGRATE = "migrate"


@dataclass
class LanguageProfile:
    """Language and framework profile."""
    language: Literal["typescript", "python", "javascript", "go", "rust"]
    frameworks: List[str] = field(default_factory=list)
    style_guide: Optional[str] = None
    type_system: Literal["strict", "gradual", "none"] = "strict"


@dataclass
class OwnershipInfo:
    """Code ownership information."""
    team_id: str
    team_name: str
    patterns: List[str] = field(default_factory=list)
    is_approver: bool = True
    contact: Optional[str] = None


@dataclass
class FileScope:
    """A file in the compilation scope."""
    file_id: str
    path: str
    content: str
    language: str
    symbols: List[str] = field(default_factory=list)
    is_primary: bool = False
    is_readonly: bool = False


@dataclass
class CompiledScope:
    """Reduced scope for LLM consumption."""
    files: list[FileScope]
    primary_file_id: str
    total_tokens_estimate: int
    symbols_in_scope: List[str]
    cross_file_references: dict[str, List[str]]


@dataclass
class ChangePlan:
    """Graph-derived change plan."""
    plan_id: str
    steps: list[Dict[str, Any]]
    affected_node_ids: List[str]
    breaking_change: bool = False
    requires_migration: bool = False


@dataclass 
class GraphNode:
    """Simplified graph node for compiler."""
    node_id: str
    node_type: str
    name: str
    path: Optional[str] = None
    content: Optional[str] = None


@dataclass
class CompilerInput:
    """
    100% deterministic input to the compiler.
    No AI involved in creating this.
    """
    intent: IntentType
    target_node_id: str
    change_plan: ChangePlan
    impacted_nodes: list[GraphNode]
    constraints: list["Constraint"]
    ownership: list[OwnershipInfo]
    language_profile: LanguageProfile
    
    # Optional context
    user_instruction: Optional[str] = None
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None

