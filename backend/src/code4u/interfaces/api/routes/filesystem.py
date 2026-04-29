from __future__ import annotations
"""File system API — real directory listing and file content for the IDE.

Endpoints:
  - GET  /projects/files?path=...  — recursive directory tree
  - GET  /files/content?path=...   — raw file content
  - POST /files/save               — save file content to disk
  - POST /terminal/exec            — execute a shell command and return output
  - GET  /symbols/definitions?path=...&file=... — symbol index for a file
"""
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import structlog

router = APIRouter()
logger = structlog.get_logger("api.filesystem")

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "dist", "build", ".next", ".nuxt", ".vscode", ".idea",
    "venv", ".venv", "env", ".env", ".code4u_cache", ".tox", "coverage",
    "htmlcov", ".eggs", "*.egg-info",
}

IGNORED_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".o", ".class", ".jar",
    ".lock", ".DS_Store",
}

MAX_FILE_SIZE = 1_000_000  # 1 MB


def _should_ignore(name: str) -> bool:
    if name.startswith(".") and name not in (".env.example",):
        return True
    if name in IGNORED_DIRS:
        return True
    _, ext = os.path.splitext(name)
    return ext in IGNORED_EXTENSIONS


def _build_tree(root: str, rel: str = "", depth: int = 0, max_depth: int = 6) -> List[Dict[str, Any]]:
    """Recursively build a JSON file tree from the filesystem."""
    if depth > max_depth:
        return []

    abs_path = os.path.join(root, rel) if rel else root
    if not os.path.isdir(abs_path):
        return []

    entries: List[Dict[str, Any]] = []
    try:
        items = sorted(os.listdir(abs_path), key=lambda n: (not os.path.isdir(os.path.join(abs_path, n)), n.lower()))
    except PermissionError:
        return []

    for name in items:
        if _should_ignore(name):
            continue
        full = os.path.join(abs_path, name)
        child_rel = os.path.join(rel, name) if rel else name

        if os.path.isdir(full):
            children = _build_tree(root, child_rel, depth + 1, max_depth)
            entries.append({
                "name": name,
                "type": "folder",
                "path": child_rel,
                "children": children,
            })
        else:
            lang = _detect_language(name)
            entries.append({
                "name": name,
                "type": "file",
                "path": child_rel,
                "language": lang,
            })

    return entries


def _detect_language(filename: str) -> str:
    ext_map = {
        ".py": "python", ".pyi": "python",
        ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript",
        ".json": "json",
        ".yaml": "yaml", ".yml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".css": "css", ".scss": "scss",
        ".html": "html",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
        ".sh": "shell", ".bash": "shell",
        ".sql": "sql",
        ".xml": "xml",
        ".dockerfile": "dockerfile",
    }
    _, ext = os.path.splitext(filename.lower())
    if filename.lower() == "dockerfile":
        return "dockerfile"
    return ext_map.get(ext, "plaintext")


# ── GET /projects/files ──────────────────────────────────────────

@router.get("/projects/files")
async def list_files(
    path: str = Query(..., description="Absolute path to the workspace root"),
    max_depth: int = Query(6, ge=1, le=10),
):
    """Return the recursive directory tree of a workspace."""
    root = os.path.expanduser(path)
    if not os.path.isdir(root):
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")

    tree = _build_tree(root, max_depth=max_depth)
    return {
        "root": root,
        "tree": tree,
    }


# ── GET /files/content ───────────────────────────────────────────

@router.get("/files/content")
async def read_file(
    path: str = Query(..., description="Absolute path to the file"),
):
    """Return the raw text content of a file."""
    full = os.path.expanduser(path)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    size = os.path.getsize(full)
    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large ({size} bytes, max {MAX_FILE_SIZE})")

    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    lang = _detect_language(os.path.basename(full))
    return {
        "path": full,
        "content": content,
        "language": lang,
        "size": size,
    }


# ── POST /files/save ─────────────────────────────────────────────

class SaveFileRequest(BaseModel):
    path: str = Field(..., description="Absolute path to save")
    content: str = Field(..., description="File content")

@router.post("/files/save")
async def save_file(body: SaveFileRequest):
    """Write content to a file on disk."""
    full = os.path.expanduser(body.path)
    try:
        with open(full, "w", encoding="utf-8") as f:
            f.write(body.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"saved": True, "path": full, "size": len(body.content)}


# ── POST /terminal/exec ──────────────────────────────────────────

class TerminalExecRequest(BaseModel):
    command: str = Field(..., description="Shell command to execute")
    cwd: str = Field(".", description="Working directory")

