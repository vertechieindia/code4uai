"""Graph-Augmented Context Retriever.

Given a user query, identifies relevant "Entry Point" symbols in the
``DependencyMap`` and performs multi-hop graph traversal to build
a rich context that includes upstream dependencies and downstream
callers.

Unlike standard RAG (keyword grep), this retriever *thinks in
nodes and edges*.  It answers questions like "Where is the auth
logic and what will break if I change it?" by traversing the
dependency graph rather than just matching text.

Retrieval strategy:
  1. **Keyword extraction** — tokenize the query into candidate
     symbol names using word-boundary splitting, camelCase/snake_case
     decomposition, and common programming term matching.
  2. **Symbol matching** — rank every symbol in the DependencyMap by
     relevance to the extracted keywords (fuzzy string similarity).
  3. **Graph traversal** — from each matched symbol, perform an
     N-hop BFS (default 2) to pull in upstream dependencies and
     downstream callers.
  4. **Deduplication & ranking** — deduplicate files, rank by
     relevance (direct match > 1-hop > 2-hop), and return the
     ordered context set.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

logger = structlog.get_logger("retriever")


@dataclass
class SymbolMatch:
    """A symbol that matched the user's query."""
    name: str
    kind: str
    file_path: str
    score: float
    start_line: int = 0
    end_line: int = 0


@dataclass
class GraphNode:
    """A file node discovered via graph traversal."""
    file_path: str
    symbols: List[str]
    hop_distance: int
    relevance: float = 0.0
    relationship: str = "related"  # "entry_point", "upstream", "downstream", "transitive"


@dataclass
class RetrievedContext:
    """The full context retrieved for a query."""
    query: str
    entry_points: List[SymbolMatch] = field(default_factory=list)
    graph_nodes: List[GraphNode] = field(default_factory=list)
    file_order: List[str] = field(default_factory=list)
    total_symbols: int = 0
    total_files: int = 0
    hops_performed: int = 0
    bottleneck_files: List[str] = field(default_factory=list)
    cycles_detected: List[List[str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "entryPoints": [
                {"name": ep.name, "kind": ep.kind, "file": ep.file_path, "score": ep.score}
                for ep in self.entry_points
            ],
            "graphNodes": [
                {
                    "file": gn.file_path,
                    "symbols": gn.symbols,
                    "hopDistance": gn.hop_distance,
                    "relationship": gn.relationship,
                }
                for gn in self.graph_nodes
            ],
            "fileOrder": self.file_order,
            "totalSymbols": self.total_symbols,
            "totalFiles": self.total_files,
            "hopsPerformed": self.hops_performed,
            "bottleneckFiles": self.bottleneck_files,
        }


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "must", "need", "dare",
    "and", "but", "or", "nor", "not", "no", "so", "yet", "for", "of",
    "in", "on", "at", "to", "by", "up", "out", "off", "over", "from",
    "into", "with", "about", "between", "through", "during", "before",
    "after", "above", "below", "it", "its", "this", "that", "these",
    "those", "my", "your", "his", "her", "our", "their", "what", "which",
    "who", "whom", "how", "where", "when", "why", "if", "then", "else",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "only", "same", "than", "too", "very",
})

_CODE_KEYWORDS = frozenset({
    "function", "class", "method", "module", "file", "import", "export",
    "variable", "constant", "interface", "type", "enum", "struct",
    "service", "controller", "handler", "route", "api", "endpoint",
    "model", "schema", "database", "query", "mutation", "resolver",
    "component", "hook", "provider", "context", "store", "reducer",
    "middleware", "decorator", "wrapper", "factory", "builder",
    "test", "spec", "fixture", "mock", "stub",
})


def extract_keywords(query: str) -> List[str]:
    """Extract candidate symbol-name keywords from a natural language query.

    Handles camelCase, PascalCase, snake_case, and kebab-case.
    """
    tokens: List[str] = []

    # Split camelCase/PascalCase
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|[a-z_]+|\w+", query)
    for w in words:
        lower = w.lower().strip("_")
        if lower and lower not in _STOP_WORDS and len(lower) > 1:
            tokens.append(lower)

    # Also extract full compound identifiers (snake_case, camelCase)
    compounds = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", query)
    for c in compounds:
        if len(c) > 2 and c.lower() not in _STOP_WORDS:
            tokens.append(c.lower())

    return list(dict.fromkeys(tokens))


def _score_symbol(symbol_name: str, keywords: List[str]) -> float:
    """Score a symbol against a set of keywords.

    Exact match = 1.0, substring match = 0.6, component match = 0.3.
    """
    name_lower = symbol_name.lower()
    # Decompose the symbol into parts
    name_parts = set(re.findall(r"[a-z]+", name_lower))

    best_score = 0.0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower == name_lower:
            best_score = max(best_score, 1.0)
        elif kw_lower in name_lower or name_lower in kw_lower:
            best_score = max(best_score, 0.6)
        elif kw_lower in name_parts:
            best_score = max(best_score, 0.3)

    return best_score


# ---------------------------------------------------------------------------
# ContextRetriever
# ---------------------------------------------------------------------------

