"""Nexus Workspace Manager — multi-repo organizational intelligence.

Scans a parent directory for repositories (identified by ``.git``,
``pyproject.toml``, ``package.json``, or ``go.mod``) and builds a
unified ``GlobalRegistry`` connecting their symbol graphs.

The ``NexusContext`` is the single entry point for cross-repo queries:
  - Which repos exist under a root?
  - What symbols does each repo export?
  - Which repos depend on which other repos?
  - What is the cross-repo blast radius of a change?

Usage::

    nexus = NexusContext("/path/to/microservices")
    nexus.scan()
    nexus.index_all()
    print(nexus.summary())
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    DependencyMap,
    SymbolDef,
    SymbolIndexer,
)

logger = structlog.get_logger("nexus")


# ---------------------------------------------------------------------------
# Repo markers — files whose presence identifies a repo root
# ---------------------------------------------------------------------------

_REPO_MARKERS = {
    ".git",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "setup.py",
}

_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", "dist", "build", ".eggs",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RepoInfo:
    """Metadata for a single repository within the Nexus."""
    name: str
    path: str
    markers: List[str] = field(default_factory=list)
    file_count: int = 0
    symbol_count: int = 0
    import_count: int = 0
    cycle_count: int = 0
    indexed: bool = False
    index_duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "markers": self.markers,
            "fileCount": self.file_count,
            "symbolCount": self.symbol_count,
            "importCount": self.import_count,
            "cycleCount": self.cycle_count,
            "indexed": self.indexed,
            "indexDurationMs": round(self.index_duration_ms, 1),
        }


@dataclass
class ExternalEdge:
    """A dependency between two repositories."""
    source_repo: str
    target_repo: str
    symbol_name: str
    source_file: str = ""
    target_file: str = ""
    edge_type: str = "import"  # "import", "package", "workspace"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sourceRepo": self.source_repo,
            "targetRepo": self.target_repo,
            "symbolName": self.symbol_name,
            "sourceFile": self.source_file,
            "targetFile": self.target_file,
            "edgeType": self.edge_type,
        }


@dataclass
class GlobalRegistry:
    """Unified symbol registry spanning all repos in the Nexus."""
    repos: Dict[str, RepoInfo] = field(default_factory=dict)
    dep_maps: Dict[str, DependencyMap] = field(default_factory=dict)
    cross_edges: List[ExternalEdge] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return sum(r.file_count for r in self.repos.values())

    @property
    def total_symbols(self) -> int:
        return sum(r.symbol_count for r in self.repos.values())

    @property
    def total_cross_edges(self) -> int:
        return len(self.cross_edges)

    def find_symbol_global(self, symbol_name: str) -> List[Tuple[str, SymbolDef]]:
        """Find a symbol across all repos. Returns (repo_name, SymbolDef) pairs."""
        results = []
        for repo_name, dm in self.dep_maps.items():
            for sym in dm.get_symbol_defs(symbol_name):
                results.append((repo_name, sym))
        return results

    def get_cross_edges_for_symbol(self, symbol_name: str) -> List[ExternalEdge]:
        """Return all cross-repo edges involving a symbol."""
        return [e for e in self.cross_edges if e.symbol_name == symbol_name]

    def get_repo_dependents(self, repo_name: str) -> List[str]:
        """Return repos that depend on *repo_name*."""
        return sorted({
            e.source_repo for e in self.cross_edges
            if e.target_repo == repo_name and e.source_repo != repo_name
        })

    def get_repo_dependencies(self, repo_name: str) -> List[str]:
        """Return repos that *repo_name* depends on."""
        return sorted({
            e.target_repo for e in self.cross_edges
            if e.source_repo == repo_name and e.target_repo != repo_name
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repos": {k: v.to_dict() for k, v in self.repos.items()},
            "totalFiles": self.total_files,
            "totalSymbols": self.total_symbols,
            "crossEdges": self.total_cross_edges,
            "edges": [e.to_dict() for e in self.cross_edges],
        }


# ---------------------------------------------------------------------------
# NexusContext
# ---------------------------------------------------------------------------

class NexusContext:
    """Multi-repo workspace manager.

    Usage::

        nexus = NexusContext("/microservices")
        nexus.scan()           # find all repos
        nexus.index_all()      # build dep maps
        nexus.link_repos()     # discover cross-repo edges
        print(nexus.summary())
    """

    def __init__(self, root_path: str, *, max_depth: int = 2) -> None:
        self._root = Path(root_path).resolve()
        self._max_depth = max_depth
        self.registry = GlobalRegistry()

    @property
    def root_path(self) -> str:
        return str(self._root)

    @property
    def repo_count(self) -> int:
        return len(self.registry.repos)

    def scan(self) -> List[RepoInfo]:
        """Scan for repositories under the root directory."""
        self.registry.repos.clear()

        if not self._root.is_dir():
            return []

        self._scan_dir(self._root, depth=0)

        logger.info(
            "nexus_scanned",
            root=str(self._root),
            repos=len(self.registry.repos),
        )

        return list(self.registry.repos.values())

    def add_repo(self, path: str, name: str = "") -> RepoInfo:
        """Manually add a repo to the Nexus."""
        p = Path(path).resolve()
        repo_name = name or p.name
        markers = [m for m in _REPO_MARKERS if (p / m).exists()]
        info = RepoInfo(name=repo_name, path=str(p), markers=markers)
        self.registry.repos[repo_name] = info
        return info

    def index_all(self) -> Dict[str, RepoInfo]:
        """Index all discovered repos and build DependencyMaps."""
        for repo_name, info in self.registry.repos.items():
            self._index_repo(repo_name, info)

        return dict(self.registry.repos)

    def index_repo(self, repo_name: str) -> Optional[RepoInfo]:
        """Index a single repo by name."""
        info = self.registry.repos.get(repo_name)
        if not info:
            return None
        self._index_repo(repo_name, info)
        return info

    def link_repos(self) -> List[ExternalEdge]:
        """Discover cross-repo dependencies by comparing exports and imports."""
        self.registry.cross_edges.clear()

        # Build symbol-to-repo mapping
        symbol_origins: Dict[str, List[Tuple[str, str]]] = {}
        for repo_name, dm in self.registry.dep_maps.items():
            for file_path in dm.all_files:
                for sym in dm.get_file_symbols(file_path):
                    if sym.name.startswith("_"):
                        continue
                    if sym.name not in symbol_origins:
                        symbol_origins[sym.name] = []
                    symbol_origins[sym.name].append((repo_name, file_path))

        # Check each repo's imports against other repos' exports
        for repo_name, dm in self.registry.dep_maps.items():
            for file_path in dm.all_files:
                for imp in dm.get_file_imports(file_path):
                    for imported_name in imp.names:
                        if imported_name in symbol_origins:
                            for origin_repo, origin_file in symbol_origins[imported_name]:
                                if origin_repo != repo_name:
                                    edge = ExternalEdge(
                                        source_repo=repo_name,
                                        target_repo=origin_repo,
                                        symbol_name=imported_name,
                                        source_file=file_path,
                                        target_file=origin_file,
                                    )
                                    self.registry.cross_edges.append(edge)

        logger.info(
            "nexus_linked",
            cross_edges=len(self.registry.cross_edges),
        )

        return self.registry.cross_edges

    def get_dep_map(self, repo_name: str) -> Optional[DependencyMap]:
        """Get the DependencyMap for a specific repo."""
        return self.registry.dep_maps.get(repo_name)

    def summary(self) -> Dict[str, Any]:
        """Generate a comprehensive summary of the Nexus."""
        repos_list = []
        for name, info in self.registry.repos.items():
            repo_data = info.to_dict()
            repo_data["dependents"] = self.registry.get_repo_dependents(name)
            repo_data["dependencies"] = self.registry.get_repo_dependencies(name)
            repos_list.append(repo_data)

        high_risk = [
            e.to_dict() for e in self.registry.cross_edges
        ]

        return {
            "rootPath": str(self._root),
            "repoCount": self.repo_count,
            "totalFiles": self.registry.total_files,
            "totalSymbols": self.registry.total_symbols,
            "crossRepoEdges": self.registry.total_cross_edges,
            "repos": repos_list,
            "highRiskLinks": high_risk[:20],
        }

    # -- Internal ------------------------------------------------------------

    def _scan_dir(self, directory: Path, depth: int) -> None:
        """Recursively scan for repo markers."""
        if depth > self._max_depth:
            return
        if directory.name in _SKIP_DIRS:
            return

        markers = [m for m in _REPO_MARKERS if (directory / m).exists()]
        if markers and directory != self._root:
            name = directory.name
            info = RepoInfo(name=name, path=str(directory), markers=markers)
            self.registry.repos[name] = info
            return  # Don't recurse into sub-repos

        try:
            for child in sorted(directory.iterdir()):
                if child.is_dir() and child.name not in _SKIP_DIRS:
                    self._scan_dir(child, depth + 1)
        except PermissionError:
            pass

    def _index_repo(self, repo_name: str, info: RepoInfo) -> None:
        """Index a single repository."""
        t0 = time.time()
        indexer = SymbolIndexer()

        try:
            dm = indexer.index_workspace(info.path, use_cache=False)
        except Exception as exc:
            logger.warning("nexus_index_error", repo=repo_name, error=str(exc))
            return

        info.file_count = len(dm.all_files)
        info.symbol_count = sum(len(dm.get_file_symbols(f)) for f in dm.all_files)
        info.import_count = sum(len(dm.get_file_imports(f)) for f in dm.all_files)
        info.indexed = True
        info.index_duration_ms = (time.time() - t0) * 1000

        self.registry.dep_maps[repo_name] = dm

        logger.info(
            "nexus_repo_indexed",
            repo=repo_name,
            files=info.file_count,
            symbols=info.symbol_count,
            duration_ms=round(info.index_duration_ms, 1),
        )