@router.post("/terminal/exec")
async def terminal_exec(body: TerminalExecRequest):
    """Execute a shell command and return stdout/stderr."""
    cwd = os.path.expanduser(body.cwd)
    if not os.path.isdir(cwd):
        raise HTTPException(status_code=404, detail=f"Directory not found: {body.cwd}")

    try:
        result = subprocess.run(
            body.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=cwd,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exitCode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Command timed out (15s limit)", "exitCode": 124}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /symbols/definitions ─────────────────────────────────────

@router.get("/symbols/definitions")
async def get_symbols(
    workspace: str = Query(..., description="Workspace root path"),
    file: str = Query("", description="Filter to a specific file (relative path)"),
):
    """Return symbols indexed by the Knowledge Graph for a workspace or file."""
    root = os.path.expanduser(workspace)
    if not os.path.isdir(root):
        raise HTTPException(status_code=404, detail=f"Directory not found: {workspace}")

    try:
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(root)
    except Exception as e:
        logger.warning("symbol_index_failed", error=str(e))
        return {"symbols": [], "error": str(e)}

    symbols = []
    all_syms = []
    for sym_list in dep_map._symbols.values():
        all_syms.extend(sym_list)

    for sym in all_syms:
        if file and not sym.file_path.endswith(file):
            continue
        symbols.append({
            "name": sym.name,
            "kind": sym.kind,
            "file": sym.file_path,
            "startLine": sym.start_line,
            "endLine": getattr(sym, "end_line", sym.start_line),
            "docstring": getattr(sym, "docstring", ""),
        })

    stats = dep_map.stats
    return {
        "workspace": root,
        "symbols": symbols,
        "totalFiles": stats.get("indexed_files", 0),
        "totalSymbols": stats.get("total_symbols", 0),
    }


# ── GET /symbols/goto — Go to Definition ──────────────────────

@router.get("/symbols/goto")
async def goto_definition(
    workspace: str = Query(..., description="Workspace root path"),
    symbol: str = Query(..., description="Symbol name to find"),
    fromFile: str = Query("", description="File the symbol was referenced from"),
):
    """Find the definition location of a symbol across all languages.

    Supports cross-language lookup (e.g., from TS to Go or vice versa).
    Returns all matching definitions sorted by relevance.
    """
    root = os.path.expanduser(workspace)
    if not os.path.isdir(root):
        raise HTTPException(status_code=404, detail="Workspace not found")

    try:
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
        indexer = SymbolIndexer()
        dep_map = indexer.index_workspace(root, use_cache=True)
    except Exception as e:
        return {"definitions": [], "error": str(e)}

    defs = dep_map.get_symbol_defs(symbol)

    if not defs:
        all_syms = []
        for sym_list in dep_map._symbols.values():
            all_syms.extend(sym_list)
        for sym in all_syms:
            if sym.name.endswith(f".{symbol}") or symbol in sym.name:
                defs.append(sym)

    results = []
    for d in defs:
        rel = os.path.relpath(d.file_path, root)
        score = 1.0
        if fromFile:
            if d.file_path.endswith(fromFile):
                score = 0.5
            elif os.path.splitext(d.file_path)[1] != os.path.splitext(fromFile)[1]:
                score = 1.5
        results.append({
            "name": d.name,
            "kind": d.kind,
            "filePath": rel,
            "absolutePath": d.file_path,
            "startLine": d.start_line,
            "endLine": d.end_line,
            "isExported": d.is_exported,
            "language": _lang_from_ext(os.path.splitext(d.file_path)[1]),
            "score": score,
        })

    results.sort(key=lambda r: r["score"], reverse=True)

    return {"symbol": symbol, "definitions": results[:10]}


# ── GET /symbols/languages — Language distribution ────────────

@router.get("/symbols/languages")
async def language_distribution(
    workspace: str = Query(..., description="Workspace root path"),
):
    """Return the language distribution for a workspace (file counts and line counts)."""
    root = os.path.expanduser(workspace)
    if not os.path.isdir(root):
        raise HTTPException(status_code=404, detail="Workspace not found")

    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next", "target"}
    ext_map = {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".js": "JavaScript", ".jsx": "JavaScript",
        ".go": "Go", ".java": "Java", ".rs": "Rust",
        ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
        ".kt": "Kotlin", ".cs": "C#", ".cpp": "C++", ".c": "C",
        ".css": "CSS", ".scss": "SCSS", ".html": "HTML",
    }

    lang_files: dict = {}
    lang_lines: dict = {}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            lang = ext_map.get(ext)
            if not lang:
                continue

            fpath = os.path.join(dirpath, fname)
            lang_files[lang] = lang_files.get(lang, 0) + 1
            try:
                with open(fpath, "r", errors="ignore") as f:
                    lang_lines[lang] = lang_lines.get(lang, 0) + sum(1 for _ in f)
            except Exception:
                pass

    total_files = sum(lang_files.values())
    total_lines = sum(lang_lines.values())

    distribution = []
    for lang in sorted(lang_files, key=lambda l: lang_lines.get(l, 0), reverse=True):
        distribution.append({
            "language": lang,
            "files": lang_files[lang],
            "lines": lang_lines.get(lang, 0),
            "filePercent": round(lang_files[lang] / max(total_files, 1) * 100, 1),
            "linePercent": round(lang_lines.get(lang, 0) / max(total_lines, 1) * 100, 1),
        })

    return {
        "totalFiles": total_files,
        "totalLines": total_lines,
        "distribution": distribution,
    }


def _lang_from_ext(ext: str) -> str:
    """Map file extension to language name."""
    m = {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
        ".js": "JavaScript", ".jsx": "JavaScript",
        ".go": "Go", ".java": "Java", ".rs": "Rust",
    }
    return m.get(ext.lower(), "Unknown")