class ContextRetriever:
    """Retrieves graph-augmented context for a code chat query.

    Uses the ``DependencyMap`` to traverse relationships instead of
    just grepping for text — this is what makes it "Graph-Augmented."
    """

    def __init__(
        self,
        dep_map: Any,
        *,
        max_entry_points: int = 5,
        max_hops: int = 2,
        max_files: int = 20,
    ) -> None:
        self._dep_map = dep_map
        self._max_entry = max_entry_points
        self._max_hops = max_hops
        self._max_files = max_files

    def retrieve(self, query: str) -> RetrievedContext:
        """Run the full retrieval pipeline for a query.

        1. Extract keywords from the query.
        2. Score and rank all symbols.
        3. Graph-traverse from top matches.
        4. Identify bottleneck modules.
        5. Return ordered context.
        """
        ctx = RetrievedContext(query=query)
        keywords = extract_keywords(query)

        if not keywords:
            return ctx

        # Step 1: Score all symbols
        scored: List[SymbolMatch] = []
        seen_names: Set[str] = set()

        for sym_name in self._all_symbol_names():
            if sym_name in seen_names:
                continue
            seen_names.add(sym_name)

            score = _score_symbol(sym_name, keywords)
            if score < 0.1:
                continue

            defs = self._dep_map.get_symbol_defs(sym_name)
            for sd in defs:
                scored.append(SymbolMatch(
                    name=sd.name,
                    kind=sd.kind,
                    file_path=sd.file_path,
                    score=score,
                    start_line=sd.start_line,
                    end_line=sd.end_line,
                ))

        scored.sort(key=lambda s: s.score, reverse=True)
        ctx.entry_points = scored[: self._max_entry]

        if not ctx.entry_points:
            return ctx

        # Step 2: Multi-hop graph traversal from entry points
        file_scores: Dict[str, float] = {}
        file_hops: Dict[str, int] = {}
        file_relationships: Dict[str, str] = {}
        file_symbols: Dict[str, Set[str]] = defaultdict(set)

        for ep in ctx.entry_points:
            fp = ep.file_path
            file_scores[fp] = max(file_scores.get(fp, 0), ep.score)
            file_hops[fp] = 0
            file_relationships[fp] = "entry_point"
            file_symbols[fp].add(ep.name)

            # BFS traversal
            frontier: Set[str] = set()

            # Downstream: files that import this symbol
            for dep in self._dep_map.get_dependents(ep.name):
                frontier.add(dep)
                if dep not in file_hops or file_hops[dep] > 1:
                    file_hops[dep] = 1
                    file_relationships[dep] = "downstream"
                file_scores[dep] = max(file_scores.get(dep, 0), ep.score * 0.7)

            # Upstream: files that this file imports from
            for imp in self._dep_map.get_file_imports(fp):
                for name in imp.names:
                    for sd in self._dep_map.get_symbol_defs(name):
                        upstream_fp = sd.file_path
                        if upstream_fp != fp:
                            frontier.add(upstream_fp)
                            if upstream_fp not in file_hops or file_hops[upstream_fp] > 1:
                                file_hops[upstream_fp] = 1
                                file_relationships[upstream_fp] = "upstream"
                            file_scores[upstream_fp] = max(
                                file_scores.get(upstream_fp, 0), ep.score * 0.7,
                            )
                            file_symbols[upstream_fp].add(name)

            # Hop 2: traverse from hop-1 files
            if self._max_hops >= 2:
                hop2_frontier: Set[str] = set()
                for hop1_fp in frontier:
                    for sym in self._dep_map.get_file_symbols(hop1_fp):
                        file_symbols[hop1_fp].add(sym.name)
                        for dep2 in self._dep_map.get_dependents(sym.name):
                            if dep2 not in file_hops:
                                hop2_frontier.add(dep2)
                                file_hops[dep2] = 2
                                file_relationships[dep2] = "transitive"
                                file_scores[dep2] = max(
                                    file_scores.get(dep2, 0), ep.score * 0.4,
                                )

        # Populate file_symbols for discovered files
        for fp in file_hops:
            if fp not in file_symbols or not file_symbols[fp]:
                for sym in self._dep_map.get_file_symbols(fp):
                    file_symbols[fp].add(sym.name)

        # Step 3: Rank and order files
        ranked_files = sorted(
            file_hops.keys(),
            key=lambda fp: (-file_scores.get(fp, 0), file_hops.get(fp, 99)),
        )
        ranked_files = ranked_files[: self._max_files]

        ctx.graph_nodes = [
            GraphNode(
                file_path=fp,
                symbols=sorted(file_symbols.get(fp, set())),
                hop_distance=file_hops.get(fp, 0),
                relevance=file_scores.get(fp, 0),
                relationship=file_relationships.get(fp, "related"),
            )
            for fp in ranked_files
        ]

        ctx.file_order = ranked_files
        ctx.total_files = len(ranked_files)
        ctx.total_symbols = sum(len(gn.symbols) for gn in ctx.graph_nodes)
        ctx.hops_performed = self._max_hops

        # Step 4: Identify bottleneck files (most dependents)
        dep_counts: Dict[str, int] = {}
        for fp in ranked_files:
            count = 0
            for sym in self._dep_map.get_file_symbols(fp):
                count += len(self._dep_map.get_dependents(sym.name))
            dep_counts[fp] = count

        bottleneck_threshold = max(dep_counts.values()) * 0.7 if dep_counts else 0
        ctx.bottleneck_files = [
            fp for fp, c in dep_counts.items()
            if c >= max(bottleneck_threshold, 2)
        ]

        logger.info(
            "context_retrieved",
            query_len=len(query),
            keywords=len(keywords),
            entry_points=len(ctx.entry_points),
            files=ctx.total_files,
            symbols=ctx.total_symbols,
            bottlenecks=len(ctx.bottleneck_files),
        )

        return ctx

    def _all_symbol_names(self) -> List[str]:
        """Return all unique symbol names from the DependencyMap."""
        if hasattr(self._dep_map, "_symbols"):
            return list(self._dep_map._symbols.keys())
        return []
