"""Code indexer for building the Knowledge Graph from source code."""

from __future__ import annotations
import ast
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
import uuid

from .models import (
    NodeType,
    RelationType,
    GraphNode,
    GraphRelationship,
    OwnershipInfo,
)
from .graph import KnowledgeGraph


class CodeIndexer:
    """
    Indexes source code to build the Knowledge Graph.
    
    Supports:
    - Python (AST-based)
    - TypeScript/JavaScript (regex-based)
    - More languages can be added
    """
    
    # File extensions to index
    SUPPORTED_EXTENSIONS = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".java": "java",
        ".kt": "kotlin",
        ".go": "go",
        ".rs": "rust",
    }
    
    # Directories to skip
    SKIP_DIRS = {
        "node_modules",
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".next",
        "target",
    }
    
    def __init__(self, graph: KnowledgeGraph):
        """Initialize indexer with target graph.
        
        Args:
            graph: KnowledgeGraph to populate
        """
        self.graph = graph
        self._file_node_ids: Dict[str, str] = {}
    
    def index_directory(
        self,
        directory: str,
        recursive: bool = True,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """Index all supported files in a directory.
        
        Args:
            directory: Path to directory
            recursive: Whether to recurse into subdirectories
            include_patterns: Glob patterns to include
            exclude_patterns: Glob patterns to exclude
            
        Returns:
            Statistics about indexed files
        """
        stats = {
            "files_indexed": 0,
            "nodes_created": 0,
            "relationships_created": 0,
            "errors": 0,
        }
        
        path = Path(directory)
        if not path.exists():
            raise ValueError(f"Directory not found: {directory}")
        
        # Walk directory
        for root, dirs, files in os.walk(directory):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            
            if not recursive:
                dirs.clear()
            
            for filename in files:
                file_path = os.path.join(root, filename)
                ext = os.path.splitext(filename)[1]
                
                if ext not in self.SUPPORTED_EXTENSIONS:
                    continue
                
                try:
                    result = self.index_file(file_path)
                    stats["files_indexed"] += 1
                    stats["nodes_created"] += result.get("nodes", 0)
                    stats["relationships_created"] += result.get("relationships", 0)
                except Exception as e:
                    stats["errors"] += 1
        
        # Build cross-file relationships
        self._build_import_relationships()
        
        return stats
    
    def index_file(self, file_path: str) -> Dict[str, int]:
        """Index a single file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Statistics about indexed entities
        """
        ext = os.path.splitext(file_path)[1]
        language = self.SUPPORTED_EXTENSIONS.get(ext, "unknown")
        
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # Create file node
        file_node = GraphNode(
            id=str(uuid.uuid4()),
            type=NodeType.FILE,
            name=os.path.basename(file_path),
            file_path=file_path,
            language=language,
            last_modified=datetime.fromtimestamp(os.path.getmtime(file_path)),
        )
        self.graph.add_node(file_node)
        self._file_node_ids[file_path] = file_node.id
        
        # Language-specific indexing
        if language == "python":
            return self._index_python(file_path, content, file_node)
        elif language in ["typescript", "javascript"]:
            return self._index_typescript(file_path, content, file_node)
        else:
            return self._index_generic(file_path, content, file_node)
    
    def _index_python(
        self, 
        file_path: str, 
        content: str, 
        file_node: GraphNode
    ) -> Dict[str, int]:
        """Index Python file using AST."""
        stats = {"nodes": 1, "relationships": 0}
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return stats
        
        # Track imports for later relationship building
        imports: List[Dict[str, Any]] = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_node = GraphNode(
                    id=str(uuid.uuid4()),
                    type=NodeType.CLASS,
                    name=node.name,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno,
                    language="python",
                    docstring=ast.get_docstring(node),
                    is_exported=not node.name.startswith("_"),
                )
                self.graph.add_node(class_node)
                stats["nodes"] += 1
                
                # Relationship: file contains class
                self.graph.add_relationship(GraphRelationship(
                    id=str(uuid.uuid4()),
                    type=RelationType.CONTAINS,
                    source_id=file_node.id,
                    target_id=class_node.id,
                ))
                stats["relationships"] += 1
                
                # Index methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        method_node = GraphNode(
                            id=str(uuid.uuid4()),
                            type=NodeType.METHOD,
                            name=item.name,
                            file_path=file_path,
                            start_line=item.lineno,
                            end_line=item.end_lineno,
                            language="python",
                            visibility="private" if item.name.startswith("_") else "public",
                            docstring=ast.get_docstring(item),
                        )
                        self.graph.add_node(method_node)
                        stats["nodes"] += 1
                        
                        self.graph.add_relationship(GraphRelationship(
                            id=str(uuid.uuid4()),
                            type=RelationType.CONTAINS,
                            source_id=class_node.id,
                            target_id=method_node.id,
                        ))
                        stats["relationships"] += 1
                
                # Handle inheritance
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        class_node.attributes["extends"] = base.id
            
            elif isinstance(node, ast.FunctionDef) and not isinstance(node, ast.AsyncFunctionDef):
                # Top-level function
                if not any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree)):
                    func_node = GraphNode(
                        id=str(uuid.uuid4()),
                        type=NodeType.FUNCTION,
                        name=node.name,
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=node.end_lineno,
                        language="python",
                        is_exported=not node.name.startswith("_"),
                        docstring=ast.get_docstring(node),
                    )
                    self.graph.add_node(func_node)
                    stats["nodes"] += 1
                    
                    self.graph.add_relationship(GraphRelationship(
                        id=str(uuid.uuid4()),
                        type=RelationType.CONTAINS,
                        source_id=file_node.id,
                        target_id=func_node.id,
                    ))
                    stats["relationships"] += 1
            
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "module": alias.name,
                        "name": alias.asname or alias.name,
                        "line": node.lineno,
                    })
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append({
                        "module": module,
                        "name": alias.name,
                        "line": node.lineno,
                    })
        
        # Store imports for later processing
        file_node.attributes["imports"] = imports
        
        return stats
    
    def _index_typescript(
        self, 
        file_path: str, 
        content: str, 
        file_node: GraphNode
    ) -> Dict[str, int]:
        """Index TypeScript/JavaScript file using regex."""
        stats = {"nodes": 1, "relationships": 0}
        
        lines = content.split("\n")
        
        # Patterns
        patterns = {
            "class": r"(?:export\s+)?class\s+(\w+)",
            "interface": r"(?:export\s+)?interface\s+(\w+)",
            "type": r"(?:export\s+)?type\s+(\w+)",
            "function": r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
            "const_func": r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>",
            "import": r"import\s+(?:{[^}]+}|\*\s+as\s+\w+|\w+)\s+from\s+['\"]([^'\"]+)['\"]",
        }
        
        imports: List[Dict[str, Any]] = []
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Classes
            match = re.search(patterns["class"], line)
            if match:
                node = GraphNode(
                    id=str(uuid.uuid4()),
                    type=NodeType.CLASS,
                    name=match.group(1),
                    file_path=file_path,
                    start_line=line_num,
                    language="typescript",
                    is_exported="export" in line,
                )
                self.graph.add_node(node)
                self.graph.add_relationship(GraphRelationship(
                    id=str(uuid.uuid4()),
                    type=RelationType.CONTAINS,
                    source_id=file_node.id,
                    target_id=node.id,
                ))
                stats["nodes"] += 1
                stats["relationships"] += 1
            
            # Interfaces
            match = re.search(patterns["interface"], line)
            if match:
                node = GraphNode(
                    id=str(uuid.uuid4()),
                    type=NodeType.INTERFACE,
                    name=match.group(1),
                    file_path=file_path,
                    start_line=line_num,
                    language="typescript",
                    is_exported="export" in line,
                )
                self.graph.add_node(node)
                self.graph.add_relationship(GraphRelationship(
                    id=str(uuid.uuid4()),
                    type=RelationType.CONTAINS,
                    source_id=file_node.id,
                    target_id=node.id,
                ))
                stats["nodes"] += 1
                stats["relationships"] += 1
            
            # Functions
            match = re.search(patterns["function"], line)
            if match:
                node = GraphNode(
                    id=str(uuid.uuid4()),
                    type=NodeType.FUNCTION,
                    name=match.group(1),
                    file_path=file_path,
                    start_line=line_num,
                    language="typescript",
                    is_exported="export" in line,
                )
                self.graph.add_node(node)
                self.graph.add_relationship(GraphRelationship(
                    id=str(uuid.uuid4()),
                    type=RelationType.CONTAINS,
                    source_id=file_node.id,
                    target_id=node.id,
                ))
                stats["nodes"] += 1
                stats["relationships"] += 1
            
            # Imports
            match = re.search(patterns["import"], line)
            if match:
                imports.append({
                    "module": match.group(1),
                    "line": line_num,
                })
        
        file_node.attributes["imports"] = imports
        
        return stats
    
    def _index_generic(
        self, 
        file_path: str, 
        content: str, 
        file_node: GraphNode
    ) -> Dict[str, int]:
        """Generic indexing for unsupported languages."""
        return {"nodes": 1, "relationships": 0}
    
    def _build_import_relationships(self) -> None:
        """Build relationships between files based on imports."""
        for file_path, file_node_id in self._file_node_ids.items():
            file_node = self.graph.get_node(file_node_id)
            if not file_node:
                continue
            
            imports = file_node.attributes.get("imports", [])
            
            for imp in imports:
                module = imp.get("module", "")
                
                # Try to resolve to a file in the graph
                for other_path, other_id in self._file_node_ids.items():
                    if other_path == file_path:
                        continue
                    
                    # Check if module matches file
                    other_name = os.path.splitext(os.path.basename(other_path))[0]
                    if module.endswith(other_name) or other_name in module:
                        self.graph.add_relationship(GraphRelationship(
                            id=str(uuid.uuid4()),
                            type=RelationType.IMPORTS,
                            source_id=file_node_id,
                            target_id=other_id,
                            line_number=imp.get("line"),
                        ))
    
    def parse_codeowners(self, codeowners_path: str) -> None:
        """Parse CODEOWNERS file and set ownership.
        
        Args:
            codeowners_path: Path to CODEOWNERS file
        """
        if not os.path.exists(codeowners_path):
            return
        
        with open(codeowners_path, "r") as f:
            lines = f.readlines()
        
        patterns: List[Tuple[str, List[str]]] = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                pattern = parts[0]
                owners = parts[1:]
                patterns.append((pattern, owners))
        
        # Apply patterns to files (reverse order for precedence)
        base_dir = os.path.dirname(codeowners_path)
        
        for pattern, owners in reversed(patterns):
            for file_path, node_id in self._file_node_ids.items():
                rel_path = os.path.relpath(file_path, base_dir)
                
                if self._match_pattern(rel_path, pattern):
                    ownership = OwnershipInfo(
                        node_id=node_id,
                        owner_team=owners[0].lstrip("@"),
                        codeowners_path=codeowners_path,
                        codeowners_pattern=pattern,
                        required_reviewers=[o.lstrip("@") for o in owners],
                    )
                    self.graph.set_ownership(ownership)
    
    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Match a path against a CODEOWNERS pattern."""
        import fnmatch
        
        # Handle directory patterns
        if pattern.endswith("/"):
            return path.startswith(pattern[:-1])
        
        # Handle glob patterns
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, f"**/{pattern}")

