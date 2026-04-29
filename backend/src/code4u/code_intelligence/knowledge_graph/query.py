"""Query builder for the Knowledge Graph."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set, Callable
from enum import Enum

from .models import NodeType, RelationType, GraphNode, GraphRelationship
from .graph import KnowledgeGraph


class QueryOperator(str, Enum):
    """Operators for query conditions."""
    EQUALS = "eq"
    NOT_EQUALS = "neq"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"
    MATCHES = "matches"  # Regex


@dataclass
class QueryCondition:
    """A condition in a graph query."""
    field: str
    operator: QueryOperator
    value: Any


@dataclass
class GraphQuery:
    """A query against the Knowledge Graph."""
    # Node filters
    node_types: List[NodeType] = field(default_factory=list)
    conditions: List[QueryCondition] = field(default_factory=list)
    
    # Relationship traversal
    traverse_outgoing: List[RelationType] = field(default_factory=list)
    traverse_incoming: List[RelationType] = field(default_factory=list)
    max_depth: int = 1
    
    # Result options
    limit: int = 100
    offset: int = 0
    order_by: Optional[str] = None
    order_desc: bool = False
    
    # Include options
    include_relationships: bool = False
    include_ownership: bool = False


@dataclass
class QueryResult:
    """Result of a graph query."""
    nodes: List[GraphNode] = field(default_factory=list)
    relationships: List[GraphRelationship] = field(default_factory=list)
    total_count: int = 0
    has_more: bool = False


class QueryBuilder:
    """
    Fluent API for building Knowledge Graph queries.
    
    Example:
        results = (QueryBuilder(graph)
            .nodes_of_type(NodeType.FUNCTION)
            .where("name", QueryOperator.STARTS_WITH, "get")
            .in_file("users.py")
            .traverse_outgoing(RelationType.CALLS)
            .limit(10)
            .execute())
    """
    
    def __init__(self, graph: KnowledgeGraph):
        """Initialize query builder.
        
        Args:
            graph: KnowledgeGraph to query
        """
        self.graph = graph
        self._query = GraphQuery()
    
    def nodes_of_type(self, *types: NodeType) -> QueryBuilder:
        """Filter by node type.
        
        Args:
            types: Node types to include
            
        Returns:
            Self for chaining
        """
        self._query.node_types.extend(types)
        return self
    
    def where(
        self, 
        field: str, 
        operator: QueryOperator, 
        value: Any
    ) -> QueryBuilder:
        """Add a condition.
        
        Args:
            field: Field to filter on
            operator: Comparison operator
            value: Value to compare
            
        Returns:
            Self for chaining
        """
        self._query.conditions.append(QueryCondition(field, operator, value))
        return self
    
    def equals(self, field: str, value: Any) -> QueryBuilder:
        """Shorthand for equality condition."""
        return self.where(field, QueryOperator.EQUALS, value)
    
    def contains(self, field: str, value: str) -> QueryBuilder:
        """Shorthand for contains condition."""
        return self.where(field, QueryOperator.CONTAINS, value)
    
    def in_file(self, file_path: str) -> QueryBuilder:
        """Filter to nodes in a specific file."""
        return self.equals("file_path", file_path)
    
    def named(self, name: str) -> QueryBuilder:
        """Filter by exact name."""
        return self.equals("name", name)
    
    def name_starts_with(self, prefix: str) -> QueryBuilder:
        """Filter by name prefix."""
        return self.where("name", QueryOperator.STARTS_WITH, prefix)
    
    def is_exported(self) -> QueryBuilder:
        """Filter to exported symbols."""
        return self.equals("is_exported", True)
    
    def traverse_outgoing(self, *rel_types: RelationType) -> QueryBuilder:
        """Traverse outgoing relationships.
        
        Args:
            rel_types: Relationship types to follow
            
        Returns:
            Self for chaining
        """
        self._query.traverse_outgoing.extend(rel_types)
        return self
    
    def traverse_incoming(self, *rel_types: RelationType) -> QueryBuilder:
        """Traverse incoming relationships.
        
        Args:
            rel_types: Relationship types to follow
            
        Returns:
            Self for chaining
        """
        self._query.traverse_incoming.extend(rel_types)
        return self
    
    def with_depth(self, depth: int) -> QueryBuilder:
        """Set max traversal depth."""
        self._query.max_depth = depth
        return self
    
    def limit(self, count: int) -> QueryBuilder:
        """Limit number of results."""
        self._query.limit = count
        return self
    
    def offset(self, count: int) -> QueryBuilder:
        """Skip results."""
        self._query.offset = count
        return self
    
    def order_by(self, field: str, desc: bool = False) -> QueryBuilder:
        """Order results."""
        self._query.order_by = field
        self._query.order_desc = desc
        return self
    
    def include_relationships(self) -> QueryBuilder:
        """Include relationships in results."""
        self._query.include_relationships = True
        return self
    
    def include_ownership(self) -> QueryBuilder:
        """Include ownership info."""
        self._query.include_ownership = True
        return self
    
    def execute(self) -> QueryResult:
        """Execute the query.
        
        Returns:
            QueryResult with matching nodes
        """
        # Start with all nodes or filtered by type
        if self._query.node_types:
            candidates: Set[str] = set()
            for node_type in self._query.node_types:
                nodes = self.graph.find_nodes(node_type=node_type)
                candidates.update(n.id for n in nodes)
        else:
            candidates = set(self.graph._nodes.keys())
        
        # Apply conditions
        matching_nodes: List[GraphNode] = []
        for node_id in candidates:
            node = self.graph.get_node(node_id)
            if node and self._matches_conditions(node):
                matching_nodes.append(node)
        
        # Traverse relationships if specified
        if self._query.traverse_outgoing or self._query.traverse_incoming:
            traversed = self._traverse(matching_nodes)
            matching_nodes.extend(traversed)
            # Remove duplicates
            seen = set()
            unique_nodes = []
            for node in matching_nodes:
                if node.id not in seen:
                    seen.add(node.id)
                    unique_nodes.append(node)
            matching_nodes = unique_nodes
        
        # Sort
        if self._query.order_by:
            matching_nodes.sort(
                key=lambda n: getattr(n, self._query.order_by, ""),
                reverse=self._query.order_desc,
            )
        
        # Count before pagination
        total_count = len(matching_nodes)
        
        # Paginate
        start = self._query.offset
        end = start + self._query.limit
        matching_nodes = matching_nodes[start:end]
        
        # Get relationships if requested
        relationships = []
        if self._query.include_relationships:
            node_ids = {n.id for n in matching_nodes}
            for node in matching_nodes:
                for rel in self.graph.get_outgoing(node.id):
                    if rel.target_id in node_ids:
                        relationships.append(rel)
        
        return QueryResult(
            nodes=matching_nodes,
            relationships=relationships,
            total_count=total_count,
            has_more=end < total_count,
        )
    
    def _matches_conditions(self, node: GraphNode) -> bool:
        """Check if a node matches all conditions."""
        for condition in self._query.conditions:
            value = getattr(node, condition.field, None)
            if value is None and condition.field in node.attributes:
                value = node.attributes[condition.field]
            
            if not self._check_condition(value, condition):
                return False
        
        return True
    
    def _check_condition(self, value: Any, condition: QueryCondition) -> bool:
        """Check a single condition."""
        target = condition.value
        op = condition.operator
        
        if value is None:
            return op == QueryOperator.NOT_EQUALS
        
        if op == QueryOperator.EQUALS:
            return value == target
        elif op == QueryOperator.NOT_EQUALS:
            return value != target
        elif op == QueryOperator.CONTAINS:
            return target in str(value)
        elif op == QueryOperator.STARTS_WITH:
            return str(value).startswith(target)
        elif op == QueryOperator.ENDS_WITH:
            return str(value).endswith(target)
        elif op == QueryOperator.IN:
            return value in target
        elif op == QueryOperator.NOT_IN:
            return value not in target
        elif op == QueryOperator.GREATER_THAN:
            return value > target
        elif op == QueryOperator.LESS_THAN:
            return value < target
        elif op == QueryOperator.GREATER_EQUAL:
            return value >= target
        elif op == QueryOperator.LESS_EQUAL:
            return value <= target
        elif op == QueryOperator.MATCHES:
            import re
            return bool(re.match(target, str(value)))
        
        return False
    
    def _traverse(self, start_nodes: List[GraphNode]) -> List[GraphNode]:
        """Traverse from start nodes following relationships."""
        visited: Set[str] = set()
        result: List[GraphNode] = []
        queue: List[Tuple[str, int]] = [(n.id, 0) for n in start_nodes]
        
        while queue:
            node_id, depth = queue.pop(0)
            
            if node_id in visited or depth >= self._query.max_depth:
                continue
            visited.add(node_id)
            
            node = self.graph.get_node(node_id)
            if not node:
                continue
            
            if depth > 0:  # Don't include start nodes again
                result.append(node)
            
            # Follow outgoing
            for rel_type in self._query.traverse_outgoing:
                for rel in self.graph.get_outgoing(node_id, rel_type):
                    if rel.target_id not in visited:
                        queue.append((rel.target_id, depth + 1))
            
            # Follow incoming
            for rel_type in self._query.traverse_incoming:
                for rel in self.graph.get_incoming(node_id, rel_type):
                    if rel.source_id not in visited:
                        queue.append((rel.source_id, depth + 1))
        
        return result
    
    # ============= Convenience Methods =============
    
    def find_callers_of(self, function_name: str) -> QueryResult:
        """Find all functions that call a given function."""
        return (QueryBuilder(self.graph)
            .nodes_of_type(NodeType.FUNCTION, NodeType.METHOD)
            .named(function_name)
            .traverse_incoming(RelationType.CALLS)
            .execute())
    
    def find_callees_of(self, function_name: str) -> QueryResult:
        """Find all functions called by a given function."""
        return (QueryBuilder(self.graph)
            .nodes_of_type(NodeType.FUNCTION, NodeType.METHOD)
            .named(function_name)
            .traverse_outgoing(RelationType.CALLS)
            .execute())
    
    def find_dependencies_of(self, file_path: str) -> QueryResult:
        """Find all files that a file depends on."""
        return (QueryBuilder(self.graph)
            .nodes_of_type(NodeType.FILE)
            .in_file(file_path)
            .traverse_outgoing(RelationType.IMPORTS)
            .execute())
    
    def find_dependents_of(self, file_path: str) -> QueryResult:
        """Find all files that depend on a file."""
        return (QueryBuilder(self.graph)
            .nodes_of_type(NodeType.FILE)
            .in_file(file_path)
            .traverse_incoming(RelationType.IMPORTS)
            .execute())

