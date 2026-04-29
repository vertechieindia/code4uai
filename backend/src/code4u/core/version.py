"""Version Manager — versioning, update checks, and self-update.

Provides:
  - ``VERSION`` constant for the current release.
  - ``VersionManager`` for comparing local vs. remote versions.
  - Atomic binary/package swap for ``code4u update``.

The remote version is fetched from a ``version.json`` at a configurable
URL (defaults to the GitHub release endpoint).

Usage::

    vm = VersionManager()
    info = vm.check_update()
    if info["update_available"]:
        print(f"New version {info['remote']} available!")
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import structlog

logger = structlog.get_logger("version")

# ---------------------------------------------------------------------------
# Current version
# ---------------------------------------------------------------------------

VERSION = "1.0.0"
VERSION_TUPLE: Tuple[int, ...] = tuple(int(x) for x in VERSION.split("."))

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_VERSION_URL = "https://raw.githubusercontent.com/code4u-ai/code4u/main/version.json"
_CODE4U_DIR = Path.home() / ".code4u"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class UpdateInfo:
    """Result of an update check."""
    local_version: str = VERSION
    remote_version: str = ""
    update_available: bool = False
    release_notes: str = ""
    download_url: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "localVersion": self.local_version,
            "remoteVersion": self.remote_version,
            "updateAvailable": self.update_available,
            "releaseNotes": self.release_notes,
            "downloadUrl": self.download_url,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# VersionManager
# ---------------------------------------------------------------------------

class VersionManager:
    """Manages version checks and updates."""

    def __init__(
        self,
        version_url: str = _DEFAULT_VERSION_URL,
        local_version: str = VERSION,
    ) -> None:
        self._url = version_url
        self._local = local_version

    @property
    def current_version(self) -> str:
        return self._local

    def check_update(self, remote_data: Optional[Dict[str, Any]] = None) -> UpdateInfo:
        """Check if a newer version is available.

        If *remote_data* is provided, uses it directly (for testing).
        Otherwise attempts an HTTP fetch of the version URL.
        """
        info = UpdateInfo(local_version=self._local)

        if remote_data is None:
            remote_data = self._fetch_remote()

        if not remote_data:
            info.error = "Could not fetch remote version."
            return info

        info.remote_version = remote_data.get("version", "")
        info.release_notes = remote_data.get("release_notes", "")
        info.download_url = remote_data.get("download_url", "")

        if info.remote_version:
            info.update_available = self._is_newer(info.remote_version)

        return info

    def ensure_directories(self) -> Dict[str, str]:
        """Create the ~/.code4u directory structure.

        Returns a dict of created directory paths.
        """
        dirs = {
            "root": _CODE4U_DIR,
            "plugins": _CODE4U_DIR / "plugins",
            "recipes": _CODE4U_DIR / "recipes",
            "rules": _CODE4U_DIR / "rules",
            "sessions": _CODE4U_DIR / "sessions",
            "logs": _CODE4U_DIR / "logs",
            "cache": _CODE4U_DIR / "global_cache",
        }
        created = {}
        for name, path in dirs.items():
            path.mkdir(parents=True, exist_ok=True)
            created[name] = str(path)

        logger.info("directories_ensured", dirs=list(created.keys()))
        return created

    def install_base_recipes(self) -> int:
        """Install the 'Standard Excellence' recipe pack.

        Returns the number of recipes installed.
        """
        recipes_dir = _CODE4U_DIR / "recipes"
        recipes_dir.mkdir(parents=True, exist_ok=True)

        base_recipes = self._get_base_recipes()
        installed = 0

        for recipe_id, content in base_recipes.items():
            recipe_file = recipes_dir / f"{recipe_id}.yaml"
            if not recipe_file.exists():
                recipe_file.write_text(content, encoding="utf-8")
                installed += 1

        logger.info("base_recipes_installed", count=installed)
        return installed

    def write_version_file(self) -> str:
        """Write a local version marker."""
        version_file = _CODE4U_DIR / "version.json"
        data = {
            "version": self._local,
            "installed_at": str(Path.home()),
        }
        version_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return str(version_file)

    def run_diagnostics(self, workspace: str = "") -> Dict[str, Any]:
        """Run a health diagnostic on the code4u installation."""
        diag: Dict[str, Any] = {
            "version": self._local,
            "code4u_dir": str(_CODE4U_DIR),
            "code4u_dir_exists": _CODE4U_DIR.is_dir(),
            "plugins_dir": str(_CODE4U_DIR / "plugins"),
            "recipes_dir": str(_CODE4U_DIR / "recipes"),
            "rules_dir": str(_CODE4U_DIR / "rules"),
        }

        # Count installed items
        for subdir in ("plugins", "recipes", "rules"):
            d = _CODE4U_DIR / subdir
            if d.is_dir():
                count = len([f for f in d.iterdir() if f.is_file()])
                diag[f"{subdir}_count"] = count
            else:
                diag[f"{subdir}_count"] = 0

        # Workspace info
        if workspace:
            ws = Path(workspace)
            diag["workspace"] = str(ws)
            diag["workspace_exists"] = ws.is_dir()
            if ws.is_dir():
                py_files = list(ws.rglob("*.py"))
                diag["python_files"] = len(py_files)
                repos = [
                    d.name for d in ws.iterdir()
                    if d.is_dir() and (d / ".git").exists()
                ]
                diag["repos"] = repos
                diag["repo_count"] = len(repos)

        return diag

    # -- Internal ------------------------------------------------------------

    def _fetch_remote(self) -> Optional[Dict[str, Any]]:
        """Fetch remote version.json (best-effort)."""
        try:
            import httpx
            resp = httpx.get(self._url, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _is_newer(self, remote_version: str) -> bool:
        """Check if remote_version is newer than local."""
        try:
            remote = tuple(int(x) for x in remote_version.split("."))
            local = tuple(int(x) for x in self._local.split("."))
            return remote > local
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def _get_base_recipes() -> Dict[str, str]:
        """Return the 'Standard Excellence' recipe pack."""
        return {
            "fstring-convert": (
                "id: fstring-convert\n"
                "name: Convert to f-strings\n"
                "description: |\n"
                "  Convert old % formatting and .format() calls to f-strings.\n"
                "selector:\n"
                "  file_glob: \"*.py\"\n"
                "prompt_template: |\n"
                "  Convert all old-style string formatting (% and .format())\n"
                "  to modern f-strings. Preserve the original logic.\n"
                "tags: [modernize, python, style]\n"
            ),
            "pathlib-convert": (
                "id: pathlib-convert\n"
                "name: Convert os.path to pathlib\n"
                "description: |\n"
                "  Replace os.path calls with pathlib.Path equivalents.\n"
                "selector:\n"
                "  file_glob: \"*.py\"\n"
                "prompt_template: |\n"
                "  Replace all os.path usage with pathlib.Path.\n"
                "  Import pathlib at the top. Remove unused os imports.\n"
                "tags: [modernize, python, pathlib]\n"
            ),
            "logging-standard": (
                "id: logging-standard\n"
                "name: Standardize Logging\n"
                "description: |\n"
                "  Replace print() debug statements with proper logging.\n"
                "selector:\n"
                "  file_glob: \"*.py\"\n"
                "prompt_template: |\n"
                "  Replace print() calls used for debugging with\n"
                "  structlog or logging module calls.\n"
                "  Use logger.debug() for debug info, logger.info() for status.\n"
                "tags: [quality, python, logging]\n"
            ),
            "type-hints": (
                "id: type-hints\n"
                "name: Add Type Hints\n"
                "description: |\n"
                "  Add type annotations to functions missing them.\n"
                "selector:\n"
                "  file_glob: \"*.py\"\n"
                "prompt_template: |\n"
                "  Add type hints to all function parameters and return types.\n"
                "  Use modern typing syntax (PEP 604 unions with |).\n"
                "  Add 'from __future__ import annotations' if needed.\n"
                "tags: [quality, python, typing]\n"
            ),
        }
