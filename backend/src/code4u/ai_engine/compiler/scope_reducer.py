from __future__ import annotations
"""Scope reduction for the Prompt Compiler.

NEVER load entire repositories.
Select ONLY relevant files and symbols.
"""
from dataclasses import dataclass
import structlog

from code4u.ai_engine.compiler.types import (
    CompilerInput,
    CompiledScope,
    FileScope,
    GraphNode,
)

logger = structlog.get_logger("compiler.scope")


@dataclass
class ScopeConfig:
    """Configuration for scope reduction."""
    max_files: int = 12
    max_symbols: int = 20
    max_tokens: int = 8000
    include_readonly_context: bool = True
    include_tests: bool = False
    

class ScopeReducer:
    """
    Reduce Knowledge Graph scope to minimal LLM context.
    
    Phase 1 of prompt compilation:
    - Max files: 5–12
    - Max symbols: 20
    - No cross-owner edits
    - No new public APIs unless flagged
    """
    
    def __init__(self, config: ScopeConfig | None = None):
        self.config = config or ScopeConfig()
    
    def reduce(self, input: CompilerInput) -> CompiledScope:
        """
        Reduce scope to minimal set of files.
        
        Priority order:
        1. Primary target file
        2. Direct dependencies
        3. Direct dependents (consumers)
        4. Shared types/schemas
        5. Context files (readonly)
        """
        logger.info(
            "reducing_scope",
            target=input.target_node_id,
            impacted_count=len(input.impacted_nodes),
            max_files=self.config.max_files
        )
        
        # Start with target node
        files: list[FileScope] = []
        primary_file_id = input.target_node_id
        
        # Add primary file
        primary_node = self._find_node(input.target_node_id, input.impacted_nodes)
        if primary_node:
            files.append(self._node_to_file_scope(primary_node, is_primary=True))
        
        # Categorize impacted nodes
        direct_deps = []
        direct_dependents = []
        schemas = []
        other = []
        
        for node in input.impacted_nodes:
            if node.node_id == input.target_node_id:
                continue
            
            if node.node_type == "schema":
                schemas.append(node)
            elif self._is_dependency(node, input):
                direct_deps.append(node)
            elif self._is_dependent(node, input):
                direct_dependents.append(node)
            else:
                other.append(node)
        
        # Add in priority order
        remaining_slots = self.config.max_files - len(files)
        
        # 1. Schemas (critical for type safety)
        for node in schemas[:min(3, remaining_slots)]:
            files.append(self._node_to_file_scope(node))
            remaining_slots -= 1
        
        # 2. Direct dependencies
        for node in direct_deps[:min(4, remaining_slots)]:
            files.append(self._node_to_file_scope(node))
            remaining_slots -= 1
        
        # 3. Direct dependents
        for node in direct_dependents[:min(3, remaining_slots)]:
            files.append(self._node_to_file_scope(node))
            remaining_slots -= 1
        
        # 4. Context files (readonly)
        if self.config.include_readonly_context and remaining_slots > 0:
            for node in other[:remaining_slots]:
                files.append(self._node_to_file_scope(node, is_readonly=True))
        
        # Filter tests unless explicitly included
        if not self.config.include_tests:
            files = [f for f in files if not self._is_test_file(f.path)]
        
        # Extract symbols
        symbols = self._extract_symbols(files)[:self.config.max_symbols]
        
        # Calculate token estimate
        total_tokens = sum(len(f.content) // 4 for f in files if f.content)
        
        # Build cross-file references
        cross_refs = self._build_cross_references(files)
        
        logger.info(
            "scope_reduced",
            file_count=len(files),
            symbol_count=len(symbols),
            estimated_tokens=total_tokens
        )
        
        return CompiledScope(
            files=files,
            primary_file_id=primary_file_id,
            total_tokens_estimate=total_tokens,
            symbols_in_scope=symbols,
            cross_file_references=cross_refs,
        )
    
    def _find_node(
        self,
        node_id: str,
        nodes: list[GraphNode]
    ) -> GraphNode | None:
        """Find a node by ID."""
        for node in nodes:
            if node.node_id == node_id:
                return node
        return None
    
    def _node_to_file_scope(
        self,
        node: GraphNode,
        is_primary: bool = False,
        is_readonly: bool = False
    ) -> FileScope:
        """Convert graph node to file scope."""
        return FileScope(
            file_id=node.node_id,
            path=node.path or f"{node.name}.unknown",
            content=node.content or "",
            language=self._detect_language(node.path or ""),
            symbols=[node.name] if node.name else [],
            is_primary=is_primary,
            is_readonly=is_readonly,
        )
    
    def _is_dependency(self, node: GraphNode, input: CompilerInput) -> bool:
        """Check if node is a dependency of the target."""
        # Would integrate with knowledge graph relationships
        return node.node_type in ("module", "package", "schema")
    
    def _is_dependent(self, node: GraphNode, input: CompilerInput) -> bool:
        """Check if node depends on the target."""
        return node.node_type in ("endpoint", "component", "service")
    
    def _is_test_file(self, path: str) -> bool:
        """Check if file is a test file."""
        test_patterns = [
            "test_", "_test.", ".test.", ".spec.",
            "/tests/", "/__tests__/", "/test/"
        ]
        path_lower = path.lower()
        return any(p in path_lower for p in test_patterns)
    
    def _detect_language(self, path: str) -> str:
        """Detect language from file path."""
        ext_map = {
            ".ts": "typescript", ".tsx": "typescript",
            ".js": "javascript", ".jsx": "javascript",
            ".py": "python",
            ".go": "go",
            ".rs": "rust",
        }
        for ext, lang in ext_map.items():
            if path.endswith(ext):
                return lang
        return "unknown"
    
    def _extract_symbols(self, files: list[FileScope]) -> List[str]:
        """Extract all symbols from files."""
        symbols = []
        for f in files:
            symbols.extend(f.symbols)
        return list(set(symbols))
    
    def _build_cross_references(
        self,
        files: list[FileScope]
    ) -> dict[str, List[str]]:
        """Build map of cross-file references."""
        refs: dict[str, List[str]] = {}
        
        for f in files:
            refs[f.file_id] = []
            for other in files:
                if other.file_id != f.file_id:
                    # Simple heuristic: check if file name appears in content
                    if other.path and f.content:
                        name = other.path.split("/")[-1].split(".")[0]
                        if name in f.content:
                            refs[f.file_id].append(other.file_id)
        
        return refs

