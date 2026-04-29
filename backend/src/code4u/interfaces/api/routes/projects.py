from __future__ import annotations
"""Project Management API — CRUD for indexed workspaces.

Endpoints:
  - POST /projects          — create a project (triggers background indexing)
  - GET  /projects          — list projects for the current tenant
  - GET  /projects/{id}     — get a single project with health score
  - DELETE /projects/{id}   — remove a project
  - POST /projects/{id}/index — re-index a project
"""

import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
import structlog

router = APIRouter()
logger = structlog.get_logger("api.projects")

# In-memory project store (swap for DB in production)
_projects: Dict[str, Dict[str, Any]] = {}


class CreateProjectRequest(BaseModel):
    name: str = Field(..., description="Project display name")
    path: str = Field(..., description="Absolute path to workspace root")
    description: str = Field("", description="Project description")
    repoUrl: str = Field("", description="Git remote URL (if cloned)")


class ProjectResponse(BaseModel):
    id: str
    name: str
    path: str
    description: str
    repoUrl: str
    tenantId: str
    status: str
    healthScore: int
    totalFiles: int
    totalSymbols: int
    languages: List[str]
    createdAt: float
    lastIndexedAt: float


def _index_workspace(path: str) -> Dict[str, Any]:
    """Run the SymbolIndexer on a workspace and return stats."""
    if not os.path.isdir(path):
        return {"totalFiles": 0, "totalSymbols": 0, "languages": [], "error": "not_found"}

    try:
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(path)
        stats = dep_map.stats

        langs = set()
        for sym_list in dep_map._symbols.values():
            for sym in sym_list:
                ext = os.path.splitext(sym.file_path)[1].lower()
                lang_map = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
                           ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go",
                           ".rs": "Rust", ".java": "Java", ".rb": "Ruby"}
                if ext in lang_map:
                    langs.add(lang_map[ext])

        return {
            "totalFiles": stats.get("indexed_files", 0),
            "totalSymbols": stats.get("total_symbols", 0),
            "languages": sorted(langs),
        }
    except Exception as e:
        logger.warning("index_failed", path=path, error=str(e))
        return {"totalFiles": 0, "totalSymbols": 0, "languages": [], "error": str(e)}


def _compute_health_score(path: str) -> int:
    """Compute a 0-100 health score using the Sentinel rules engine."""
    try:
        from code4u.agents.nexus.rules import RuleRegistry
        from code4u.agents.nexus.sentinel import Sentinel
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
            DependencyMap, SymbolIndexer,
        )

        indexer = SymbolIndexer()
        dm = indexer.index_workspace(path)
        registry = RuleRegistry()
        registry.load(path)
        sentinel = Sentinel(registry, dm)
        result = sentinel.scan_full()

        if result.files_scanned == 0:
            return 100

        violation_ratio = len(result.violations) / max(result.files_scanned, 1)
        score = max(0, int(100 - violation_ratio * 100))
        return min(score, 100)
    except Exception:
        return 85  # default healthy if sentinel unavailable


def _count_files(path: str) -> int:
    """Quick file count without full indexing."""
    if not os.path.isdir(path):
        return 0
    count = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "dist", "build", ".next", ".pytest_cache",
        }]
        count += len(files)
        if count > 10000:
            break
    return count


# ── POST /projects ────────────────────────────────────────────────

@router.post("/projects")
async def create_project(body: CreateProjectRequest, request: Request):
    """Create a project and trigger initial indexing.

    If ``repoUrl`` is provided and the path does not exist yet, the
    repository is cloned first using the GitManager.
    """
    tenant_id = getattr(request.state, "tenant_id", "local")
    user_id = getattr(request.state, "user_id", "")
    path = os.path.expanduser(body.path)

    clone_info: Optional[Dict[str, Any]] = None

    if body.repoUrl and not os.path.isdir(path):
        from code4u.core.filesystem.git_manager import GitManager
        from code4u.core.config import get_settings

        settings = get_settings()
        mgr = GitManager(base_dir=settings.repo_clone_base)

        gh_token = ""
        try:
            from code4u.interfaces.api.routes.auth import get_github_token
            gh_token = get_github_token(user_id) or ""
        except Exception:
            pass

        result = mgr.clone(body.repoUrl, token=gh_token)
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=f"Clone failed: {result.error}",
            )

        path = result.local_path
        clone_info = result.to_dict()
        logger.info("project_cloned", repo=body.repoUrl, path=path)

    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Directory not found: {body.path}")

    project_id = str(uuid.uuid4())[:12]

    index_result = _index_workspace(path)

    health = _compute_health_score(path)

    project = {
        "id": project_id,
        "name": body.name,
        "path": path,
        "description": body.description,
        "repoUrl": body.repoUrl,
        "tenantId": tenant_id,
        "status": "indexed",
        "healthScore": health,
        "totalFiles": index_result.get("totalFiles", 0),
        "totalSymbols": index_result.get("totalSymbols", 0),
        "languages": index_result.get("languages", []),
        "createdAt": time.time(),
        "lastIndexedAt": time.time(),
    }

    if clone_info:
        project["cloneInfo"] = clone_info

    _projects[project_id] = project
    logger.info("project_created", id=project_id, name=body.name, path=path)

    return project


# ── GET /projects ─────────────────────────────────────────────────

