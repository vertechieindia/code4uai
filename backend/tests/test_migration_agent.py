"""Day 19 — Multi-File Migration Agent test suite.

Tests:
  - MigrationPlanner: symbol extraction, content manipulation, import updates.
  - ImportSyncer: batch import rewriting, fallback search.
  - MigrationExecutor: atomic write, full rollback on failure.
  - End-to-end: move symbol + verify imports + verify rollback.
  - API endpoints: plan, execute, move.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

import pytest

from code4u.agents.migration.planner import (
    MigrationPlan,
    MigrationPlanner,
    SymbolExtraction,
    ImportUpdate,
)
from code4u.agents.migration.import_sync import ImportSyncer, SyncedFile
from code4u.agents.migration.executor import MigrationExecutor, MigrationResult
from code4u.code_intelligence.knowledge_graph.symbol_indexer import (
    SymbolIndexer,
    DependencyMap,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def migration_project(tmp_path):
    """A project with a shared model used by many files."""
    (tmp_path / "models.py").write_text(
        "class UserProfile:\n"
        "    def __init__(self, name, email):\n"
        "        self.name = name\n"
        "        self.email = email\n\n"
        "class Order:\n"
        "    def __init__(self, user, items):\n"
        "        self.user = user\n"
        "        self.items = items\n"
    )
    (tmp_path / "api.py").write_text(
        "from models import UserProfile\n\n"
        "def get_user(uid):\n"
        "    return UserProfile('Alice', 'alice@test.com')\n"
    )
    (tmp_path / "service.py").write_text(
        "from models import UserProfile, Order\n\n"
        "def create_order(user: UserProfile):\n"
        "    return Order(user, [])\n"
    )
    (tmp_path / "admin.py").write_text(
        "from models import UserProfile\n\n"
        "def list_users():\n"
        "    return [UserProfile('Bob', 'bob@test.com')]\n"
    )
    (tmp_path / "tests.py").write_text(
        "from models import UserProfile\n\n"
        "def test_user():\n"
        "    u = UserProfile('Test', 'test@test.com')\n"
        "    assert u.name == 'Test'\n"
    )
    return tmp_path


@pytest.fixture
def migration_dep_map(migration_project):
    indexer = SymbolIndexer()
    return indexer.index_workspace(str(migration_project), use_cache=False)


# ═══════════════════════════════════════════════════════════════════════════
# MigrationPlanner tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMigrationPlanner:
    def test_plan_move_basic(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        assert plan.is_valid
        assert len(plan.symbols_to_move) == 1
        assert plan.symbols_to_move[0].name == "UserProfile"
        assert plan.symbols_to_move[0].kind == "class"

    def test_plan_finds_impacted_files(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        impacted_names = {Path(f).name for f in plan.impacted_files}
        assert "api.py" in impacted_names
        assert "admin.py" in impacted_names
        assert "tests.py" in impacted_names
        # service.py also imports UserProfile
        assert "service.py" in impacted_names

    def test_plan_generates_import_updates(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        assert len(plan.import_updates) > 0
        for iu in plan.import_updates:
            assert "entities" in iu.new_import
            assert "UserProfile" in iu.new_import

    def test_source_content_symbol_removed(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        assert "UserProfile" not in plan.source_new_content
        assert "Order" in plan.source_new_content

    def test_target_content_has_symbol(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        assert "class UserProfile:" in plan.target_new_content
        assert "self.name = name" in plan.target_new_content

    def test_plan_invalid_symbol(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["NonexistentClass"],
        )
        assert not plan.is_valid
        assert any("not found" in e for e in plan.validation_errors)

    def test_plan_invalid_source_file(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "nonexistent.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        assert not plan.is_valid

    def test_plan_to_dict(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        d = plan.to_dict()
        assert "sourceFile" in d
        assert "targetFile" in d
        assert "symbolsToMove" in d
        assert "importUpdates" in d
        assert "totalOperations" in d

    def test_plan_total_operations(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        # source + target + import updates
        assert plan.total_operations == 2 + len(plan.import_updates)

    def test_re_export_stub(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        assert "from entities import UserProfile" in plan.re_export_stub

    def test_plan_from_intent(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_from_intent(
            "Move UserProfile from models.py to entities.py",
            str(migration_project),
        )
        assert plan is not None
        assert plan.is_valid
        assert plan.symbols_to_move[0].name == "UserProfile"

    def test_plan_from_intent_invalid(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        result = planner.plan_from_intent(
            "do something random",
            str(migration_project),
        )
        assert result is None

    def test_naming_collision_detected(self, migration_project, migration_dep_map):
        """Moving a symbol to a file that already has it should fail."""
        # Create target with conflicting name
        (migration_project / "entities.py").write_text(
            "class UserProfile:\n    pass\n"
        )
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        assert not plan.is_valid
        assert any("collision" in e.lower() for e in plan.validation_errors)


# ═══════════════════════════════════════════════════════════════════════════
# ImportSyncer tests
# ═══════════════════════════════════════════════════════════════════════════

class TestImportSyncer:
    def test_sync_basic(self):
        syncer = ImportSyncer()
        updates = [
            ImportUpdate(
                file_path="/fake/api.py",
                old_import="from models import UserProfile",
                new_import="from entities import UserProfile",
                line_number=1,
            ),
        ]
        content = "from models import UserProfile\n\ndef get_user():\n    pass\n"
        results = syncer.sync_all(updates, file_contents={"/fake/api.py": content})
        assert len(results) == 1
        assert results[0].changed
        assert "from entities import UserProfile" in results[0].new_content

    def test_sync_multiple_files(self):
        syncer = ImportSyncer()
        updates = [
            ImportUpdate(
                file_path="/fake/a.py",
                old_import="from models import X",
                new_import="from entities import X",
                line_number=1,
            ),
            ImportUpdate(
                file_path="/fake/b.py",
                old_import="from models import X",
                new_import="from entities import X",
                line_number=1,
            ),
        ]
        contents = {
            "/fake/a.py": "from models import X\n\nprint(X)\n",
            "/fake/b.py": "from models import X\n\nuse(X)\n",
        }
        results = syncer.sync_all(updates, file_contents=contents)
        assert len(results) == 2
        assert all(r.changed for r in results)

    def test_sync_fallback_search(self):
        """If line_number doesn't match, syncer searches for the old import."""
        syncer = ImportSyncer()
        updates = [
            ImportUpdate(
                file_path="/fake/api.py",
                old_import="from models import UserProfile",
                new_import="from entities import UserProfile",
                line_number=99,  # wrong line number
            ),
        ]
        content = "# comment\nfrom models import UserProfile\n\ndef get():\n    pass\n"
        results = syncer.sync_all(updates, file_contents={"/fake/api.py": content})
        assert results[0].changed
        assert "from entities import UserProfile" in results[0].new_content

    def test_sync_no_change_needed(self):
        syncer = ImportSyncer()
        updates = [
            ImportUpdate(
                file_path="/fake/api.py",
                old_import="from something import Else",
                new_import="from something import Else",
                line_number=1,
            ),
        ]
        content = "from something import Else\n"
        results = syncer.sync_all(updates, file_contents={"/fake/api.py": content})
        assert not results[0].changed

    def test_preview(self):
        syncer = ImportSyncer()
        updates = [
            ImportUpdate(
                file_path="/fake/a.py",
                old_import="from old import X",
                new_import="from new import X",
                line_number=1,
            ),
        ]
        preview = syncer.preview(updates)
        assert len(preview) == 1
        assert preview[0]["old"] == "from old import X"


