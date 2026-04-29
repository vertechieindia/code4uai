"""
code4u.ai Knowledge Graph

The Knowledge Graph is the MOST IMPORTANT system in code4u.ai.
It provides:
- Complete map of your codebase
- Every function, class, dependency, relationship
- Cross-repo understanding
- Ownership boundaries
- Real-time sync with code changes

This is what makes us deterministic. The LLM never guesses - it knows.
"""

from .models import (
    NodeType,
    RelationType,
    GraphNode,
    GraphRelationship,
    ImpactAnalysis,
    OwnershipInfo,
    DependencyChain,
)
from .graph import KnowledgeGraph
from .indexer import CodeIndexer
from .query import QueryBuilder, GraphQuery
from .traversal import GraphTraverser
from .symbol_indexer import SymbolIndexer, DependencyMap, SymbolDef, ImportRef, ExportRef

__all__ = [
    # Models
    "NodeType",
    "RelationType",
    "GraphNode",
    "GraphRelationship",
    "ImpactAnalysis",
    "OwnershipInfo",
    "DependencyChain",
    # Core
    "KnowledgeGraph",
    "CodeIndexer",
    "QueryBuilder",
    "GraphQuery",
    "GraphTraverser",
    # Lightweight indexer (Day 2)
    "SymbolIndexer",
    "DependencyMap",
    "SymbolDef",
    "ImportRef",
    "ExportRef",
]

