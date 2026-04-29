"""Graph traversal utilities."""

from __future__ import annotations
from typing import Optional, List, Set, Callable, Iterator, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from .models import NodeType, RelationType, GraphNode, GraphRelationship
from .graph import KnowledgeGraph


class TraversalOrder(str, Enum):
    """Order of traversal."""
    BREADTH_FIRST = "bfs"
    DEPTH_FIRST = "dfs"


@dataclass
class TraversalResult:
    """Result of a graph traversal."""
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphRelationship] = field(default_factory=list)
    path: List[str] = field(default_factory=list)
    depth_map: Dict[str, int] = field(default_factory=dict)


class GraphTraverser:
    """
    Traversal utilities for the Knowledge Graph.
    
    Provides:
    - BFS/DFS traversal
    - Path finding
    - Subgraph extraction
    - Cycle detection
    """
    
    def __init__(self, graph: KnowledgeGraph):
        """Initialize traverser.
        
        Args:
            graph: KnowledgeGraph to traverse
        """
        self.graph = graph
    
    def traverse(
        self,
        start_id: str,
        rel_types: Optional[List[RelationType]] = None,
        direction: str = "outgoing",  # outgoing, incoming, both
        max_depth: int = 10,
        order: TraversalOrder = TraversalOrder.BREADTH_FIRST,
        filter_fn: Optional[Callable[[GraphNode], bool]] = None,
        stop_fn: Optional[Callable[[GraphNode, int], bool]] = None,
    ) -> TraversalResult:
        """Traverse the graph from a starting node.
        
        Args:
            start_id: Starting node ID
            rel_types: Relationship types to follow (None = all)
            direction: Direction to traverse
            max_depth: Maximum traversal depth
            order: BFS or DFS
            filter_fn: Function to filter nodes
            stop_fn: Function to stop traversal (node, depth) -> bool
            
        Returns:
            TraversalResult with visited nodes
        """
        result = TraversalResult()
        visited: Set[str] = set()
        
        if order == TraversalOrder.BREADTH_FIRST:
            queue: List[Tuple[str, int]] = [(start_id, 0)]
        else:
            queue = [(start_id, 0)]
        
        while queue:
            if order == TraversalOrder.BREADTH_FIRST:
                node_id, depth = queue.pop(0)
            else:
                node_id, depth = queue.pop()
            
            if node_id in visited:
                continue
            
            if depth > max_depth:
                continue
            
            node = self.graph.get_node(node_id)
            if not node:
                continue
            
            # Check stop condition
            if stop_fn and stop_fn(node, depth):
                continue
            
            # Check filter
            if filter_fn and not filter_fn(node):
                continue
            
            visited.add(node_id)
            result.nodes.append(node)
            result.depth_map[node_id] = depth
            
            # Get neighbors
            neighbors = self._get_neighbors(node_id, rel_types, direction)
            
            for neighbor_id, rel in neighbors:
                if neighbor_id not in visited:
                    queue.append((neighbor_id, depth + 1))
                    result.edges.append(rel)
        
        return result
    
    def _get_neighbors(
        self,
        node_id: str,
        rel_types: Optional[List[RelationType]],
        direction: str,
    ) -> List[Tuple[str, GraphRelationship]]:
        """Get neighboring nodes."""
        neighbors = []
        
        if direction in ["outgoing", "both"]:
            for rel in self.graph.get_outgoing(node_id):
                if rel_types is None or rel.type in rel_types:
                    neighbors.append((rel.target_id, rel))
        
        if direction in ["incoming", "both"]:
            for rel in self.graph.get_incoming(node_id):
                if rel_types is None or rel.type in rel_types:
                    neighbors.append((rel.source_id, rel))
        
        return neighbors
    
    def find_path(
        self,
        start_id: str,
        end_id: str,
        rel_types: Optional[List[RelationType]] = None,
        max_depth: int = 20,
    ) -> Optional[List[str]]:
        """Find shortest path between two nodes.
        
        Args:
            start_id: Starting node
            end_id: Target node
            rel_types: Relationship types to follow
            max_depth: Maximum path length
            
        Returns:
            List of node IDs in path, or None if no path
        """
        if start_id == end_id:
            return [start_id]
        
        visited: Set[str] = set()
        queue: List[Tuple[str, List[str]]] = [(start_id, [start_id])]
        
        while queue:
            node_id, path = queue.pop(0)
            
            if len(path) > max_depth:
                continue
            
            if node_id in visited:
                continue
            visited.add(node_id)
            
            neighbors = self._get_neighbors(node_id, rel_types, "outgoing")
            
            for neighbor_id, _ in neighbors:
                if neighbor_id == end_id:
                    return path + [neighbor_id]
                
                if neighbor_id not in visited:
                    queue.append((neighbor_id, path + [neighbor_id]))
        
        return None
    
    def find_all_paths(
        self,
        start_id: str,
        end_id: str,
        rel_types: Optional[List[RelationType]] = None,
        max_depth: int = 10,
        max_paths: int = 100,
    ) -> List[List[str]]:
        """Find all paths between two nodes.
        
        Args:
            start_id: Starting node
            end_id: Target node
            rel_types: Relationship types to follow
            max_depth: Maximum path length
            max_paths: Maximum number of paths to return
            
        Returns:
            List of paths (each path is list of node IDs)
        """
        paths: List[List[str]] = []
        
        def dfs(current: str, path: List[str], visited: Set[str]):
            if len(paths) >= max_paths:
                return
            if len(path) > max_depth:
                return
            
            if current == end_id:
                paths.append(path.copy())
                return
            
            neighbors = self._get_neighbors(current, rel_types, "outgoing")
            
            for neighbor_id, _ in neighbors:
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    path.append(neighbor_id)
                    dfs(neighbor_id, path, visited)
                    path.pop()
                    visited.discard(neighbor_id)
        
        dfs(start_id, [start_id], {start_id})
        return paths
    
    def extract_subgraph(
        self,
        center_id: str,
        radius: int = 2,
        rel_types: Optional[List[RelationType]] = None,
    ) -> tuple[List[GraphNode], List[GraphRelationship]]:
        """Extract a subgraph around a center node.
        
        Args:
            center_id: Center node
            radius: Number of hops from center
            rel_types: Relationship types to follow
            
        Returns:
            Tuple of (nodes, relationships)
        """
        result = self.traverse(
            start_id=center_id,
            rel_types=rel_types,
            direction="both",
            max_depth=radius,
        )
        
        # Get all relationships between visited nodes
        node_ids = {n.id for n in result.nodes}
        relationships = []
        
        for node in result.nodes:
            for rel in self.graph.get_outgoing(node.id):
                if rel.target_id in node_ids:
                    relationships.append(rel)
        
        return result.nodes, relationships
    
    def find_connected_components(self) -> List[Set[str]]:
        """Find all connected components in the graph.
        
        Returns:
            List of sets of node IDs (each set is a component)
        """
        visited: Set[str] = set()
        components: List[Set[str]] = []
        
        for node_id in self.graph._nodes:
            if node_id in visited:
                continue
            
            # BFS to find all connected nodes
            component: Set[str] = set()
            queue = [node_id]
            
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                
                visited.add(current)
                component.add(current)
                
                # Get all neighbors (both directions)
                for rel in self.graph.get_outgoing(current):
                    if rel.target_id not in visited:
                        queue.append(rel.target_id)
                
                for rel in self.graph.get_incoming(current):
                    if rel.source_id not in visited:
                        queue.append(rel.source_id)
            
            if component:
                components.append(component)
        
        return components
    
    def topological_sort(
        self,
        rel_type: RelationType = RelationType.DEPENDS_ON
    ) -> Optional[List[str]]:
        """Perform topological sort on the graph.
        
        Args:
            rel_type: Relationship type to use for ordering
            
        Returns:
            List of node IDs in topological order, or None if cycle exists
        """
        # Calculate in-degrees
        in_degree: Dict[str, int] = {nid: 0 for nid in self.graph._nodes}
        
        for node_id in self.graph._nodes:
            for rel in self.graph.get_outgoing(node_id, rel_type):
                in_degree[rel.target_id] = in_degree.get(rel.target_id, 0) + 1
        
        # Queue nodes with no dependencies
        queue = [nid for nid, degree in in_degree.items() if degree == 0]
        result: List[str] = []
        
        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            
            for rel in self.graph.get_outgoing(node_id, rel_type):
                in_degree[rel.target_id] -= 1
                if in_degree[rel.target_id] == 0:
                    queue.append(rel.target_id)
        
        # Check for cycle
        if len(result) != len(self.graph._nodes):
            return None
        
        return result
    
    def get_node_metrics(self, node_id: str) -> Dict[str, Any]:
        """Calculate metrics for a node.
        
        Args:
            node_id: Node to analyze
            
        Returns:
            Dictionary of metrics
        """
        node = self.graph.get_node(node_id)
        if not node:
            return {}
        
        outgoing = self.graph.get_outgoing(node_id)
        incoming = self.graph.get_incoming(node_id)
        
        return {
            "out_degree": len(outgoing),
            "in_degree": len(incoming),
            "total_degree": len(outgoing) + len(incoming),
            "dependencies": node.dependencies_count,
            "dependents": node.dependents_count,
            "is_leaf": len(outgoing) == 0,
            "is_root": len(incoming) == 0,
            "is_isolated": len(outgoing) == 0 and len(incoming) == 0,
        }

