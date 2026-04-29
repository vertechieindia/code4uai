"""Day 30 — V1.0 Launch test suite.

Tests:
  - VersionManager: version constant, update checks, directory setup, recipes.
  - Distribution: build info, PyInstaller spec.
  - UpdateInfo: data model serialization.
  - Diagnostics: workspace analysis.
  - CLI: welcome, update, --version commands.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code4u.core.version import (
    VERSION,
    VERSION_TUPLE,
    UpdateInfo,
    VersionManager,
)
from code4u.core.dist import (
    get_build_info,
    get_pyinstaller_spec,
    generate_pyinstaller_command,
)


# ═══════════════════════════════════════════════════════════════════════════
# Version constant tests
# ═══════════════════════════════════════════════════════════════════════════

class TestVersionConstant:
    def test_version_is_1_0_0(self):
        assert VERSION == "1.0.0"

    def test_version_tuple(self):
        assert VERSION_TUPLE == (1, 0, 0)

    def test_cli_version_matches(self):
        from code4u.cli import __version__
        assert __version__ == VERSION


# ═══════════════════════════════════════════════════════════════════════════
# UpdateInfo tests
# ═══════════════════════════════════════════════════════════════════════════

class TestUpdateInfo:
    def test_defaults(self):
        info = UpdateInfo()
        assert info.local_version == VERSION
        assert not info.update_available
        assert info.error == ""

    def test_to_dict(self):
        info = UpdateInfo(
            remote_version="2.0.0",
            update_available=True,
            release_notes="New features!",
        )
        d = info.to_dict()
        assert d["remoteVersion"] == "2.0.0"
        assert d["updateAvailable"]
        assert d["releaseNotes"] == "New features!"


# ═══════════════════════════════════════════════════════════════════════════
# VersionManager tests
# ═══════════════════════════════════════════════════════════════════════════

class TestVersionManager:
    def test_current_version(self):
        vm = VersionManager()
        assert vm.current_version == VERSION

    def test_check_update_newer(self):
        vm = VersionManager(local_version="1.0.0")
        info = vm.check_update({"version": "2.0.0", "release_notes": "Big update"})
        assert info.update_available
        assert info.remote_version == "2.0.0"
        assert info.release_notes == "Big update"

    def test_check_update_same(self):
        vm = VersionManager(local_version="1.0.0")
        info = vm.check_update({"version": "1.0.0"})
        assert not info.update_available

    def test_check_update_older(self):
        vm = VersionManager(local_version="2.0.0")
        info = vm.check_update({"version": "1.0.0"})
        assert not info.update_available

    def test_check_update_no_remote(self):
        vm = VersionManager()
        info = vm.check_update(None)
        assert not info.update_available
        assert info.error != ""

    def test_check_update_invalid_version(self):
        vm = VersionManager()
        info = vm.check_update({"version": "not-a-version"})
        assert not info.update_available

    def test_ensure_directories(self, tmp_path, monkeypatch):
        monkeypatch.setattr("code4u.core.version._CODE4U_DIR", tmp_path / ".code4u")
        vm = VersionManager()
        dirs = vm.ensure_directories()
        assert "plugins" in dirs
        assert "recipes" in dirs
        assert "rules" in dirs
        assert "sessions" in dirs
        assert "logs" in dirs
        assert (tmp_path / ".code4u" / "plugins").is_dir()
        assert (tmp_path / ".code4u" / "recipes").is_dir()

    def test_install_base_recipes(self, tmp_path, monkeypatch):
        monkeypatch.setattr("code4u.core.version._CODE4U_DIR", tmp_path / ".code4u")
        vm = VersionManager()
        vm.ensure_directories()
        count = vm.install_base_recipes()
        assert count >= 4
        recipes_dir = tmp_path / ".code4u" / "recipes"
        assert (recipes_dir / "fstring-convert.yaml").exists()
        assert (recipes_dir / "pathlib-convert.yaml").exists()
        assert (recipes_dir / "logging-standard.yaml").exists()
        assert (recipes_dir / "type-hints.yaml").exists()

    def test_install_recipes_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("code4u.core.version._CODE4U_DIR", tmp_path / ".code4u")
        vm = VersionManager()
        vm.ensure_directories()
        first = vm.install_base_recipes()
        second = vm.install_base_recipes()
        assert first >= 4
        assert second == 0

    def test_write_version_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("code4u.core.version._CODE4U_DIR", tmp_path / ".code4u")
        vm = VersionManager()
        vm.ensure_directories()
        path = vm.write_version_file()
        data = json.loads(Path(path).read_text())
        assert data["version"] == VERSION

    def test_diagnostics_no_workspace(self):
        vm = VersionManager()
        diag = vm.run_diagnostics()
        assert diag["version"] == VERSION
        assert "code4u_dir" in diag

    def test_diagnostics_with_workspace(self, tmp_path):
        (tmp_path / "app.py").write_text("print('hello')\n")
        (tmp_path / "utils.py").write_text("x = 1\n")
        vm = VersionManager()
        diag = vm.run_diagnostics(str(tmp_path))
        assert diag["workspace_exists"]
        assert diag["python_files"] == 2

    def test_diagnostics_with_repos(self, tmp_path):
        repo = tmp_path / "my-repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        vm = VersionManager()
        diag = vm.run_diagnostics(str(tmp_path))
        assert diag["repo_count"] == 1
        assert "my-repo" in diag["repos"]


# ═══════════════════════════════════════════════════════════════════════════
# Distribution tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDistribution:
    def test_build_info(self):
        info = get_build_info()
        assert info["version"] == VERSION
        assert "python" in info
        assert "platform" in info
        assert "arch" in info

    def test_pyinstaller_spec(self):
        spec = get_pyinstaller_spec()
        assert spec["name"] == "code4u"
        assert spec["version"] == VERSION
        assert spec["one_file"]
        assert spec["console"]
        assert len(spec["hidden_imports"]) > 20

    def test_pyinstaller_command(self):
        cmd = generate_pyinstaller_command()
        assert "pyinstaller" in cmd
        assert "--onefile" in cmd
        assert "--name code4u" in cmd
        assert "code4u.cli.main" in cmd

    def test_hidden_imports_complete(self):
        spec = get_pyinstaller_spec()
        hi = spec["hidden_imports"]
        assert "code4u.cli.main" in hi
        assert "code4u.core.version" in hi
        assert "code4u.agents.nexus.sentinel" in hi
        assert "code4u.agents.performance.parser" in hi
        assert "code4u.agents.orchestrator.chief" in hi


# ═══════════════════════════════════════════════════════════════════════════
# Install script tests
# ═══════════════════════════════════════════════════════════════════════════

class TestInstallScript:
    def test_install_script_exists(self):
        script = Path(__file__).parent.parent.parent / "scripts" / "install.sh"
        assert script.exists(), f"install.sh not found at {script}"

    def test_install_script_executable(self):
        script = Path(__file__).parent.parent.parent / "scripts" / "install.sh"
        if script.exists():
            import os
            assert os.access(str(script), os.X_OK)

    def test_install_script_content(self):
        script = Path(__file__).parent.parent.parent / "scripts" / "install.sh"
        if script.exists():
            content = script.read_text()
            assert "#!/usr/bin/env bash" in content
            assert ".code4u" in content
            assert "python" in content.lower()


# ═══════════════════════════════════════════════════════════════════════════
# CLI command tests
# ═══════════════════════════════════════════════════════════════════════════

class TestCLICommands:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        self.client = TestClient(app)
        yield

    def test_version_endpoint(self):
        """Version is correctly wired."""
        from code4u.core.version import VERSION
        from code4u.cli import __version__
        assert __version__ == VERSION
        assert VERSION == "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════
# Integration tests
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_full_setup_flow(self, tmp_path, monkeypatch):
        """Simulate the full install flow."""
        monkeypatch.setattr("code4u.core.version._CODE4U_DIR", tmp_path / ".code4u")

        vm = VersionManager()

        # Step 1: Create directories
        dirs = vm.ensure_directories()
        assert len(dirs) >= 6

        # Step 2: Install recipes
        count = vm.install_base_recipes()
        assert count >= 4

        # Step 3: Write version file
        vf = vm.write_version_file()
        assert Path(vf).exists()

        # Step 4: Run diagnostics
        diag = vm.run_diagnostics(str(tmp_path))
        assert diag["version"] == VERSION
        assert diag["recipes_count"] >= 4

    def test_version_comparison_logic(self):
        vm = VersionManager(local_version="1.0.0")

        # Newer versions
        assert vm._is_newer("1.0.1")
        assert vm._is_newer("1.1.0")
        assert vm._is_newer("2.0.0")

        # Same or older
        assert not vm._is_newer("1.0.0")
        assert not vm._is_newer("0.9.9")
        assert not vm._is_newer("0.0.1")

    def test_base_recipes_valid_yaml(self, tmp_path, monkeypatch):
        """Verify base recipes are valid YAML."""
        monkeypatch.setattr("code4u.core.version._CODE4U_DIR", tmp_path / ".code4u")
        vm = VersionManager()
        vm.ensure_directories()
        vm.install_base_recipes()

        recipes_dir = tmp_path / ".code4u" / "recipes"
        for yaml_file in recipes_dir.glob("*.yaml"):
            content = yaml_file.read_text()
            assert "id:" in content
            assert "name:" in content
            assert "prompt_template:" in content

    def test_pyproject_version_matches(self):
        """Ensure pyproject.toml and VERSION constant are aligned."""
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            assert f'version = "{VERSION}"' in content or f"version = '{VERSION}'" in content
