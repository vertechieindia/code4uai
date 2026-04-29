"""Distribution Builder — packaging config for single-binary builds.

Provides configuration and helpers for building a portable ``code4u``
binary using PyInstaller (primary) or Nuitka (alternative).

Usage::

    from code4u.core.dist import get_pyinstaller_spec, get_build_info

    spec = get_pyinstaller_spec()
    print(spec["entry_point"])
    print(spec["hidden_imports"])
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any, Dict, List

from code4u.core.version import VERSION


def get_build_info() -> Dict[str, Any]:
    """Return build metadata for the current environment."""
    return {
        "version": VERSION,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.system().lower(),
        "arch": platform.machine(),
        "executable": sys.executable,
        "package_dir": str(Path(__file__).parent.parent),
    }


def get_pyinstaller_spec() -> Dict[str, Any]:
    """Return PyInstaller configuration for building code4u binary."""
    pkg_root = Path(__file__).parent.parent

    hidden_imports = [
        "code4u.cli.main",
        "code4u.core.version",
        "code4u.core.nexus",
        "code4u.core.recipes",
        "code4u.core.presence",
        "code4u.core.staging",
        "code4u.core.watcher",
        "code4u.core.guardrails",
        "code4u.core.consensus",
        "code4u.core.loader",
        "code4u.agents.nexus.sentinel",
        "code4u.agents.nexus.rules",
        "code4u.agents.nexus.impact_analyzer",
        "code4u.agents.performance.parser",
        "code4u.agents.performance.optimizer",
        "code4u.agents.orchestrator.chief",
        "code4u.agents.orchestrator.controller",
        "code4u.agents.orchestrator.models",
        "code4u.agents.chat.retriever",
        "code4u.agents.chat.assembler",
        "code4u.agents.healing.parser",
        "code4u.agents.healing.diagnoser",
        "code4u.agents.migration.planner",
        "code4u.agents.migration.import_sync",
        "code4u.agents.migration.executor",
        "code4u.agents.review.critic",
        "code4u.agents.vision.processor",
        "code4u.agents.vision.mapper",
        "code4u.agents.meta.forge",
        "code4u.agents.base",
        "code4u.interfaces.cli.dashboard",
        "code4u.interfaces.api.app",
        "code4u.code_intelligence.knowledge_graph.symbol_indexer",
        "code4u.ai_engine.llm.adapters.base",
        "code4u.models.analytics",
        "structlog",
        "rich",
        "typer",
        "yaml",
        "watchdog",
        "filelock",
    ]

    data_files: List[str] = []

    return {
        "entry_point": str(pkg_root / "cli" / "main.py"),
        "name": "code4u",
        "version": VERSION,
        "one_file": True,
        "console": True,
        "hidden_imports": hidden_imports,
        "data_files": data_files,
        "icon": None,
        "strip": True,
        "upx": True,
    }


def generate_pyinstaller_command() -> str:
    """Generate the PyInstaller CLI command."""
    spec = get_pyinstaller_spec()
    parts = [
        "pyinstaller",
        "--onefile",
        "--console",
        f"--name {spec['name']}",
        "--strip",
    ]
    for hi in spec["hidden_imports"]:
        parts.append(f"--hidden-import {hi}")
    parts.append(spec["entry_point"])
    return " \\\n  ".join(parts)
