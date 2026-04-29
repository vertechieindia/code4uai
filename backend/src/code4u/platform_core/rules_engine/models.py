"""Data models for Rules & Workflows Engine."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from enum import Enum
from datetime import datetime


class RuleType(str, Enum):
    """Types of rules."""
    INSTRUCTION = "instruction"      # General instruction
    STYLE = "style"                  # Code style preference
    CONSTRAINT = "constraint"        # Hard constraint
    TEMPLATE = "template"            # Code template
    CONTEXT = "context"              # Context information
    FORBIDDEN = "forbidden"          # Things to avoid


class RuleScope(str, Enum):
    """Scope of rule application."""
    GLOBAL = "global"                # Apply everywhere
    DIRECTORY = "directory"          # Apply to directory
    FILE_PATTERN = "file_pattern"    # Apply to matching files
    LANGUAGE = "language"            # Apply to language
    PROJECT = "project"              # Apply to project
    TEAM = "team"                    # Team-wide rules


@dataclass
class Rule:
    """A rule that modifies model behavior."""
    id: str
    name: str
    type: RuleType
    
    # Rule content
    instruction: str
    
    # Scope
    scope: RuleScope = RuleScope.GLOBAL
    globs: List[str] = field(default_factory=list)  # File patterns
    languages: List[str] = field(default_factory=list)
    directories: List[str] = field(default_factory=list)
    
    # Priority (higher = more important)
    priority: int = 0
    
    # Metadata
    description: Optional[str] = None
    author: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Conditions
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    # Status
    enabled: bool = True
    
    def matches(
        self,
        file_path: Optional[str] = None,
        language: Optional[str] = None,
        directory: Optional[str] = None,
    ) -> bool:
        """Check if rule applies to given context."""
        if not self.enabled:
            return False
        
        if self.scope == RuleScope.GLOBAL:
            return True
        
        if self.scope == RuleScope.LANGUAGE:
            if language and self.languages:
                return language in self.languages
        
        if self.scope == RuleScope.FILE_PATTERN:
            if file_path and self.globs:
                import fnmatch
                return any(fnmatch.fnmatch(file_path, g) for g in self.globs)
        
        if self.scope == RuleScope.DIRECTORY:
            if directory and self.directories:
                return any(directory.startswith(d) for d in self.directories)
        
        return False


@dataclass
class WorkflowStep:
    """A step in a workflow."""
    id: str
    name: str
    
    # Action
    action: str  # prompt, refactor, validate, wait_for_approval
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Prompt content (if action is prompt)
    prompt: Optional[str] = None
    
    # Conditions
    condition: Optional[str] = None
    
    # Error handling
    on_error: str = "fail"  # fail, continue, retry
    max_retries: int = 3
    
    # Output
    output_variable: Optional[str] = None


@dataclass
class Workflow:
    """A reusable workflow (like Cursor custom commands)."""
    id: str
    name: str
    
    # Trigger
    command: str  # e.g., "code-review", "pr", "fix-tests"
    description: str = ""
    
    # Steps
    steps: List[WorkflowStep] = field(default_factory=list)
    
    # Scope
    scope: RuleScope = RuleScope.GLOBAL
    globs: List[str] = field(default_factory=list)
    
    # Variables
    input_variables: List[str] = field(default_factory=list)
    default_values: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    author: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    
    # Status
    enabled: bool = True


@dataclass
class Memory:
    """A memory (learned preference or context)."""
    id: str
    
    # Content
    content: str
    
    # Type
    type: str = "preference"  # preference, fact, instruction
    
    # Source
    source: str = "user"  # user, inferred, imported
    
    # Confidence
    confidence: float = 1.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    use_count: int = 0
    
    # Scope
    scope: RuleScope = RuleScope.GLOBAL
    
    # Status
    enabled: bool = True


@dataclass
class RuleFile:
    """A .mdc rule file (like Cursor)."""
    path: str
    
    # Frontmatter
    description: Optional[str] = None
    globs: List[str] = field(default_factory=list)
    
    # Content
    content: str = ""
    
    # Parsed rules
    rules: List[Rule] = field(default_factory=list)
    
    # Metadata
    last_modified: Optional[datetime] = None


@dataclass
class RulesContext:
    """Context for rule evaluation."""
    file_path: Optional[str] = None
    language: Optional[str] = None
    directory: Optional[str] = None
    project: Optional[str] = None
    team: Optional[str] = None
    
    # Additional context
    intent: Optional[str] = None
    selection: Optional[str] = None
    
    # Variables
    variables: Dict[str, Any] = field(default_factory=dict)

