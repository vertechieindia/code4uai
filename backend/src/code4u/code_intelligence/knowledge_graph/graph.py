"""Core Knowledge Graph implementation."""

from __future__ import annotations
import threading
from typing import Optional, List, Dict, Set, Any, Iterator
from collections import defaultdict
import uuid

from .models import (
    NodeType,
    RelationType,
    GraphNode,
    GraphRelationship,
    ImpactAnalysis,
    OwnershipInfo,
    DependencyChain,
    GraphStats,
)


class KnowledgeGraph:
    """
    The core Knowledge Graph for code4u.ai.
    
    This is the MOST IMPORTANT system after the state machine.
    It provides:
    - Complete understanding of codebase structure
    - Dependency tracking
    - Impact analysis
    - Ownership boundaries
    
    The LLM never guesses. It KNOWS because of this graph.
    """
    
    def __init__(self, tenant_id: str = "default"):
        """Initialize a Knowledge Graph for a tenant.
        
        Args:
            tenant_id: Tenant identifier for isolation
        """
        self.tenant_id = tenant_id
        
        # Primary storage
        self._nodes: Dict[str, GraphNode] = {}
        self._relationships: Dict[str, GraphRelationship] = {}
        
        # Indexes for fast lookup
        self._nodes_by_type: Dict[NodeType, Set[str]] = defaultdict(set)
        self._nodes_by_file: Dict[str, Set[str]] = defaultdict(set)
        self._nodes_by_name: Dict[str, Set[str]] = defaultdict(set)
        
        # Relationship indexes
        self._outgoing: Dict[str, Set[str]] = defaultdict(set)  # node_id -> rel_ids
        self._incoming: Dict[str, Set[str]] = defaultdict(set)  # node_id -> rel_ids
        self._relationships_by_type: Dict[RelationType, Set[str]] = defaultdict(set)
        
        # Ownership
        self._ownership: Dict[str, OwnershipInfo] = {}
        
        # Thread safety
        self._lock = threading.RLock()
    
    # ============= Node Operations =============
    
    def add_node(self, node: GraphNode) -> str:
        """Add a node to the graph.
        
        Args:
            node: The node to add
            
        Returns:
            Node ID
        """
        with self._lock:
            if not node.id:
                node.id = str(uuid.uuid4())
            
            self._nodes[node.id] = node
            
            # Update indexes
            self._nodes_by_type[node.type].add(node.id)
            self._nodes_by_name[node.name].add(node.id)
            if node.file_path:
                self._nodes_by_file[node.file_path].add(node.id)
            
            return node.id
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID.
        
        Args:
            node_id: Node identifier
            
        Returns:
            GraphNode or None
        """
        return self._nodes.get(node_id)
    
    def update_node(self, node: GraphNode) -> bool:
        """Update an existing node.
        
        Args:
            node: Node with updated data
            
        Returns:
            True if updated, False if not found
        """
        with self._lock:
            if node.id not in self._nodes:
                return False
            
            old_node = self._nodes[node.id]
            
            # Update indexes if needed
            if old_node.type != node.type:
                self._nodes_by_type[old_node.type].discard(node.id)
                self._nodes_by_type[node.type].add(node.id)
            
            if old_node.name != node.name:
                self._nodes_by_name[old_node.name].discard(node.id)
                self._nodes_by_name[node.name].add(node.id)
            
            if old_node.file_path != node.file_path:
                if old_node.file_path:
                    self._nodes_by_file[old_node.file_path].discard(node.id)
                if node.file_path:
                    self._nodes_by_file[node.file_path].add(node.id)
            
            self._nodes[node.id] = node
            return True
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node and its relationships.
        
        Args:
            node_id: Node to remove
            
        Returns:
            True if removed
        """
        with self._lock:
            if node_id not in self._nodes:
                return False
            
            node = self._nodes[node_id]
            
            # Remove relationships
            for rel_id in list(self._outgoing.get(node_id, [])):
                self._remove_relationship_internal(rel_id)
            for rel_id in list(self._incoming.get(node_id, [])):
                self._remove_relationship_internal(rel_id)
            
            # Remove from indexes
            self._nodes_by_type[node.type].discard(node_id)
            self._nodes_by_name[node.name].discard(node_id)
            if node.file_path:
                self._nodes_by_file[node.file_path].discard(node_id)
            
            # Remove ownership
            if node_id in self._ownership:
                del self._ownership[node_id]
            
            del self._nodes[node_id]
            return True
    
    def find_nodes(
        self,
        node_type: Optional[NodeType] = None,
        name: Optional[str] = None,
        file_path: Optional[str] = None,
        name_pattern: Optional[str] = None,
    ) -> List[GraphNode]:
        """Find nodes matching criteria.
        
        Args:
            node_type: Filter by type
            name: Exact name match
            file_path: Filter by file
            name_pattern: Regex pattern for name
            
        Returns:
            List of matching nodes
        """
        candidates: Set[str] = set()
        
        if file_path:
            candidates = self._nodes_by_file.get(file_path, set()).copy()
        elif name:
            candidates = self._nodes_by_name.get(name, set()).copy()
        elif node_type:
            candidates = self._nodes_by_type.get(node_type, set()).copy()
        else:
            candidates = set(self._nodes.keys())
        
        results = []
        for node_id in candidates:
            node = self._nodes.get(node_id)
            if not node:
                continue
            
            if node_type and node.type != node_type:
                continue
            if name and node.name != name:
                continue
            if file_path and node.file_path != file_path:
                continue
            if name_pattern:
                import re
                if not re.match(name_pattern, node.name):
                    continue
            
            results.append(node)
        
        return results
    
    # ============= Relationship Operations =============
    
    def add_relationship(self, relationship: GraphRelationship) -> str:
        """Add a relationship between nodes.
        
        Args:
            relationship: The relationship to add
            
        Returns:
            Relationship ID
        """
        with self._lock:
            if not relationship.id:
                relationship.id = str(uuid.uuid4())
            
            # Validate nodes exist
            if relationship.source_id not in self._nodes:
                raise ValueError(f"Source node not found: {relationship.source_id}")
            if relationship.target_id not in self._nodes:
                raise ValueError(f"Target node not found: {relationship.target_id}")
            
            self._relationships[relationship.id] = relationship
            
            # Update indexes
            self._outgoing[relationship.source_id].add(relationship.id)
            self._incoming[relationship.target_id].add(relationship.id)
            self._relationships_by_type[relationship.type].add(relationship.id)
            
            # Update node counts
            self._nodes[relationship.source_id].dependencies_count += 1
            self._nodes[relationship.target_id].dependents_count += 1
            
            return relationship.id
    
    def get_relationship(self, rel_id: str) -> Optional[GraphRelationship]:
        """Get a relationship by ID."""
        return self._relationships.get(rel_id)
    
    def _remove_relationship_internal(self, rel_id: str) -> None:
        """Internal method to remove a relationship."""
        if rel_id not in self._relationships:
            return
        
        rel = self._relationships[rel_id]
        
        self._outgoing[rel.source_id].discard(rel_id)
        self._incoming[rel.target_id].discard(rel_id)
        self._relationships_by_type[rel.type].discard(rel_id)
        
        # Update counts
        if rel.source_id in self._nodes:
            self._nodes[rel.source_id].dependencies_count -= 1
        if rel.target_id in self._nodes:
            self._nodes[rel.target_id].dependents_count -= 1
        
        del self._relationships[rel_id]
    
    def remove_relationship(self, rel_id: str) -> bool:
        """Remove a relationship."""
        with self._lock:
            if rel_id not in self._relationships:
                return False
            self._remove_relationship_internal(rel_id)
            return True
    
    def get_outgoing(
        self, 
        node_id: str, 
        rel_type: Optional[RelationType] = None
    ) -> List[GraphRelationship]:
        """Get outgoing relationships from a node."""
        rel_ids = self._outgoing.get(node_id, set())
        results = []
        
        for rel_id in rel_ids:
            rel = self._relationships.get(rel_id)
            if rel and (rel_type is None or rel.type == rel_type):
                results.append(rel)
        
        return results
    
    def get_incoming(
        self, 
        node_id: str, 
        rel_type: Optional[RelationType] = None
    ) -> List[GraphRelationship]:
        """Get incoming relationships to a node."""
        rel_ids = self._incoming.get(node_id, set())
        results = []
        
        for rel_id in rel_ids:
            rel = self._relationships.get(rel_id)
            if rel and (rel_type is None or rel.type == rel_type):
                results.append(rel)
        
        return results
    
    # ============= Analysis Operations =============
    
    def analyze_impact(
        self,
        node_id: str,
        max_depth: int = 10,
    ) -> ImpactAnalysis:
        """Analyze the impact of changing a node.
        
        Args:
            node_id: Node to analyze
            max_depth: Maximum traversal depth
            
        Returns:
            ImpactAnalysis with all affected entities
        """
        node = self.get_node(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")
        
        analysis = ImpactAnalysis(target_node_id=node_id)
        
        # BFS to find all impacted nodes
        visited: Set[str] = set()
        queue: List[Tuple[str, int]] = [(node_id, 0)]
        
        while queue:
            current_id, depth = queue.pop(0)
            
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            
            current = self.get_node(current_id)
            if not current:
                continue
            
            # Categorize by depth
            if depth == 1:
                analysis.directly_impacted.append(current_id)
            elif depth > 1:
                analysis.transitively_impacted.append(current_id)
            
            # Categorize by type
            if current.type == NodeType.FILE and current.file_path:
                analysis.impacted_files.append(current.file_path)
            elif current.type in [NodeType.FUNCTION, NodeType.METHOD]:
                analysis.impacted_functions.append(current.name)
            elif current.type == NodeType.CLASS:
                analysis.impacted_classes.append(current.name)
            elif current.type == NodeType.SCHEMA:
                analysis.impacted_schemas.append(current.name)
            elif current.type == NodeType.ENDPOINT:
                analysis.impacted_endpoints.append(current.name)
            
            # Get ownership
            ownership = self.get_ownership(current_id)
            if ownership and ownership.owner_team not in analysis.impacted_teams:
                analysis.impacted_teams.append(ownership.owner_team)
            
            # Add dependents to queue
            for rel in self.get_incoming(current_id):
                if rel.type in [
                    RelationType.DEPENDS_ON,
                    RelationType.USES,
                    RelationType.CALLS,
                    RelationType.IMPORTS,
                    RelationType.REFERENCES,
                ]:
                    queue.append((rel.source_id, depth + 1))
        
        # Calculate stats
        analysis.total_nodes_affected = len(visited) - 1  # Exclude source
        analysis.total_files_affected = len(set(analysis.impacted_files))
        analysis.blast_radius = analysis.total_nodes_affected
        
        # Determine risk
        analysis.risk_level = self._calculate_risk_level(analysis)
        analysis.breaking_change = self._is_breaking_change(node, analysis)
        
        # Add recommendations
        analysis.recommendations = self._generate_recommendations(analysis)
        
        # Determine required approvals
        analysis.requires_approval_from = list(set(analysis.impacted_teams))
        
        return analysis
    
    def _calculate_risk_level(self, analysis: ImpactAnalysis) -> str:
        """Calculate risk level for an impact analysis."""
        if analysis.total_nodes_affected > 100:
            return "critical"
        elif analysis.total_nodes_affected > 50:
            return "high"
        elif analysis.total_nodes_affected > 20:
            return "medium"
        return "low"
    
    def _is_breaking_change(
        self, 
        node: GraphNode, 
        analysis: ImpactAnalysis
    ) -> bool:
        """Determine if a change is breaking."""
        # Public API changes are breaking
        if node.is_exported and node.type in [
            NodeType.FUNCTION, 
            NodeType.CLASS, 
            NodeType.INTERFACE,
        ]:
            return True
        
        # Schema changes are breaking
        if node.type == NodeType.SCHEMA:
            return True
        
        # Changes affecting multiple teams are breaking
        if len(analysis.impacted_teams) > 2:
            return True
        
        return False
    
    def _generate_recommendations(self, analysis: ImpactAnalysis) -> List[str]:
        """Generate recommendations based on impact."""
        recs = []
        
        if analysis.risk_level in ["high", "critical"]:
            recs.append("Consider phased rollout")
            recs.append("Add feature flag for gradual enablement")
        
        if len(analysis.impacted_teams) > 1:
            recs.append(f"Coordinate with teams: {', '.join(analysis.impacted_teams)}")
        
        if analysis.impacted_schemas:
            recs.append("Schema migration required - prepare rollback plan")
        
        if analysis.impacted_endpoints:
            recs.append("API versioning may be needed")
        
        return recs
    
    def find_dependency_chain(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 10,
    ) -> Optional[DependencyChain]:
        """Find the dependency chain between two nodes.
        
        Args:
            source_id: Starting node
            target_id: Target node
            max_depth: Maximum search depth
            
        Returns:
            DependencyChain if path exists, None otherwise
        """
        # BFS to find shortest path
        visited: Set[str] = set()
        queue: List[Tuple[str, List[str], List[RelationType]]] = [
            (source_id, [source_id], [])
        ]
        
        while queue:
            current_id, path, rels = queue.pop(0)
            
            if current_id == target_id:
                return DependencyChain(
                    source_id=source_id,
                    target_id=target_id,
                    path=path,
                    relationships=rels,
                    depth=len(path) - 1,
                )
            
            if current_id in visited or len(path) > max_depth:
                continue
            visited.add(current_id)
            
            for rel in self.get_outgoing(current_id):
                if rel.target_id not in visited:
                    queue.append((
                        rel.target_id,
                        path + [rel.target_id],
                        rels + [rel.type],
                    ))
        
        return None
    
    def detect_circular_dependencies(self) -> List[DependencyChain]:
        """Detect circular dependencies in the graph.
        
        Returns:
            List of circular dependency chains
        """
        cycles = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        
        def dfs(node_id: str, path: List[str], rels: List[RelationType]):
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for rel in self.get_outgoing(node_id, RelationType.DEPENDS_ON):
                if rel.target_id not in visited:
                    dfs(rel.target_id, path + [rel.target_id], rels + [rel.type])
                elif rel.target_id in rec_stack:
                    # Found cycle
                    cycle_start = path.index(rel.target_id)
                    cycles.append(DependencyChain(
                        source_id=rel.target_id,
                        target_id=node_id,
                        path=path[cycle_start:] + [rel.target_id],
                        relationships=rels[cycle_start:] + [rel.type],
                        is_circular=True,
                    ))
            
            rec_stack.discard(node_id)
        
        for node_id in self._nodes:
            if node_id not in visited:
                dfs(node_id, [node_id], [])
        
        return cycles
    
    # ============= Ownership =============
    
    def set_ownership(self, ownership: OwnershipInfo) -> None:
        """Set ownership for a node."""
        with self._lock:
            self._ownership[ownership.node_id] = ownership
    
    def get_ownership(self, node_id: str) -> Optional[OwnershipInfo]:
        """Get ownership for a node."""
        return self._ownership.get(node_id)
    
    def get_nodes_by_owner(self, owner_team: str) -> List[GraphNode]:
        """Get all nodes owned by a team."""
        results = []
        for node_id, ownership in self._ownership.items():
            if ownership.owner_team == owner_team:
                node = self.get_node(node_id)
                if node:
                    results.append(node)
        return results
    
    # ============= Stats =============
    
    def get_stats(self) -> GraphStats:
        """Get statistics about the graph."""
        stats = GraphStats(
            total_nodes=len(self._nodes),
            total_relationships=len(self._relationships),
        )
        
        # By type
        for node_type, node_ids in self._nodes_by_type.items():
            stats.nodes_by_type[node_type.value] = len(node_ids)
        
        for rel_type, rel_ids in self._relationships_by_type.items():
            stats.relationships_by_type[rel_type.value] = len(rel_ids)
        
        # Files
        stats.files_indexed = len(self._nodes_by_file)
        
        # Orphans (nodes with no relationships)
        for node_id in self._nodes:
            if not self._outgoing.get(node_id) and not self._incoming.get(node_id):
                stats.orphan_nodes += 1
        
        # Circular dependencies
        stats.circular_dependencies = len(self.detect_circular_dependencies())
        
        return stats
    
    # ============= Serialization =============
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "nodes": {
                nid: {
                    "id": n.id,
                    "type": n.type.value,
                    "name": n.name,
                    "file_path": n.file_path,
                    "start_line": n.start_line,
                    "end_line": n.end_line,
                    "signature": n.signature,
                    "attributes": n.attributes,
                }
                for nid, n in self._nodes.items()
            },
            "relationships": {
                rid: {
                    "id": r.id,
                    "type": r.type.value,
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "attributes": r.attributes,
                }
                for rid, r in self._relationships.items()
            },
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KnowledgeGraph:
        """Deserialize graph from dictionary."""
        graph = cls(tenant_id=data.get("tenant_id", "default"))
        
        # Load nodes
        for node_data in data.get("nodes", {}).values():
            node = GraphNode(
                id=node_data["id"],
                type=NodeType(node_data["type"]),
                name=node_data["name"],
                file_path=node_data.get("file_path"),
                start_line=node_data.get("start_line"),
                end_line=node_data.get("end_line"),
                signature=node_data.get("signature"),
                attributes=node_data.get("attributes", {}),
            )
            graph.add_node(node)
        
        # Load relationships
        for rel_data in data.get("relationships", {}).values():
            rel = GraphRelationship(
                id=rel_data["id"],
                type=RelationType(rel_data["type"]),
                source_id=rel_data["source_id"],
                target_id=rel_data["target_id"],
                attributes=rel_data.get("attributes", {}),
            )
            try:
                graph.add_relationship(rel)
            except ValueError:
                pass  # Skip invalid relationships
        
        return graph

