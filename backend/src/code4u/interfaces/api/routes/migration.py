"""Library Migration API — analyze and plan dependency upgrades.

Endpoints:
  - ``POST /migrate/analyze``   — analyze a workspace for outdated deps.
  - ``POST /migrate/plan``      — generate a migration plan for a library upgrade.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class AnalyzeRequest(BaseModel):
    workspacePath: str = Field(..., description="Workspace root path.")


class MigratePlanRequest(BaseModel):
    workspacePath: str = Field(..., description="Workspace root path.")
    library: str = Field(..., description="Library/package name to upgrade.")
    targetVersion: str = Field("", description="Target version (latest if empty).")
    language: str = Field("", description="Language hint (auto-detect if empty).")


@router.post("/migrate/analyze")
async def analyze_dependencies(request: AnalyzeRequest):
    """Scan a workspace and return all dependency files with their packages."""
    workspace = request.workspacePath
    if not os.path.isdir(workspace):
        raise HTTPException(status_code=404, detail="Workspace not found")

    results: List[Dict[str, Any]] = []

    pkg_json = os.path.join(workspace, "package.json")
    if os.path.isfile(pkg_json):
        results.append(_analyze_npm(pkg_json))

    go_mod = os.path.join(workspace, "go.mod")
    if os.path.isfile(go_mod):
        results.append(_analyze_go_mod(go_mod))

    req_txt = os.path.join(workspace, "requirements.txt")
    if os.path.isfile(req_txt):
        results.append(_analyze_pip(req_txt))

    pyproject = os.path.join(workspace, "pyproject.toml")
    if os.path.isfile(pyproject):
        results.append(_analyze_pyproject(pyproject))

    cargo = os.path.join(workspace, "Cargo.toml")
    if os.path.isfile(cargo):
        results.append(_analyze_cargo(cargo))

    pom = os.path.join(workspace, "pom.xml")
    if os.path.isfile(pom):
        results.append(_analyze_maven(pom))

    return {
        "workspace": workspace,
        "manifests": results,
        "totalPackages": sum(len(r.get("packages", [])) for r in results),
    }


def _analyze_npm(path: str) -> Dict[str, Any]:
    try:
        with open(path) as f:
            pkg = json.load(f)
    except Exception:
        return {"file": "package.json", "ecosystem": "npm", "packages": []}

    packages = []
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name, version in pkg.get(section, {}).items():
            packages.append({
                "name": name,
                "currentVersion": version,
                "section": section,
                "ecosystem": "npm",
            })

    return {"file": "package.json", "ecosystem": "npm", "packages": packages}


def _analyze_go_mod(path: str) -> Dict[str, Any]:
    packages = []
    try:
        with open(path) as f:
            content = f.read()

        in_require = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "require (":
                in_require = True
                continue
            if in_require and stripped == ")":
                in_require = False
                continue
            if in_require and stripped and not stripped.startswith("//"):
                parts = stripped.split()
                if len(parts) >= 2:
                    packages.append({
                        "name": parts[0],
                        "currentVersion": parts[1],
                        "section": "require",
                        "ecosystem": "go",
                    })

            single = re.match(r"^require\s+(\S+)\s+(\S+)", stripped)
            if single:
                packages.append({
                    "name": single.group(1),
                    "currentVersion": single.group(2),
                    "section": "require",
                    "ecosystem": "go",
                })
    except Exception:
        pass

    return {"file": "go.mod", "ecosystem": "go", "packages": packages}


def _analyze_pip(path: str) -> Dict[str, Any]:
    packages = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                m = re.match(r"([a-zA-Z0-9_\-\.]+)\s*([><=!~]+\s*[\d\.\*]+)?", line)
                if m:
                    packages.append({
                        "name": m.group(1),
                        "currentVersion": (m.group(2) or "").strip(),
                        "section": "requirements",
                        "ecosystem": "pip",
                    })
    except Exception:
        pass

    return {"file": "requirements.txt", "ecosystem": "pip", "packages": packages}


def _analyze_pyproject(path: str) -> Dict[str, Any]:
    packages = []
    try:
        with open(path) as f:
            content = f.read()

        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped in ("[project.dependencies]", "dependencies = ["):
                in_deps = True
                continue
            if in_deps and (stripped.startswith("[") or stripped == "]"):
                in_deps = False
                continue
            if in_deps and stripped:
                clean = stripped.strip('",').strip("',")
                m = re.match(r"([a-zA-Z0-9_\-\.]+)\s*([><=!~]+.*)?", clean)
                if m:
                    packages.append({
                        "name": m.group(1),
                        "currentVersion": (m.group(2) or "").strip(),
                        "section": "dependencies",
                        "ecosystem": "pip",
                    })
    except Exception:
        pass

    return {"file": "pyproject.toml", "ecosystem": "pip", "packages": packages}


def _analyze_cargo(path: str) -> Dict[str, Any]:
    packages = []
    try:
        with open(path) as f:
            content = f.read()

        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "[dependencies]":
                in_deps = True
                continue
            if in_deps and stripped.startswith("["):
                in_deps = False
                continue
            if in_deps and "=" in stripped:
                m = re.match(r'(\w[\w\-]*)\s*=\s*["\']?([^"\']+)', stripped)
                if m:
                    packages.append({
                        "name": m.group(1),
                        "currentVersion": m.group(2).strip(),
                        "section": "dependencies",
                        "ecosystem": "cargo",
                    })
    except Exception:
        pass

    return {"file": "Cargo.toml", "ecosystem": "cargo", "packages": packages}


def _analyze_maven(path: str) -> Dict[str, Any]:
    packages = []
    try:
        with open(path) as f:
            content = f.read()

        for m in re.finditer(
            r"<dependency>.*?<groupId>([^<]+)</groupId>.*?<artifactId>([^<]+)</artifactId>.*?(?:<version>([^<]+)</version>)?.*?</dependency>",
            content, re.DOTALL,
        ):
            packages.append({
                "name": f"{m.group(1)}:{m.group(2)}",
                "currentVersion": m.group(3) or "",
                "section": "dependencies",
                "ecosystem": "maven",
            })
    except Exception:
        pass

    return {"file": "pom.xml", "ecosystem": "maven", "packages": packages}


@router.post("/migrate/plan")
async def migration_plan(request: MigratePlanRequest):
    """Generate a migration plan for upgrading a specific library.

    Scans the workspace for all usages of the library, identifies
    breaking change patterns, and suggests an upgrade path.
    """
    workspace = request.workspacePath
    if not os.path.isdir(workspace):
        raise HTTPException(status_code=404, detail="Workspace not found")

    library = request.library
    target = request.targetVersion or "latest"

    usage_files: List[Dict[str, Any]] = []
    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
    code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rs"}

    import_patterns = [
        re.compile(rf"""(?:from|import)\s+{re.escape(library)}"""),
        re.compile(rf"""require\s*\(\s*['\"]{re.escape(library)}"""),
        re.compile(rf"""import\s+['\"]{re.escape(library)}"""),
    ]

    scanned = 0
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in code_exts:
                continue
            if scanned > 200:
                break
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue
            scanned += 1

            matches = []
            for i, line in enumerate(content.splitlines()):
                for pat in import_patterns:
                    if pat.search(line):
                        matches.append({"line": i + 1, "text": line.strip()[:120]})
                        break

            if matches:
                rel = os.path.relpath(fpath, workspace)
                usage_files.append({
                    "filePath": rel,
                    "imports": matches,
                    "importCount": len(matches),
                })

    manifest_info = _find_manifest_version(workspace, library)

    steps = []
    if manifest_info:
        steps.append({
            "step": 1,
            "action": "update_manifest",
            "description": f"Update {manifest_info['file']} to set {library} version to {target}",
            "file": manifest_info["file"],
        })

    if usage_files:
        steps.append({
            "step": 2,
            "action": "review_imports",
            "description": f"Review {len(usage_files)} file(s) that import {library} for breaking API changes",
            "affectedFiles": len(usage_files),
        })

    steps.append({
        "step": len(steps) + 1,
        "action": "run_tests",
        "description": "Run the test suite to catch any regressions from the upgrade",
    })

    steps.append({
        "step": len(steps) + 1,
        "action": "lint_check",
        "description": "Run linters to catch deprecated API usage",
    })

    return {
        "library": library,
        "currentVersion": manifest_info.get("version", "unknown") if manifest_info else "unknown",
        "targetVersion": target,
        "usageFiles": usage_files,
        "totalUsages": sum(f["importCount"] for f in usage_files),
        "filesScanned": scanned,
        "migrationSteps": steps,
        "riskLevel": "high" if len(usage_files) > 10 else "medium" if len(usage_files) > 3 else "low",
    }


def _find_manifest_version(workspace: str, library: str) -> Optional[Dict[str, str]]:
    """Find the current version of a library in the workspace's manifest."""
    pkg_json = os.path.join(workspace, "package.json")
    if os.path.isfile(pkg_json):
        try:
            with open(pkg_json) as f:
                pkg = json.load(f)
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                if library in pkg.get(section, {}):
                    return {"file": "package.json", "version": pkg[section][library]}
        except Exception:
            pass

    req_txt = os.path.join(workspace, "requirements.txt")
    if os.path.isfile(req_txt):
        try:
            with open(req_txt) as f:
                for line in f:
                    if line.strip().lower().startswith(library.lower()):
                        m = re.match(r"[a-zA-Z0-9_\-\.]+\s*([><=!~]+\s*[\d\.\*]+)", line.strip())
                        if m:
                            return {"file": "requirements.txt", "version": m.group(1).strip()}
        except Exception:
            pass

    go_mod = os.path.join(workspace, "go.mod")
    if os.path.isfile(go_mod):
        try:
            with open(go_mod) as f:
                for line in f:
                    if library in line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            return {"file": "go.mod", "version": parts[-1]}
        except Exception:
            pass

    return None