@router.get("/projects")
async def list_projects(request: Request):
    """List all projects for the current tenant."""
    tenant_id = getattr(request.state, "tenant_id", "local")

    items = [
        p for p in _projects.values()
        if p["tenantId"] == tenant_id or tenant_id == "local"
    ]
    items.sort(key=lambda p: p["createdAt"], reverse=True)

    return {
        "projects": items,
        "total": len(items),
    }


# ── GET /projects/health-summary ──────────────────────────────────
# Must be registered BEFORE the parameterized {project_id} route.

@router.get("/projects/health-summary")
async def projects_health_summary(request: Request):
    """Aggregate health metrics across all projects."""
    tenant_id = getattr(request.state, "tenant_id", "local")
    items = [
        p for p in _projects.values()
        if p["tenantId"] == tenant_id or tenant_id == "local"
    ]

    if not items:
        return {
            "projectCount": 0,
            "avgHealthScore": 0,
            "totalFiles": 0,
            "totalSymbols": 0,
            "languages": [],
        }

    total_files = sum(p["totalFiles"] for p in items)
    total_symbols = sum(p["totalSymbols"] for p in items)
    avg_health = round(sum(p["healthScore"] for p in items) / len(items))
    all_langs = set()
    for p in items:
        all_langs.update(p.get("languages", []))

    return {
        "projectCount": len(items),
        "avgHealthScore": avg_health,
        "totalFiles": total_files,
        "totalSymbols": total_symbols,
        "languages": sorted(all_langs),
    }


# ── GET /projects/{id} ───────────────────────────────────────────

@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a single project with full details."""
    project = _projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── DELETE /projects/{id} ─────────────────────────────────────────

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Remove a project from the registry."""
    if project_id not in _projects:
        raise HTTPException(status_code=404, detail="Project not found")
    del _projects[project_id]
    return {"deleted": True, "id": project_id}


# ── POST /projects/{id}/index ────────────────────────────────────

@router.post("/projects/{project_id}/index")
async def reindex_project(project_id: str):
    """Re-index a project's workspace."""
    project = _projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    index_result = _index_workspace(project["path"])
    health = _compute_health_score(project["path"])

    project["totalFiles"] = index_result.get("totalFiles", 0)
    project["totalSymbols"] = index_result.get("totalSymbols", 0)
    project["languages"] = index_result.get("languages", [])
    project["healthScore"] = health
    project["lastIndexedAt"] = time.time()
    project["status"] = "indexed"

    return project


# ── GET /projects/{id}/heatmap ──────────────────────────────────

@router.get("/projects/{project_id}/heatmap")
async def project_heatmap(project_id: str, max_files: int = Query(100)):
    """Return a complexity heatmap for the project's files.

    Each file entry includes line count, cyclomatic complexity,
    maintenance burden, and churn estimate.
    """
    import ast as _ast

    project = _projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    workspace = project["path"]
    if not os.path.isdir(workspace):
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        "dist", "build", ".next", ".pytest_cache", ".mypy_cache",
    }
    code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}

    entries: List[Dict[str, Any]] = []
    scanned = 0

    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in code_exts:
                continue
            if scanned >= max_files:
                break

            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, workspace)

            try:
                with open(fpath, "r", errors="ignore") as f:
                    source = f.read()
            except Exception:
                continue

            lines = source.count("\n") + 1
            if lines < 3:
                continue

            scanned += 1

            max_cc = 0
            avg_cc = 0.0
            fn_count = 0
            max_nesting = 0

            if ext == ".py":
                try:
                    tree = _ast.parse(source)
                    ccs = []
                    for node in _ast.walk(tree):
                        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                            cc = 1
                            for child in _ast.walk(node):
                                if isinstance(child, (_ast.If, _ast.While, _ast.For, _ast.ExceptHandler)):
                                    cc += 1
                                elif isinstance(child, _ast.BoolOp):
                                    cc += len(child.values) - 1
                            ccs.append(cc)
                            nd = _max_nesting(node)
                            max_nesting = max(max_nesting, nd)

                    fn_count = len(ccs)
                    max_cc = max(ccs) if ccs else 0
                    avg_cc = round(sum(ccs) / len(ccs), 1) if ccs else 0
                except SyntaxError:
                    pass

            burden = min(100, int(
                (lines / 500) * 20 +
                (max_cc / 15) * 40 +
                (max_nesting / 6) * 25 +
                (fn_count / 30) * 15
            ))

            entries.append({
                "filePath": rel,
                "lines": lines,
                "functions": fn_count,
                "maxComplexity": max_cc,
                "avgComplexity": avg_cc,
                "maxNesting": max_nesting,
                "maintenanceBurden": burden,
                "language": ext.lstrip("."),
            })
        if scanned >= max_files:
            break

    entries.sort(key=lambda e: e["maintenanceBurden"], reverse=True)

    return {
        "projectId": project_id,
        "projectName": project.get("name", ""),
        "files": entries,
        "scannedFiles": scanned,
        "avgBurden": round(sum(e["maintenanceBurden"] for e in entries) / max(len(entries), 1), 1),
    }


def _max_nesting(node: Any, depth: int = 0) -> int:
    """Compute max nesting depth inside a function AST node."""
    import ast as _ast
    max_d = depth
    nesting_types = (_ast.If, _ast.For, _ast.While, _ast.With, _ast.Try, _ast.ExceptHandler)
    for child in _ast.iter_child_nodes(node):
        if isinstance(child, nesting_types):
            max_d = max(max_d, _max_nesting(child, depth + 1))
        else:
            max_d = max(max_d, _max_nesting(child, depth))
    return max_d
