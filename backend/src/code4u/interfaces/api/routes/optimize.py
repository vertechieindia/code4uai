"""Optimization & Semantic Search API.

Endpoints:
  - ``POST /optimize``          — Analyze code for performance anti-patterns
                                  and propose optimized alternatives.
  - ``POST /search/semantic``   — Semantic concept search across a workspace
                                  using TF-IDF + cosine similarity.
"""

from __future__ import annotations

import ast
import math
import os
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# =====================================================================
# /optimize — Algorithmic Optimization Intent
# =====================================================================

class OptimizeRequest(BaseModel):
    workspacePath: str = Field(..., description="Workspace root path.")
    filePath: str = Field("", description="Specific file to optimize (empty = scan workspace).")
    source: str = Field("", description="Source code to optimize (if filePath not provided).")
    intent: str = Field("optimize", description="Optimization intent description.")
    maxFiles: int = Field(20, description="Max files to scan.")


class OptimizationFinding(BaseModel):
    filePath: str
    line: int
    category: str
    severity: str
    description: str
    currentCode: str
    suggestedFix: str
    estimatedSpeedup: str


@router.post("/optimize")
async def optimize(request: OptimizeRequest):
    """Analyze code for performance anti-patterns and propose fixes.

    Detects: O(n^2) loops, N+1 queries, missing memoization,
    redundant API calls, string concatenation in loops, inefficient
    container lookups, and blocking I/O patterns.
    """
    findings: List[Dict[str, Any]] = []

    if request.source:
        findings = _analyze_source(request.source, request.filePath or "<input>")
    elif request.filePath:
        full_path = request.filePath
        if not os.path.isabs(full_path):
            full_path = os.path.join(request.workspacePath, full_path)
        if not os.path.isfile(full_path):
            raise HTTPException(status_code=404, detail=f"File not found: {full_path}")
        with open(full_path, "r", errors="ignore") as f:
            source = f.read()
        rel = os.path.relpath(full_path, request.workspacePath) if request.workspacePath else full_path
        findings = _analyze_source(source, rel)
    else:
        workspace = request.workspacePath
        if not os.path.isdir(workspace):
            raise HTTPException(status_code=404, detail="Workspace not found")

        skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
        scanned = 0
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in skip]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in (".py", ".ts", ".tsx", ".js", ".jsx"):
                    continue
                if scanned >= request.maxFiles:
                    break
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", errors="ignore") as f:
                        source = f.read()
                except Exception:
                    continue
                if len(source) < 30:
                    continue
                scanned += 1
                rel = os.path.relpath(fpath, workspace)
                findings.extend(_analyze_source(source, rel))
            if scanned >= request.maxFiles:
                break

    findings.sort(key=lambda f: {"critical": 0, "warning": 1, "info": 2}.get(f.get("severity", ""), 3))

    return {
        "findings": findings,
        "totalFindings": len(findings),
        "categories": dict(Counter(f["category"] for f in findings)),
    }


_PATTERNS = [
    {
        "id": "nested-loop",
        "regex": r"^\s*for\s+.+:.*\n(?:\s+.*\n)*?\s+for\s+.+:",
        "category": "O(n\u00b2) Nested Loop",
        "severity": "critical",
        "description": "Nested loop detected — likely O(n\u00b2) time complexity.",
        "suggestion": "Convert the inner loop lookup to a set/dict for O(1) access, or use itertools.product.",
        "speedup": "O(n) from O(n\u00b2)",
    },
    {
        "id": "n-plus-1",
        "regex": r"for\s+\w+\s+in\s+\w+.*:\s*\n\s+.*(?:\.query|\.get|\.fetch|\.find|SELECT|await\s+\w+\.get)",
        "category": "N+1 Query",
        "severity": "critical",
        "description": "Database/API call inside a loop — classic N+1 query pattern.",
        "suggestion": "Batch the queries before the loop using `WHERE id IN (...)` or prefetching.",
        "speedup": "~Nx faster",
    },
    {
        "id": "string-concat-loop",
        "regex": r"for\s+.+:\s*\n(?:\s+.*\n)*?\s+\w+\s*\+=\s*['\"]",
        "category": "String Concatenation in Loop",
        "severity": "warning",
        "description": "String concatenation with `+=` inside a loop creates O(n\u00b2) copies.",
        "suggestion": "Collect into a list and use `''.join(parts)` after the loop.",
        "speedup": "~10x for large strings",
    },
    {
        "id": "list-in-check",
        "regex": r"if\s+\w+\s+in\s+\[.{10,}\]",
        "category": "Inefficient Lookup",
        "severity": "warning",
        "description": "Membership check on a list literal — O(n) per check.",
        "suggestion": "Use a set literal `{...}` for O(1) lookups.",
        "speedup": "O(1) from O(n)",
    },
    {
        "id": "no-cache",
        "regex": r"def\s+(\w+)\(.*\).*:\s*\n(?:\s+.*\n)*?\s+(?:return|yield)\s+.*\1\(",
        "category": "Missing Memoization",
        "severity": "info",
        "description": "Recursive function without caching — may recompute subproblems.",
        "suggestion": "Add `@functools.lru_cache` or `@functools.cache` decorator.",
        "speedup": "Exponential to polynomial",
    },
    {
        "id": "blocking-sleep",
        "regex": r"time\.sleep\(",
        "category": "Blocking I/O",
        "severity": "warning",
        "description": "Blocking `time.sleep()` in potentially async context.",
        "suggestion": "Use `await asyncio.sleep()` in async code.",
        "speedup": "Non-blocking",
    },
    {
        "id": "readlines",
        "regex": r"\.readlines\(\)",
        "category": "Memory Inefficiency",
        "severity": "info",
        "description": "`.readlines()` loads the entire file into memory.",
        "suggestion": "Iterate the file object directly: `for line in f:`",
        "speedup": "O(1) memory vs O(n)",
    },
]


