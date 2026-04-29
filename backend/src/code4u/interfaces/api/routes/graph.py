"""API routes for Knowledge Graph."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid

from code4u.code_intelligence.knowledge_graph import (
    KnowledgeGraph,
    CodeIndexer,
    QueryBuilder,
    GraphTraverser,
    NodeType,
    RelationType,
    GraphNode as KGNode,
    ImpactAnalysis as KGImpactAnalysis,
)


router = APIRouter(prefix="/graph", tags=["knowledge-graph"])

# Tenant graphs storage
_graphs: Dict[str, KnowledgeGraph] = {}


def get_graph(tenant_id: str) -> KnowledgeGraph:
    """Get or create graph for tenant."""
    if tenant_id not in _graphs:
        _graphs[tenant_id] = KnowledgeGraph(tenant_id=tenant_id)
    return _graphs[tenant_id]


# ============= Request/Response Models =============

class IndexDirectoryRequest(BaseModel):
    """Request to index a directory."""
    directory: str
    recursive: bool = True
    codeowners_path: Optional[str] = None


class IndexResponse(BaseModel):
    """Response from indexing."""
    files_indexed: int
    nodes_created: int
    relationships_created: int
    errors: int


class NodeModel(BaseModel):
    """API model for graph node."""
    id: str
    type: str
    name: str
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    language: Optional[str] = None
    visibility: str = "public"
    is_exported: bool = False
    signature: Optional[str] = None
    docstring: Optional[str] = None


class RelationshipModel(BaseModel):
    """API model for relationship."""
    id: str
    type: str
    source_id: str
    target_id: str
    line_number: Optional[int] = None


class QueryRequest(BaseModel):
    """Request for graph query."""
    node_types: List[str] = []
    name: Optional[str] = None
    name_pattern: Optional[str] = None
    file_path: Optional[str] = None
    is_exported: Optional[bool] = None
    limit: int = 100
    offset: int = 0


class QueryResponse(BaseModel):
    """Response from graph query."""
    nodes: List[NodeModel]
    total_count: int
    has_more: bool


class ImpactRequest(BaseModel):
    """Request for impact analysis."""
    node_id: Optional[str] = None
    file_path: Optional[str] = None
    symbol: Optional[str] = None
    max_depth: int = 10


class ImpactResponse(BaseModel):
    """Response from impact analysis."""
    target_node_id: str
    directly_impacted: List[str]
    transitively_impacted: List[str]
    impacted_files: List[str]
    impacted_functions: List[str]
    impacted_classes: List[str]
    impacted_teams: List[str]
    breaking_change: bool
    risk_level: str
    total_nodes_affected: int
    recommendations: List[str]


class PathRequest(BaseModel):
    """Request to find path between nodes."""
    start_id: str
    end_id: str
    max_depth: int = 20


class PathResponse(BaseModel):
    """Response with path."""
    path: Optional[List[str]]
    found: bool


class StatsResponse(BaseModel):
    """Graph statistics."""
    total_nodes: int
    total_relationships: int
    nodes_by_type: Dict[str, int]
    relationships_by_type: Dict[str, int]
    files_indexed: int
    orphan_nodes: int
    circular_dependencies: int


# ============= Endpoints =============

@router.post("/index", response_model=IndexResponse)
async def index_directory(
    request: IndexDirectoryRequest,
    background_tasks: BackgroundTasks,
    x_tenant_id: str = Header(default="default"),
) -> IndexResponse:
    """Index a directory to build the Knowledge Graph.
    
    Args:
        request: Index request with directory path
        x_tenant_id: Tenant ID
        
    Returns:
        Index statistics
    """
    graph = get_graph(x_tenant_id)
    indexer = CodeIndexer(graph)
    
    try:
        stats = indexer.index_directory(
            directory=request.directory,
            recursive=request.recursive,
        )
        
        # Parse CODEOWNERS if provided
        if request.codeowners_path:
            indexer.parse_codeowners(request.codeowners_path)
        
        return IndexResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes/{node_id}", response_model=NodeModel)
async def get_node(
    node_id: str,
    x_tenant_id: str = Header(default="default"),
) -> NodeModel:
    """Get a specific node by ID."""
    graph = get_graph(x_tenant_id)
    node = graph.get_node(node_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    return NodeModel(
        id=node.id,
        type=node.type.value,
        name=node.name,
        file_path=node.file_path,
        start_line=node.start_line,
        end_line=node.end_line,
        language=node.language,
        visibility=node.visibility,
        is_exported=node.is_exported,
        signature=node.signature,
        docstring=node.docstring,
    )


@router.post("/query", response_model=QueryResponse)
async def query_graph(
    request: QueryRequest,
    x_tenant_id: str = Header(default="default"),
) -> QueryResponse:
    """Query the Knowledge Graph."""
    graph = get_graph(x_tenant_id)
    builder = QueryBuilder(graph)
    
    # Build query
    if request.node_types:
        types = [NodeType(t) for t in request.node_types]
        builder.nodes_of_type(*types)
    
    if request.name:
        builder.named(request.name)
    
    if request.file_path:
        builder.in_file(request.file_path)
    
    if request.is_exported:
        builder.is_exported()
    
    builder.limit(request.limit).offset(request.offset)
    
    result = builder.execute()
    
    nodes = [
        NodeModel(
            id=n.id,
            type=n.type.value,
            name=n.name,
            file_path=n.file_path,
            start_line=n.start_line,
            end_line=n.end_line,
            language=n.language,
            visibility=n.visibility,
            is_exported=n.is_exported,
            signature=n.signature,
            docstring=n.docstring,
        )
        for n in result.nodes
    ]
    
    return QueryResponse(
        nodes=nodes,
        total_count=result.total_count,
        has_more=result.has_more,
    )


@router.post("/impact", response_model=ImpactResponse)
async def analyze_impact(
    request: ImpactRequest,
    x_tenant_id: str = Header(default="default"),
) -> ImpactResponse:
    """Analyze impact of changes to a node."""
    graph = get_graph(x_tenant_id)
    
    # Find node
    node_id = request.node_id
    if not node_id and request.file_path:
        nodes = graph.find_nodes(file_path=request.file_path)
        if nodes:
            node_id = nodes[0].id
    
    if not node_id and request.symbol:
        nodes = graph.find_nodes(name=request.symbol)
        if nodes:
            node_id = nodes[0].id
    
    if not node_id:
        raise HTTPException(status_code=404, detail="Node not found")
    
    try:
        analysis = graph.analyze_impact(node_id, max_depth=request.max_depth)
        
        return ImpactResponse(
            target_node_id=analysis.target_node_id,
            directly_impacted=analysis.directly_impacted,
            transitively_impacted=analysis.transitively_impacted,
            impacted_files=analysis.impacted_files,
            impacted_functions=analysis.impacted_functions,
            impacted_classes=analysis.impacted_classes,
            impacted_teams=analysis.impacted_teams,
            breaking_change=analysis.breaking_change,
            risk_level=analysis.risk_level,
            total_nodes_affected=analysis.total_nodes_affected,
            recommendations=analysis.recommendations,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/path", response_model=PathResponse)
async def find_path(
    request: PathRequest,
    x_tenant_id: str = Header(default="default"),
) -> PathResponse:
    """Find path between two nodes."""
    graph = get_graph(x_tenant_id)
    traverser = GraphTraverser(graph)
    
    path = traverser.find_path(
        start_id=request.start_id,
        end_id=request.end_id,
        max_depth=request.max_depth,
    )
    
    return PathResponse(
        path=path,
        found=path is not None,
    )


@router.get("/nodes/{node_id}/dependents", response_model=QueryResponse)
async def get_dependents(
    node_id: str,
    max_depth: int = 5,
    x_tenant_id: str = Header(default="default"),
) -> QueryResponse:
    """Get all nodes that depend on this node."""
    graph = get_graph(x_tenant_id)
    traverser = GraphTraverser(graph)
    
    result = traverser.traverse(
        start_id=node_id,
        rel_types=[RelationType.DEPENDS_ON, RelationType.USES, RelationType.CALLS],
        direction="incoming",
        max_depth=max_depth,
    )
    
    nodes = [
        NodeModel(
            id=n.id,
            type=n.type.value,
            name=n.name,
            file_path=n.file_path,
            start_line=n.start_line,
            end_line=n.end_line,
            language=n.language,
            visibility=n.visibility,
            is_exported=n.is_exported,
        )
        for n in result.nodes
    ]
    
    return QueryResponse(
        nodes=nodes,
        total_count=len(nodes),
        has_more=False,
    )


@router.get("/nodes/{node_id}/dependencies", response_model=QueryResponse)
async def get_dependencies(
    node_id: str,
    max_depth: int = 5,
    x_tenant_id: str = Header(default="default"),
) -> QueryResponse:
    """Get all nodes this node depends on."""
    graph = get_graph(x_tenant_id)
    traverser = GraphTraverser(graph)
    
    result = traverser.traverse(
        start_id=node_id,
        rel_types=[RelationType.DEPENDS_ON, RelationType.USES, RelationType.CALLS],
        direction="outgoing",
        max_depth=max_depth,
    )
    
    nodes = [
        NodeModel(
            id=n.id,
            type=n.type.value,
            name=n.name,
            file_path=n.file_path,
            start_line=n.start_line,
            end_line=n.end_line,
            language=n.language,
            visibility=n.visibility,
            is_exported=n.is_exported,
        )
        for n in result.nodes
    ]
    
    return QueryResponse(
        nodes=nodes,
        total_count=len(nodes),
        has_more=False,
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    x_tenant_id: str = Header(default="default"),
) -> StatsResponse:
    """Get Knowledge Graph statistics."""
    graph = get_graph(x_tenant_id)
    stats = graph.get_stats()
    
    return StatsResponse(
        total_nodes=stats.total_nodes,
        total_relationships=stats.total_relationships,
        nodes_by_type=stats.nodes_by_type,
        relationships_by_type=stats.relationships_by_type,
        files_indexed=stats.files_indexed,
        orphan_nodes=stats.orphan_nodes,
        circular_dependencies=stats.circular_dependencies,
    )


@router.delete("/")
async def clear_graph(
    x_tenant_id: str = Header(default="default"),
) -> Dict[str, str]:
    """Clear the Knowledge Graph for a tenant."""
    if x_tenant_id in _graphs:
        del _graphs[x_tenant_id]
    return {"status": "cleared", "tenant_id": x_tenant_id}


@router.get("/health")
async def graph_health() -> Dict[str, Any]:
    """Health check for Knowledge Graph service."""
    return {
        "status": "healthy",
        "service": "knowledge-graph",
        "active_tenants": len(_graphs),
    }

