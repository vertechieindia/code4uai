"""Cross-Repo Impact Analyzer — blast radius across the Nexus.

Given a symbol name and the Nexus ``GlobalRegistry``, this agent
answers: "If I change this exported interface, which other
repositories need PRs?"

Usage::

    nexus = NexusContext("/microservices")
    nexus.scan(); nexus.index_all(); nexus.link_repos()

    analyzer = ImpactAnalyzer(nexus.registry)
    blast = analyzer.analyze("User")
    for repo in blast.affected_repos:
        print(repo.name, [f.path for f in repo.files])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

from code4u.core.nexus import GlobalRegistry, ExternalEdge

logger = structlog.get_logger("impact_analyzer")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AffectedFile:
    """A specific file affected by a cross-repo change."""
    path: str
    repo_name: str
    symbol_used: str
    import_line: str = ""
    usage_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "repoName": self.repo_name,
            "symbolUsed": self.symbol_used,
            "importLine": self.import_line,
            "usageCount": self.usage_count,
        }


@dataclass
class AffectedRepo:
    """A repository affected by a cross-repo change."""
    name: str
    path: str = ""
    files: List[AffectedFile] = field(default_factory=list)
    edge_count: int = 0
    severity: str = "medium"  # "low", "medium", "high", "critical"

    @property
    def file_count(self) -> int:
        return len(self.files)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "files": [f.to_dict() for f in self.files],
            "fileCount": self.file_count,
            "edgeCount": self.edge_count,
            "severity": self.severity,
        }


@dataclass
class BlastRadius:
    """Complete cross-repo blast radius for a symbol change."""
    symbol_name: str
    origin_repo: str = ""
    origin_file: str = ""
    affected_repos: List[AffectedRepo] = field(default_factory=list)
    total_files: int = 0
    total_repos: int = 0
    severity: str = "low"
    pr_plan: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbolName": self.symbol_name,
            "originRepo": self.origin_repo,
            "originFile": self.origin_file,
            "affectedRepos": [r.to_dict() for r in self.affected_repos],
            "totalFiles": self.total_files,
            "totalRepos": self.total_repos,
            "severity": self.severity,
            "prPlan": self.pr_plan,
        }


# ---------------------------------------------------------------------------
# ImpactAnalyzer
# ---------------------------------------------------------------------------

class ImpactAnalyzer:
    """Analyzes cross-repo blast radius using the GlobalRegistry.

    Usage::

        analyzer = ImpactAnalyzer(registry)
        blast = analyzer.analyze("UserModel")
    """

    def __init__(self, registry: GlobalRegistry) -> None:
        self._registry = registry

    def analyze(self, symbol_name: str) -> BlastRadius:
        """Calculate the full cross-repo blast radius for a symbol."""
        blast = BlastRadius(symbol_name=symbol_name)

        # Find where the symbol is defined
        origins = self._registry.find_symbol_global(symbol_name)
        if origins:
            blast.origin_repo = origins[0][0]
            blast.origin_file = origins[0][1].file_path

        # Find cross-repo edges
        edges = self._registry.get_cross_edges_for_symbol(symbol_name)
        if not edges:
            # Also check within-repo dependents for context
            blast.severity = "low"
            return blast

        # Group by affected repo
        repo_files: Dict[str, List[AffectedFile]] = {}
        for edge in edges:
            repo = edge.source_repo
            if repo not in repo_files:
                repo_files[repo] = []

            af = AffectedFile(
                path=edge.source_file,
                repo_name=repo,
                symbol_used=edge.symbol_name,
            )

            # Try to find the import line in the dep map
            dm = self._registry.dep_maps.get(repo)
            if dm:
                for imp in dm.get_file_imports(edge.source_file):
                    if symbol_name in imp.names:
                        af.import_line = f"from {imp.module} import {', '.join(imp.names)}"
                        break

            repo_files[repo].append(af)

        # Build AffectedRepo objects
        for repo_name, files in sorted(repo_files.items()):
            repo_info = self._registry.repos.get(repo_name)
            edge_count = len(files)
            severity = self._classify_severity(edge_count)

            ar = AffectedRepo(
                name=repo_name,
                path=repo_info.path if repo_info else "",
                files=files,
                edge_count=edge_count,
                severity=severity,
            )
            blast.affected_repos.append(ar)

        blast.total_repos = len(blast.affected_repos)
        blast.total_files = sum(r.file_count for r in blast.affected_repos)
        blast.severity = self._overall_severity(blast.affected_repos)

        # Generate PR plan
        blast.pr_plan = self._generate_pr_plan(blast)

        logger.info(
            "blast_radius_analyzed",
            symbol=symbol_name,
            repos=blast.total_repos,
            files=blast.total_files,
            severity=blast.severity,
        )

        return blast

    def analyze_repo(self, repo_name: str) -> List[BlastRadius]:
        """Analyze all exported symbols from a repo that are used cross-repo."""
        results = []
        seen_symbols: set = set()

        for edge in self._registry.cross_edges:
            if edge.target_repo == repo_name and edge.symbol_name not in seen_symbols:
                seen_symbols.add(edge.symbol_name)
                blast = self.analyze(edge.symbol_name)
                if blast.total_repos > 0:
                    results.append(blast)

        return results

    def high_risk_symbols(self, min_repos: int = 2) -> List[BlastRadius]:
        """Find symbols that affect multiple repos (high-risk)."""
        symbol_repos: Dict[str, set] = {}
        for edge in self._registry.cross_edges:
            if edge.symbol_name not in symbol_repos:
                symbol_repos[edge.symbol_name] = set()
            symbol_repos[edge.symbol_name].add(edge.source_repo)

        results = []
        for sym, repos in sorted(symbol_repos.items(), key=lambda x: len(x[1]), reverse=True):
            if len(repos) >= min_repos:
                blast = self.analyze(sym)
                results.append(blast)

        return results

    # -- Internal ------------------------------------------------------------

    @staticmethod
    def _classify_severity(edge_count: int) -> str:
        if edge_count >= 10:
            return "critical"
        if edge_count >= 5:
            return "high"
        if edge_count >= 2:
            return "medium"
        return "low"

    @staticmethod
    def _overall_severity(repos: List[AffectedRepo]) -> str:
        if not repos:
            return "low"
        severities = [r.severity for r in repos]
        if "critical" in severities:
            return "critical"
        if "high" in severities:
            return "high"
        if len(repos) >= 3:
            return "high"
        if "medium" in severities:
            return "medium"
        return "low"

    @staticmethod
    def _generate_pr_plan(blast: BlastRadius) -> List[Dict[str, Any]]:
        """Generate a multi-PR plan for breaking changes."""
        plan = []
        for repo in blast.affected_repos:
            pr = {
                "repo": repo.name,
                "title": f"Update {blast.symbol_name} usage after API change",
                "files": [f.path for f in repo.files],
                "fileCount": repo.file_count,
                "priority": {"critical": 1, "high": 2, "medium": 3, "low": 4}.get(repo.severity, 3),
            }
            plan.append(pr)

        plan.sort(key=lambda x: x["priority"])
        return plan
