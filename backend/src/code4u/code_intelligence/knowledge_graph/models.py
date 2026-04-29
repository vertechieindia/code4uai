"""Data models for the Knowledge Graph."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from enum import Enum
from datetime import datetime


class NodeType(str, Enum):
    """Types of nodes in the Knowledge Graph."""
    # Code entities
    FILE = "file"
    MODULE = "module"
    PACKAGE = "package"
    CLASS = "class"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    TYPE = "type"
    ENUM = "enum"
    
    # Schema entities
    SCHEMA = "schema"
    TABLE = "table"
    COLUMN = "column"
    INDEX = "index"
    
    # API entities
    ENDPOINT = "endpoint"
    ROUTE = "route"
    CONTROLLER = "controller"
    SERVICE = "service"
    
    # Infrastructure
    REPOSITORY = "repository"
    CONFIG = "config"
    SECRET = "secret"
    
    # Organization
    TEAM = "team"
    OWNER = "owner"


class RelationType(str, Enum):
    """Types of relationships between nodes."""
    # Code relationships
    IMPORTS = "imports"
    EXPORTS = "exports"
    CALLS = "calls"
    CALLED_BY = "called_by"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    USES = "uses"
    USED_BY = "used_by"
    DEFINES = "defines"
    DEFINED_IN = "defined_in"
    CONTAINS = "contains"
    CONTAINED_IN = "contained_in"
    REFERENCES = "references"
    REFERENCED_BY = "referenced_by"
    DEPENDS_ON = "depends_on"
    DEPENDENCY_OF = "dependency_of"
    
    # Type relationships
    RETURNS = "returns"
    ACCEPTS = "accepts"
    TYPE_OF = "type_of"
    INSTANCE_OF = "instance_of"
    
    # Schema relationships
    HAS_COLUMN = "has_column"
    FOREIGN_KEY = "foreign_key"
    MIGRATES_TO = "migrates_to"
    
    # Ownership relationships
    OWNED_BY = "owned_by"
    MAINTAINS = "maintains"
    REVIEWS = "reviews"


@dataclass
class GraphNode:
    """A node in the Knowledge Graph."""
    id: str
    type: NodeType
    name: str
    
    # Location
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    
    # Metadata
    language: Optional[str] = None
    visibility: str = "public"  # public, private, protected, internal
    is_exported: bool = False
    is_deprecated: bool = False
    
    # Signature/Schema
    signature: Optional[str] = None
    docstring: Optional[str] = None
    
    # For types
    type_annotation: Optional[str] = None
    
    # Computed
    complexity: int = 0
    dependencies_count: int = 0
    dependents_count: int = 0
    
    # Versioning
    last_modified: Optional[datetime] = None
    last_modifier: Optional[str] = None
    version: str = "1"
    
    # Custom attributes
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, GraphNode):
            return self.id == other.id
        return False


@dataclass
class GraphRelationship:
    """A relationship between two nodes."""
    id: str
    type: RelationType
    source_id: str
    target_id: str
    
    # Metadata
    weight: float = 1.0
    is_direct: bool = True
    
    # For imports/calls
    line_number: Optional[int] = None
    
    # Version tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Custom attributes
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OwnershipInfo:
    """Ownership information for a code entity."""
    node_id: str
    
    # Primary owner
    owner_team: str
    owner_email: Optional[str] = None
    
    # Code owners file reference
    codeowners_path: Optional[str] = None
    codeowners_pattern: Optional[str] = None
    
    # Reviewers
    required_reviewers: List[str] = field(default_factory=list)
    
    # Access
    can_modify: List[str] = field(default_factory=list)
    can_read: List[str] = field(default_factory=list)
    
    # Tags
    sensitivity: str = "normal"  # normal, sensitive, critical
    compliance_tags: List[str] = field(default_factory=list)


@dataclass
class DependencyChain:
    """A chain of dependencies between nodes."""
    source_id: str
    target_id: str
    
    # The path of nodes
    path: List[str] = field(default_factory=list)
    
    # Relationships along the path
    relationships: List[RelationType] = field(default_factory=list)
    
    # Computed
    depth: int = 0
    is_circular: bool = False


@dataclass
class ImpactAnalysis:
    """Analysis of impact for a proposed change."""
    target_node_id: str
    
    # Direct impacts
    directly_impacted: List[str] = field(default_factory=list)
    
    # Transitive impacts
    transitively_impacted: List[str] = field(default_factory=list)
    
    # By type
    impacted_files: List[str] = field(default_factory=list)
    impacted_functions: List[str] = field(default_factory=list)
    impacted_classes: List[str] = field(default_factory=list)
    impacted_schemas: List[str] = field(default_factory=list)
    impacted_endpoints: List[str] = field(default_factory=list)
    
    # Ownership
    impacted_teams: List[str] = field(default_factory=list)
    requires_approval_from: List[str] = field(default_factory=list)
    
    # Risk assessment
    breaking_change: bool = False
    risk_level: str = "low"  # low, medium, high, critical
    risk_factors: List[str] = field(default_factory=list)
    
    # Statistics
    total_nodes_affected: int = 0
    total_files_affected: int = 0
    blast_radius: int = 0
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)


@dataclass
class GraphStats:
    """Statistics about the Knowledge Graph."""
    total_nodes: int = 0
    total_relationships: int = 0
    
    # By type
    nodes_by_type: Dict[str, int] = field(default_factory=dict)
    relationships_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Coverage
    files_indexed: int = 0
    repositories: int = 0
    
    # Health
    orphan_nodes: int = 0
    circular_dependencies: int = 0
    
    # Timing
    last_full_index: Optional[datetime] = None
    last_incremental_update: Optional[datetime] = None