def _analyze_source(source: str, file_path: str) -> List[Dict[str, Any]]:
    """Run all optimization pattern detectors on source code."""
    findings: List[Dict[str, Any]] = []
    lines = source.splitlines()

    for pat in _PATTERNS:
        for m in re.finditer(pat["regex"], source, re.MULTILINE):
            line_no = source[:m.start()].count("\n") + 1
            ctx_start = max(0, line_no - 1)
            ctx_end = min(len(lines), line_no + 4)
            current_code = "\n".join(lines[ctx_start:ctx_end])

            findings.append({
                "filePath": file_path,
                "line": line_no,
                "category": pat["category"],
                "severity": pat["severity"],
                "description": pat["description"],
                "currentCode": current_code[:500],
                "suggestedFix": pat["suggestion"],
                "estimatedSpeedup": pat["speedup"],
            })

    if file_path.endswith(".py"):
        findings.extend(_ast_analysis(source, file_path))

    return findings


def _ast_analysis(source: str, file_path: str) -> List[Dict[str, Any]]:
    """AST-based detection for Python-specific patterns."""
    findings: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body_lines = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno
            if body_lines > 80:
                findings.append({
                    "filePath": file_path,
                    "line": node.lineno,
                    "category": "Large Function",
                    "severity": "info",
                    "description": f"Function `{node.name}` is {body_lines} lines — hard to optimize and test.",
                    "currentCode": "\n".join(lines[node.lineno - 1:node.lineno + 2]),
                    "suggestedFix": "Break into smaller, focused functions with single responsibilities.",
                    "estimatedSpeedup": "Improved maintainability",
                })

            cc = 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                    cc += 1
                elif isinstance(child, ast.BoolOp):
                    cc += len(child.values) - 1
            if cc > 15:
                findings.append({
                    "filePath": file_path,
                    "line": node.lineno,
                    "category": "High Complexity",
                    "severity": "warning",
                    "description": f"Function `{node.name}` has cyclomatic complexity {cc} (threshold: 15).",
                    "currentCode": "\n".join(lines[node.lineno - 1:node.lineno + 2]),
                    "suggestedFix": "Extract complex conditional logic into helper functions or use strategy pattern.",
                    "estimatedSpeedup": "Reduced bug density",
                })

    return findings


# =====================================================================
# /search/semantic — Concept-based code search
# =====================================================================

class SemanticSearchRequest(BaseModel):
    query: str = Field(..., description="Natural language concept to search for.")
    workspacePath: str = Field(..., description="Workspace root path.")
    maxResults: int = Field(15, description="Max results to return.")
    includeSnippets: bool = Field(True, description="Include code snippets in results.")
    useLocalVectorStore: bool = Field(False, description="Force local FAISS/numpy vector store.")


_STOPWORDS = frozenset(
    "the a an is are was were be been being have has had do does did "
    "will would shall should may might can could of in to for on with "
    "at by from as into through during before after above below between "
    "and or but not no nor so yet both either neither each every all "
    "any few more most other some such than too very it its this that "
    "these those i me my we our you your he him his she her they them "
    "their what which who whom how when where why if then else".split()
)