# ═══════════════════════════════════════════════════════════════════════════
# MigrationExecutor tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMigrationExecutor:
    def test_dry_run(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        executor = MigrationExecutor()
        result = executor.execute(plan, dry_run=True)
        assert result.success
        assert result.dry_run
        assert not (migration_project / "entities.py").exists()

    def test_execute_creates_target(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        executor = MigrationExecutor()
        result = executor.execute(plan)
        assert result.success
        assert (migration_project / "entities.py").exists()
        target_content = (migration_project / "entities.py").read_text()
        assert "class UserProfile:" in target_content

    def test_execute_removes_from_source(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        executor = MigrationExecutor()
        result = executor.execute(plan)
        assert result.success
        source_content = (migration_project / "models.py").read_text()
        assert "UserProfile" not in source_content
        assert "Order" in source_content

    def test_execute_updates_imports(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        executor = MigrationExecutor()
        result = executor.execute(plan)
        assert result.success

        api_content = (migration_project / "api.py").read_text()
        assert "from entities import UserProfile" in api_content

        admin_content = (migration_project / "admin.py").read_text()
        assert "from entities import UserProfile" in admin_content

    def test_execute_invalid_plan(self, migration_project, migration_dep_map):
        plan = MigrationPlan(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            is_valid=False,
            validation_errors=["test error"],
        )
        executor = MigrationExecutor()
        result = executor.execute(plan)
        assert not result.success
        assert "validation errors" in result.error

    def test_result_to_dict(self, migration_project, migration_dep_map):
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        executor = MigrationExecutor()
        result = executor.execute(plan, dry_run=True)
        d = result.to_dict()
        assert "success" in d
        assert "filesWritten" in d
        assert "dryRun" in d


# ═══════════════════════════════════════════════════════════════════════════
# Rollback tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAtomicRollback:
    def test_rollback_on_write_failure(self, migration_project, migration_dep_map):
        """If a file write fails, ALL changes must be rolled back."""
        # Save original state
        original_models = (migration_project / "models.py").read_text()
        original_api = (migration_project / "api.py").read_text()
        original_admin = (migration_project / "admin.py").read_text()

        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )

        # Make one impacted file read-only to force a write failure
        admin_path = migration_project / "admin.py"
        admin_path.chmod(0o444)

        executor = MigrationExecutor()
        try:
            result = executor.execute(plan)
        finally:
            admin_path.chmod(0o644)

        assert not result.success
        assert result.files_rolled_back > 0

        # Verify filesystem is restored
        assert (migration_project / "models.py").read_text() == original_models
        assert (migration_project / "api.py").read_text() == original_api
        # entities.py should not exist (was newly created then rolled back)
        assert not (migration_project / "entities.py").exists()

    def test_rollback_preserves_unrelated_files(self, migration_project, migration_dep_map):
        """Files not involved in the migration should be untouched."""
        original_tests = (migration_project / "tests.py").read_text()

        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["Order"],
        )
        executor = MigrationExecutor()
        result = executor.execute(plan)

        # Whether it succeeds or fails, tests.py should be unchanged
        # (tests.py doesn't import Order)
        assert (migration_project / "tests.py").read_text() == original_tests


# ═══════════════════════════════════════════════════════════════════════════
# End-to-end integration tests
# ═══════════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    def test_full_move_and_verify(self, migration_project, migration_dep_map):
        """Move UserProfile and verify every file is correct."""
        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        executor = MigrationExecutor()
        result = executor.execute(plan)

        assert result.success
        assert result.files_written >= 3  # source + target + at least 1 import fix

        # Target has the class
        assert "class UserProfile:" in (migration_project / "entities.py").read_text()

        # Source still has Order but not UserProfile
        source = (migration_project / "models.py").read_text()
        assert "UserProfile" not in source
        assert "Order" in source

        # All callers point to entities
        for name in ["api.py", "admin.py", "tests.py"]:
            content = (migration_project / name).read_text()
            assert "entities" in content, f"{name} should import from entities"

    def test_move_variable(self, migration_project, migration_dep_map):
        """Variables can also be moved."""
        (migration_project / "config.py").write_text(
            "APP_NAME = 'code4u'\n\nDEBUG = True\n"
        )
        # Re-index
        dep_map = SymbolIndexer().index_workspace(str(migration_project), use_cache=False)
        planner = MigrationPlanner(dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "config.py"),
            target_file=str(migration_project / "settings.py"),
            symbol_names=["APP_NAME"],
        )
        assert plan.is_valid
        executor = MigrationExecutor()
        result = executor.execute(plan)
        assert result.success
        assert "APP_NAME" in (migration_project / "settings.py").read_text()

    def test_move_preserves_syntax(self, migration_project, migration_dep_map):
        """After migration, all files must have valid Python syntax."""
        import ast

        planner = MigrationPlanner(migration_dep_map)
        plan = planner.plan_move(
            source_file=str(migration_project / "models.py"),
            target_file=str(migration_project / "entities.py"),
            symbol_names=["UserProfile"],
        )
        executor = MigrationExecutor()
        executor.execute(plan)

        for py_file in migration_project.glob("*.py"):
            content = py_file.read_text()
            if content.strip():
                ast.parse(content)  # should not raise


# ═══════════════════════════════════════════════════════════════════════════
# API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMigrationAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        self.client = TestClient(app)
        yield

    def test_plan_endpoint(self, migration_project):
        resp = self.client.post("/api/v1/migration/plan", json={
            "sourceFile": str(migration_project / "models.py"),
            "targetFile": str(migration_project / "entities.py"),
            "symbolNames": ["UserProfile"],
            "workspacePath": str(migration_project),
        })
        assert resp.status_code == 200
        plan = resp.json()["plan"]
        assert plan["isValid"]
        assert len(plan["symbolsToMove"]) == 1

    def test_move_endpoint_dry_run(self, migration_project):
        resp = self.client.post("/api/v1/migration/move", json={
            "intent": "Move UserProfile from models.py to entities.py",
            "workspacePath": str(migration_project),
            "dryRun": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["success"]
        assert data["result"]["dryRun"]

    def test_move_endpoint_execute(self, migration_project):
        resp = self.client.post("/api/v1/migration/move", json={
            "sourceFile": str(migration_project / "models.py"),
            "targetFile": str(migration_project / "entities.py"),
            "symbolNames": ["UserProfile"],
            "workspacePath": str(migration_project),
            "dryRun": False,
        })
        assert resp.status_code == 200
        assert resp.json()["result"]["success"]
        assert (migration_project / "entities.py").exists()

    def test_move_endpoint_bad_intent(self, migration_project):
        resp = self.client.post("/api/v1/migration/move", json={
            "intent": "do something random",
            "workspacePath": str(migration_project),
        })
        assert resp.status_code == 400
