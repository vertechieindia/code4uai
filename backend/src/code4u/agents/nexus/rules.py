"""Architectural Rule Engine — YAML-based fitness functions.

Defines ``ArchitecturalRule`` — a declarative constraint on codebase
structure enforced by the Drift Sentinel.  Rules can target:

  - **forbidden_imports**: modules/packages that must not be imported
    from files matching a given glob (e.g. "no SQLAlchemy in UI layer").
  - **required_decorators**: decorators that must be present on
    functions/classes matching a pattern (e.g. "@login_required on routes").
  - **naming_conventions**: regex patterns that symbol names must follow
    in files matching a selector (e.g. "async functions start with get_").
  - **layer_boundaries**: directed allowed-dependency rules between
    architectural layers (e.g. "controllers may import services but
    not repositories directly").

Rules are loaded from YAML files in ``~/.code4u/rules/`` (global)
and ``<workspace>/.code4u/rules/`` (project-local, overriding global).

Usage::

    registry = RuleRegistry()
    registry.load("/path/to/workspace")
    for rule in registry.all():
        print(rule.id, rule.severity)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("arch_rules")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class LayerBoundary:
    """Directed dependency between architectural layers."""
    source_layer: str
    allowed_targets: List[str] = field(default_factory=list)
    forbidden_targets: List[str] = field(default_factory=list)
    source_glob: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sourceLayer": self.source_layer,
            "allowedTargets": self.allowed_targets,
            "forbiddenTargets": self.forbidden_targets,
            "sourceGlob": self.source_glob,
            "description": self.description,
        }


@dataclass
class ForbiddenImport:
    """An import pattern that is not allowed in certain files."""
    module_pattern: str
    file_glob: str = "*"
    reason: str = ""

    def matches_module(self, module_name: str) -> bool:
        return bool(re.search(self.module_pattern, module_name))

    def matches_file(self, file_path: str) -> bool:
        from fnmatch import fnmatch
        return fnmatch(Path(file_path).name, self.file_glob) or fnmatch(file_path, self.file_glob)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modulePattern": self.module_pattern,
            "fileGlob": self.file_glob,
            "reason": self.reason,
        }


@dataclass
class RequiredDecorator:
    """A decorator that must be present on matching symbols."""
    decorator_name: str
    symbol_pattern: str = ".*"
    file_glob: str = "*"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decoratorName": self.decorator_name,
            "symbolPattern": self.symbol_pattern,
            "fileGlob": self.file_glob,
            "reason": self.reason,
        }


@dataclass
class NamingConvention:
    """A naming pattern that symbols must follow."""
    pattern: str
    symbol_type: str = "function"  # "function", "class", "variable"
    file_glob: str = "*"
    reason: str = ""

    def matches(self, name: str) -> bool:
        return bool(re.match(self.pattern, name))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern,
            "symbolType": self.symbol_type,
            "fileGlob": self.file_glob,
            "reason": self.reason,
        }


@dataclass
class ArchitecturalRule:
    """A single architectural fitness function.

    Loaded from YAML with the following structure::

        id: no-db-in-ui
        name: No Database in UI Layer
        description: UI components must not import DB models directly.
        severity: error
        enabled: true
        forbidden_imports:
          - module_pattern: "sqlalchemy|prisma|models\\.db"
            file_glob: "*.tsx"
            reason: "Use the Service layer for data access."
        layer_boundaries:
          - source_layer: controllers
            forbidden_targets: [repositories]
        naming_conventions:
          - pattern: "^[a-z_][a-z0-9_]*$"
            symbol_type: function
            file_glob: "*.py"
    """
    id: str
    name: str
    description: str = ""
    severity: str = "warning"  # "info", "warning", "error", "critical"
    enabled: bool = True
    forbidden_imports: List[ForbiddenImport] = field(default_factory=list)
    required_decorators: List[RequiredDecorator] = field(default_factory=list)
    naming_conventions: List[NamingConvention] = field(default_factory=list)
    layer_boundaries: List[LayerBoundary] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArchitecturalRule:
        """Create a rule from a parsed YAML/dict."""
        forbidden = [
            ForbiddenImport(
                module_pattern=fi.get("module_pattern", ""),
                file_glob=fi.get("file_glob", "*"),
                reason=fi.get("reason", ""),
            )
            for fi in data.get("forbidden_imports", [])
        ]

        decorators = [
            RequiredDecorator(
                decorator_name=rd.get("decorator_name", ""),
                symbol_pattern=rd.get("symbol_pattern", ".*"),
                file_glob=rd.get("file_glob", "*"),
                reason=rd.get("reason", ""),
            )
            for rd in data.get("required_decorators", [])
        ]

        naming = [
            NamingConvention(
                pattern=nc.get("pattern", ""),
                symbol_type=nc.get("symbol_type", "function"),
                file_glob=nc.get("file_glob", "*"),
                reason=nc.get("reason", ""),
            )
            for nc in data.get("naming_conventions", [])
        ]

        boundaries = [
            LayerBoundary(
                source_layer=lb.get("source_layer", ""),
                allowed_targets=lb.get("allowed_targets", []),
                forbidden_targets=lb.get("forbidden_targets", []),
                source_glob=lb.get("source_glob", ""),
                description=lb.get("description", ""),
            )
            for lb in data.get("layer_boundaries", [])
        ]

        return cls(
            id=data.get("id", "unknown"),
            name=data.get("name", "Unnamed Rule"),
            description=data.get("description", ""),
            severity=data.get("severity", "warning"),
            enabled=data.get("enabled", True),
            forbidden_imports=forbidden,
            required_decorators=decorators,
            naming_conventions=naming,
            layer_boundaries=boundaries,
            tags=data.get("tags", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "enabled": self.enabled,
            "forbiddenImports": [fi.to_dict() for fi in self.forbidden_imports],
            "requiredDecorators": [rd.to_dict() for rd in self.required_decorators],
            "namingConventions": [nc.to_dict() for nc in self.naming_conventions],
            "layerBoundaries": [lb.to_dict() for lb in self.layer_boundaries],
            "tags": self.tags,
        }

    def to_prompt_context(self) -> str:
        """Render this rule as prompt context for LLM agents."""
        lines = [f"RULE [{self.severity.upper()}]: {self.name}"]
        if self.description:
            lines.append(f"  {self.description}")
        for fi in self.forbidden_imports:
            lines.append(f"  - FORBIDDEN import: {fi.module_pattern} in {fi.file_glob}")
            if fi.reason:
                lines.append(f"    Reason: {fi.reason}")
        for nc in self.naming_conventions:
            lines.append(f"  - NAMING: {nc.symbol_type} must match {nc.pattern} in {nc.file_glob}")
        for lb in self.layer_boundaries:
            if lb.forbidden_targets:
                lines.append(f"  - BOUNDARY: {lb.source_layer} must NOT import from {', '.join(lb.forbidden_targets)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Violation
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    """A detected architectural rule violation."""
    rule_id: str
    rule_name: str
    severity: str
    file_path: str
    line: int = 0
    message: str = ""
    symbol_name: str = ""
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "ruleName": self.rule_name,
            "severity": self.severity,
            "filePath": self.file_path,
            "line": self.line,
            "message": self.message,
            "symbolName": self.symbol_name,
            "suggestion": self.suggestion,
        }


# ---------------------------------------------------------------------------
# RuleRegistry
# ---------------------------------------------------------------------------

class RuleRegistry:
    """Discovers and manages architectural rules from YAML files."""

    GLOBAL_DIR = Path.home() / ".code4u" / "rules"
    LOCAL_DIR_NAME = ".code4u/rules"

    def __init__(self) -> None:
        self._rules: Dict[str, ArchitecturalRule] = {}
        self._loaded = False

    def load(self, workspace_path: str = "") -> None:
        """Load rules from global and project-local directories."""
        self._rules.clear()

        if self.GLOBAL_DIR.is_dir():
            self._load_dir(self.GLOBAL_DIR)

        if workspace_path:
            local_dir = Path(workspace_path) / self.LOCAL_DIR_NAME
            if local_dir.is_dir():
                self._load_dir(local_dir)

        self._loaded = True
        logger.info("rules_loaded", count=len(self._rules))

    def register(self, rule: ArchitecturalRule) -> None:
        """Manually register a rule."""
        self._rules[rule.id] = rule
        self._loaded = True

    def get(self, rule_id: str) -> Optional[ArchitecturalRule]:
        return self._rules.get(rule_id)

    def all(self) -> List[ArchitecturalRule]:
        """Return all enabled rules."""
        return [r for r in self._rules.values() if r.enabled]

    def all_rules(self) -> List[ArchitecturalRule]:
        """Return all rules (including disabled)."""
        return list(self._rules.values())

    @property
    def count(self) -> int:
        return len(self._rules)

    def rules_for_file(self, file_path: str) -> List[ArchitecturalRule]:
        """Return rules applicable to a specific file."""
        from fnmatch import fnmatch
        result = []
        fname = Path(file_path).name
        for rule in self.all():
            applicable = False
            for fi in rule.forbidden_imports:
                if fnmatch(fname, fi.file_glob) or fnmatch(file_path, fi.file_glob):
                    applicable = True
                    break
            for nc in rule.naming_conventions:
                if fnmatch(fname, nc.file_glob) or fnmatch(file_path, nc.file_glob):
                    applicable = True
                    break
            for rd in rule.required_decorators:
                if fnmatch(fname, rd.file_glob) or fnmatch(file_path, rd.file_glob):
                    applicable = True
                    break
            if applicable:
                result.append(rule)
        return result

    def to_prompt_context(self, file_path: str = "") -> str:
        """Render all applicable rules as prompt context."""
        rules = self.rules_for_file(file_path) if file_path else self.all()
        if not rules:
            return ""
        sections = ["<architectural_rules>"]
        for r in rules:
            sections.append(r.to_prompt_context())
        sections.append("</architectural_rules>")
        return "\n".join(sections)

    # -- Internal ------------------------------------------------------------

    def _load_dir(self, directory: Path) -> None:
        """Load all YAML files in a directory."""
        try:
            import yaml
        except ImportError:
            self._load_dir_fallback(directory)
            return

        for yaml_file in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    rule = ArchitecturalRule.from_dict(data)
                    self._rules[rule.id] = rule
            except Exception as exc:
                logger.warning("rule_load_error", file=str(yaml_file), error=str(exc))

    def _load_dir_fallback(self, directory: Path) -> None:
        """Fallback loader when PyYAML is not installed."""
        pass