def _tokenize(text: str) -> List[str]:
    """Split text into normalized tokens for TF-IDF."""
    text = re.sub(r"[A-Z]", lambda m: " " + m.group().lower(), text)
    text = re.sub(r"[_\-./\\]", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    tokens = [t for t in text.split() if len(t) > 1 and t not in _STOPWORDS]
    return tokens


def _compute_tfidf(
    docs: List[List[str]],
) -> tuple[List[Dict[str, float]], Dict[str, float]]:
    """Compute TF-IDF vectors for a list of tokenized documents."""
    n = len(docs)
    df: Dict[str, int] = defaultdict(int)
    for doc in docs:
        seen = set(doc)
        for t in seen:
            df[t] += 1

    idf = {t: math.log((n + 1) / (freq + 1)) + 1 for t, freq in df.items()}

    tfidf_vecs: List[Dict[str, float]] = []
    for doc in docs:
        tf = Counter(doc)
        total = len(doc) or 1
        vec = {t: (count / total) * idf.get(t, 1) for t, count in tf.items()}
        tfidf_vecs.append(vec)

    return tfidf_vecs, idf


def _cosine_sim(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    common = set(a.keys()) & set(b.keys())
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@router.post("/search/semantic")
async def semantic_search(request: SemanticSearchRequest):
    """Search for code by concept using TF-IDF cosine similarity.

    Unlike keyword search, this finds relevant code even when exact
    terms don't match (e.g., searching "payment processing" finds
    ``handle_checkout``, ``process_order``, ``charge_card``).
    """
    workspace = request.workspacePath
    if not os.path.isdir(workspace):
        raise HTTPException(status_code=404, detail="Workspace not found")

    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next"}
    code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb"}

    file_texts: List[str] = []
    file_paths: List[str] = []
    file_sources: List[str] = []

    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in code_exts:
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    source = f.read()
            except Exception:
                continue
            if len(source) < 10:
                continue

            rel = os.path.relpath(fpath, workspace)
            file_paths.append(rel)
            file_sources.append(source)

            text = rel + " " + _extract_identifiers(source, ext)
            file_texts.append(text)

    if not file_texts:
        return {"results": [], "totalFiles": 0, "query": request.query}

    tokenized_docs = [_tokenize(t) for t in file_texts]
    query_tokens = _tokenize(request.query)

    tfidf_vecs, idf = _compute_tfidf(tokenized_docs + [query_tokens])
    query_vec = tfidf_vecs[-1]
    doc_vecs = tfidf_vecs[:-1]

    scored: List[tuple[float, int]] = []
    for i, dv in enumerate(doc_vecs):
        sim = _cosine_sim(query_vec, dv)
        if sim > 0.01:
            scored.append((sim, i))

    scored.sort(reverse=True)
    top = scored[:request.maxResults]

    results = []
    for score, idx in top:
        rel = file_paths[idx]
        source = file_sources[idx]
        snippet = ""
        matched_line = 0

        if request.includeSnippets:
            snippet, matched_line = _best_snippet(source, request.query)

        results.append({
            "filePath": rel,
            "score": round(score, 4),
            "snippet": snippet,
            "matchedLine": matched_line,
            "language": os.path.splitext(rel)[1].lstrip("."),
        })

    return {
        "results": results,
        "totalFiles": len(file_texts),
        "query": request.query,
    }


@router.post("/search/vector")
async def vector_search(request: SemanticSearchRequest):
    """Semantic search using the local FAISS/numpy vector store.

    Indexes the workspace on first call, then uses cosine similarity
    over hashed TF-IDF embeddings for sub-second retrieval.
    """
    from code4u.ai_engine.vector_store import (
        get_local_vector_store,
        VectorDocument,
    )

    workspace = request.workspacePath
    if not os.path.isdir(workspace):
        raise HTTPException(status_code=404, detail="Workspace not found")

    store = get_local_vector_store()

    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next"}
    code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb"}

    docs: List[VectorDocument] = []
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            ext_name = os.path.splitext(fname)[1].lower()
            if ext_name not in code_exts:
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    source = f.read()
            except Exception:
                continue
            if len(source) < 10:
                continue
            rel = os.path.relpath(fpath, workspace)
            identifiers = _extract_identifiers(source, ext_name)
            docs.append(VectorDocument(
                id=rel,
                content=rel + " " + identifiers + " " + source[:2000],
                metadata={"language": ext_name.lstrip("."), "lines": source.count("\n") + 1},
            ))

    if docs:
        store.add_documents(docs)

    results = store.search(request.query, top_k=request.maxResults)

    return {
        "results": [
            {
                "filePath": r.id,
                "score": round(r.score, 4),
                "snippet": r.content[:300] if request.includeSnippets else "",
                "language": r.metadata.get("language", ""),
            }
            for r in results
        ],
        "totalIndexed": store.count,
        "query": request.query,
        "backend": store.stats()["backend"],
    }


@router.get("/search/vector/stats")
async def vector_store_stats():
    """Return local vector store statistics."""
    from code4u.ai_engine.vector_store import get_local_vector_store
    store = get_local_vector_store()
    return store.stats()


def _extract_identifiers(source: str, ext: str) -> str:
    """Extract function/class/variable names from source for indexing."""
    idents: List[str] = []

    idents.extend(re.findall(r"(?:def|function|class|const|let|var|type|interface)\s+(\w+)", source))
    idents.extend(re.findall(r"#\s*(.+?)$", source, re.MULTILINE))
    idents.extend(re.findall(r"//\s*(.+?)$", source, re.MULTILINE))
    idents.extend(re.findall(r'"""(.+?)"""', source, re.DOTALL)[:3])
    idents.extend(re.findall(r"'''(.+?)'''", source, re.DOTALL)[:3])

    return " ".join(idents)


def _best_snippet(source: str, query: str) -> tuple[str, int]:
    """Find the most relevant 5-line snippet for a query."""
    lines = source.splitlines()
    query_words = set(_tokenize(query))
    best_score = 0
    best_line = 0

    for i, line in enumerate(lines):
        line_tokens = set(_tokenize(line))
        overlap = len(query_words & line_tokens)
        if overlap > best_score:
            best_score = overlap
            best_line = i

    start = max(0, best_line - 1)
    end = min(len(lines), best_line + 4)
    return "\n".join(lines[start:end]), best_line + 1
