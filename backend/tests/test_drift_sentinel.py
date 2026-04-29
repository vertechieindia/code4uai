"""Day 28 — Drift Sentinel test suite.

Tests:
  - ArchitecturalRule: schema, from_dict, to_dict, prompt context.
  - RuleRegistry: load, register, query by file.
  - ForbiddenImport / NamingConvention / LayerBoundary: matching logic.
  - Sentinel: full scan, delta scan, single file, suggest_fix.
  - ScanResult: aggregation, severity counts.
  - TUI DriftWarning: model and rendering.
  - ChiefArchitect JIT: rules hydrated into sub-task configs.
  - API endpoints: scan, delta, rules, suggest.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from code4u.agents.nexus.rules import (
    ArchitecturalRule,
    ForbiddenImport,
    LayerBoundary,
    NamingConvention,
    RequiredDecorator,
    RuleRegistry,
    Violation,
)
from code4u.agents.nexus.sentinel import (
    ScanResult,
    Sentinel,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_rule():
    """A standard forbidden-import rule."""
    return ArchitecturalRule(
        id="no-db-in-ui",
        name="No Database in UI Layer",
        description="UI components must not import DB models directly.",
        severity="error",
        forbidden_imports=[
            ForbiddenImport(
                module_pattern=r"sqlalchemy|models\.db",
                file_glob="*.tsx",
                reason="Use the Service layer for data access.",
            ),
        ],
    )


@pytest.fixture
def naming_rule():
    """A naming convention rule."""
    return ArchitecturalRule(
        id="snake-case-funcs",
        name="Snake Case Functions",
        description="All functions must use snake_case.",
        severity="warning",
        naming_conventions=[
            NamingConvention(
                pattern=r"^[a-z_][a-z0-9_]*$",
                symbol_type="function",
                file_glob="*.py",
                reason="Follow PEP 8 naming conventions.",
            ),
        ],
    )


@pytest.fixture
def env_rule():
    """Forbid os.environ outside config.py."""
    return ArchitecturalRule(
        id="no-env-outside-config",
        name="No os.environ Outside Config",
        description="os.environ access is only allowed in config.py.",
        severity="error",
        forbidden_imports=[
            ForbiddenImport(
                module_pattern=r"^os$",
                file_glob="routes*.py",
                reason="Use the config module for environment access.",
            ),
        ],
    )


@pytest.fixture
def workspace_with_violations(tmp_path):
    """Create a workspace with architectural violations."""
    # config.py — clean (os import allowed here)
    (tmp_path / "config.py").write_text(textwrap.dedent("""\
        import os
        DB_URL = os.environ.get("DATABASE_URL", "sqlite:///test.db")
    """))

    # routes.py — violation: imports os directly
    (tmp_path / "routes.py").write_text(textwrap.dedent("""\
        import os
        from flask import Flask

        app = Flask(__name__)
        SECRET = os.environ.get("SECRET_KEY")

        def get_users():
            return []

        def fetchData():
            return {}
    """))

    # service.py — clean
    (tmp_path / "service.py").write_text(textwrap.dedent("""\
        from config import DB_URL

        def get_all_users():
            return []
    """))

    return tmp_path


# ═══════════════════════════════════════════════════════════════════════════
# ArchitecturalRule tests
# ═══════════════════════════════════════════════════════════════════════════

class TestArchitecturalRule:
    def test_from_dict(self):
        data = {
            "id": "test-rule",
            "name": "Test Rule",
            "severity": "error",
            "forbidden_imports": [
                {"module_pattern": "django", "file_glob": "*.py", "reason": "No Django"}
            ],
            "naming_conventions": [
                {"pattern": "^[a-z_]+$", "symbol_type": "function", "file_glob": "*.py"}
            ],
            "layer_boundaries": [
                {"source_layer": "ui", "forbidden_targets": ["db"]}
            ],
        }
        rule = ArchitecturalRule.from_dict(data)
        assert rule.id == "test-rule"
        assert rule.severity == "error"
        assert len(rule.forbidden_imports) == 1
        assert len(rule.naming_conventions) == 1
        assert len(rule.layer_boundaries) == 1

    def test_to_dict(self, sample_rule):
        d = sample_rule.to_dict()
        assert d["id"] == "no-db-in-ui"
        assert d["severity"] == "error"
        assert len(d["forbiddenImports"]) == 1
        assert d["forbiddenImports"][0]["modulePattern"] == r"sqlalchemy|models\.db"

    def test_to_prompt_context(self, sample_rule):
        ctx = sample_rule.to_prompt_context()
        assert "RULE [ERROR]" in ctx
        assert "No Database in UI Layer" in ctx
        assert "FORBIDDEN import" in ctx

    def test_disabled_rule(self):
        rule = ArchitecturalRule(id="disabled", name="Off", enabled=False)
        assert not rule.enabled

    def test_defaults(self):
        rule = ArchitecturalRule(id="default", name="Default")
        assert rule.severity == "warning"
        assert rule.enabled
        assert rule.forbidden_imports == []


# ═══════════════════════════════════════════════════════════════════════════
# ForbiddenImport tests
# ═══════════════════════════════════════════════════════════════════════════

class TestForbiddenImport:
    def test_matches_module(self):
        fi = ForbiddenImport(module_pattern=r"sqlalchemy|prisma")
        assert fi.matches_module("sqlalchemy")
        assert fi.matches_module("sqlalchemy.orm")
        assert fi.matches_module("prisma")
        assert not fi.matches_module("flask")

    def test_matches_file(self):
        fi = ForbiddenImport(module_pattern="os", file_glob="routes*.py")
        assert fi.matches_file("routes.py")
        assert fi.matches_file("routes_admin.py")
        assert not fi.matches_file("config.py")

    def test_to_dict(self):
        fi = ForbiddenImport("os", "*.py", "Use config instead")
        d = fi.to_dict()
        assert d["modulePattern"] == "os"
        assert d["reason"] == "Use config instead"


# ═══════════════════════════════════════════════════════════════════════════
# NamingConvention tests
# ═══════════════════════════════════════════════════════════════════════════

class TestNamingConvention:
    def test_matches_snake_case(self):
        nc = NamingConvention(pattern=r"^[a-z_][a-z0-9_]*$")
        assert nc.matches("get_users")
        assert nc.matches("_private")
        assert not nc.matches("getData")
        assert not nc.matches("FetchAll")

    def test_to_dict(self):
        nc = NamingConvention("^[a-z]+$", "function", "*.py", "Use lowercase")
        d = nc.to_dict()
        assert d["pattern"] == "^[a-z]+$"
        assert d["symbolType"] == "function"


# ═══════════════════════════════════════════════════════════════════════════
# LayerBoundary tests
# ═══════════════════════════════════════════════════════════════════════════

class TestLayerBoundary:
    def test_to_dict(self):
        lb = LayerBoundary("ui", forbidden_targets=["db", "infra"])
        d = lb.to_dict()
        assert d["sourceLayer"] == "ui"
        assert "db" in d["forbiddenTargets"]


# ═══════════════════════════════════════════════════════════════════════════
# Violation tests
# ═══════════════════════════════════════════════════════════════════════════

class TestViolation:
    def test_to_dict(self):
        v = Violation(
            rule_id="r1", rule_name="Rule 1", severity="error",
            file_path="api.py", line=10, message="Bad import",
            symbol_name="os", suggestion="Use config",
        )
        d = v.to_dict()
        assert d["ruleId"] == "r1"
        assert d["line"] == 10
        assert d["suggestion"] == "Use config"


# ═══════════════════════════════════════════════════════════════════════════
# RuleRegistry tests
# ═══════════════════════════════════════════════════════════════════════════

class TestRuleRegistry:
    def test_register(self, sample_rule):
        reg = RuleRegistry()
        reg.register(sample_rule)
        assert reg.count == 1
        assert reg.get("no-db-in-ui") is not None

    def test_all_excludes_disabled(self, sample_rule):
        reg = RuleRegistry()
        reg.register(sample_rule)
        disabled = ArchitecturalRule(id="off", name="Off", enabled=False)
        reg.register(disabled)
        assert len(reg.all()) == 1
        assert len(reg.all_rules()) == 2

    def test_rules_for_file(self, sample_rule):
        reg = RuleRegistry()
        reg.register(sample_rule)
        assert len(reg.rules_for_file("Component.tsx")) == 1
        assert len(reg.rules_for_file("service.py")) == 0

    def test_to_prompt_context(self, sample_rule):
        reg = RuleRegistry()
        reg.register(sample_rule)
        ctx = reg.to_prompt_context()
        assert "<architectural_rules>" in ctx
        assert "No Database in UI Layer" in ctx

    def test_to_prompt_context_for_file(self, sample_rule, naming_rule):
        reg = RuleRegistry()
        reg.register(sample_rule)
        reg.register(naming_rule)
        ctx = reg.to_prompt_context("Component.tsx")
        assert "No Database in UI Layer" in ctx
        # .tsx doesn't match *.py naming rule
        assert "Snake Case" not in ctx

    def test_load_nonexistent(self):
        reg = RuleRegistry()
        reg.load("/nonexistent/path")
        assert reg.count == 0

    def test_load_from_yaml(self, tmp_path):
        rules_dir = tmp_path / ".code4u" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "test.yaml").write_text(textwrap.dedent("""\
            id: yaml-rule
            name: YAML Rule
            severity: warning
            forbidden_imports:
              - module_pattern: "os"
                file_glob: "*.py"
                reason: "No direct os usage"
        """))
        reg = RuleRegistry()
        reg.load(str(tmp_path))
        # Will only work if PyYAML is installed
        if reg.count > 0:
            rule = reg.get("yaml-rule")
            assert rule is not None
            assert rule.name == "YAML Rule"


# ═══════════════════════════════════════════════════════════════════════════
# ScanResult tests
# ═══════════════════════════════════════════════════════════════════════════

class TestScanResult:
    def test_empty(self):
        sr = ScanResult()
        assert sr.clean
        assert sr.error_count == 0
        assert sr.warning_count == 0

    def test_with_violations(self):
        sr = ScanResult(violations=[
            Violation("r1", "R1", "error", "a.py"),
            Violation("r2", "R2", "warning", "b.py"),
            Violation("r3", "R3", "error", "c.py"),
        ])
        sr.clean = False
        assert sr.error_count == 2
        assert sr.warning_count == 1

    def test_to_dict(self):
        sr = ScanResult(files_scanned=5, rules_checked=3, duration_ms=12.5, clean=True)
        d = sr.to_dict()
        assert d["filesScanned"] == 5
        assert d["clean"]


# ═══════════════════════════════════════════════════════════════════════════
# Sentinel tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSentinel:
    @pytest.fixture
    def dep_map(self, workspace_with_violations):
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
        indexer = SymbolIndexer()
        return indexer.index_workspace(str(workspace_with_violations), use_cache=False)

    def test_scan_full_forbidden_import(self, dep_map, env_rule):
        reg = RuleRegistry()
        reg.register(env_rule)
        sentinel = Sentinel(reg, dep_map)
        result = sentinel.scan_full()
        # routes.py imports os, which is forbidden for routes*.py
        os_violations = [v for v in result.violations if "os" in v.symbol_name.lower()]
        assert len(os_violations) >= 1
        assert not result.clean

    def test_scan_full_naming_convention(self, dep_map, naming_rule):
        reg = RuleRegistry()
        reg.register(naming_rule)
        sentinel = Sentinel(reg, dep_map)
        result = sentinel.scan_full()
        # routes.py has fetchData (camelCase) which violates snake_case
        camel_violations = [v for v in result.violations if "fetchData" in (v.symbol_name or "")]
        assert len(camel_violations) >= 1

    def test_scan_delta(self, dep_map, env_rule):
        reg = RuleRegistry()
        reg.register(env_rule)
        sentinel = Sentinel(reg, dep_map)
        routes_files = [f for f in dep_map.all_files if "routes" in f]
        if routes_files:
            result = sentinel.scan_delta(routes_files)
            assert result.files_scanned == len(routes_files)

    def test_scan_file(self, dep_map, env_rule):
        reg = RuleRegistry()
        reg.register(env_rule)
        sentinel = Sentinel(reg, dep_map)
        routes_files = [f for f in dep_map.all_files if "routes" in f]
        if routes_files:
            violations = sentinel.scan_file(routes_files[0])
            assert len(violations) >= 1

    def test_clean_file(self, dep_map, env_rule):
        reg = RuleRegistry()
        reg.register(env_rule)
        sentinel = Sentinel(reg, dep_map)
        service_files = [f for f in dep_map.all_files if "service" in f]
        if service_files:
            violations = sentinel.scan_file(service_files[0])
            assert len(violations) == 0

    def test_no_dep_map(self, env_rule):
        reg = RuleRegistry()
        reg.register(env_rule)
        sentinel = Sentinel(reg)
        result = sentinel.scan_full()
        assert result.clean
        assert result.files_scanned == 0

    def test_on_violation_callback(self, dep_map, env_rule):
        reg = RuleRegistry()
        reg.register(env_rule)
        captured = []
        sentinel = Sentinel(reg, dep_map, on_violation=lambda v: captured.append(v))
        sentinel.scan_full()
        routes_files = [f for f in dep_map.all_files if "routes" in f]
        if routes_files:
            assert len(captured) >= 1

    def test_rule_count(self, env_rule, naming_rule):
        reg = RuleRegistry()
        reg.register(env_rule)
        reg.register(naming_rule)
        sentinel = Sentinel(reg)
        assert sentinel.rule_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# Suggest fix tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSuggestFix:
    def test_forbidden_import_fix(self, env_rule):
        reg = RuleRegistry()
        reg.register(env_rule)
        sentinel = Sentinel(reg)
        v = Violation(
            rule_id="no-env-outside-config",
            rule_name="No os.environ Outside Config",
            severity="error",
            file_path="routes.py",
            message="Forbidden import 'os'",
            symbol_name="os",
        )
        fix = sentinel.suggest_fix(v)
        assert fix["action"] == "replace_import"
        assert fix["automatable"]
        assert "heal_intent" in fix

    def test_naming_fix(self, naming_rule):
        reg = RuleRegistry()
        reg.register(naming_rule)
        sentinel = Sentinel(reg)
        v = Violation(
            rule_id="snake-case-funcs",
            rule_name="Snake Case Functions",
            severity="warning",
            file_path="api.py",
            symbol_name="fetchData",
            message="Violates naming convention",
        )
        fix = sentinel.suggest_fix(v)
        assert fix["action"] == "rename_symbol"
        assert fix["automatable"]
        assert "heal_intent" in fix

    def test_unknown_rule_fix(self):
        reg = RuleRegistry()
        sentinel = Sentinel(reg)
        v = Violation("unknown", "Unknown", "info", "x.py", message="Something")
        fix = sentinel.suggest_fix(v)
        assert fix["action"] == "manual_review"

    def test_fix_with_suggestion(self):
        reg = RuleRegistry()
        sentinel = Sentinel(reg)
        v = Violation("r", "R", "info", "x.py", suggestion="Do this instead")
        fix = sentinel.suggest_fix(v)
        assert fix["description"] == "Do this instead"
        assert fix["automatable"]


# ═══════════════════════════════════════════════════════════════════════════
# TUI DriftWarning tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDriftWarningTUI:
    def test_drift_warning_model(self):
        from code4u.interfaces.cli.dashboard import DriftWarning
        dw = DriftWarning(
            rule_id="r1", rule_name="Rule 1",
            severity="error", file_path="api.py",
            message="Bad import detected",
        )
        assert dw.rule_id == "r1"
        assert "s ago" in dw.age_str()

    def test_add_drift_warning(self):
        from code4u.interfaces.cli.dashboard import DashboardState, DriftWarning
        state = DashboardState()
        state.add_drift_warning(DriftWarning("r1", "R1", "error", "a.py", "Bad"))
        assert len(state.drift_warnings) == 1

    def test_drift_warnings_capped(self):
        from code4u.interfaces.cli.dashboard import DashboardState, DriftWarning
        state = DashboardState()
        for i in range(20):
            state.add_drift_warning(DriftWarning(f"r{i}", f"R{i}", "warning", f"f{i}.py", f"W{i}"))
        assert len(state.drift_warnings) == 15

    def test_render_drift_panel_empty(self):
        from code4u.interfaces.cli.dashboard import DashboardState, render_drift_panel
        state = DashboardState()
        panel = render_drift_panel(state)
        assert panel is not None

    def test_render_drift_panel_with_data(self):
        from code4u.interfaces.cli.dashboard import DashboardState, DriftWarning, render_drift_panel
        state = DashboardState()
        state.add_drift_warning(DriftWarning("r1", "R1", "error", "api.py", "Forbidden import"))
        panel = render_drift_panel(state)
        assert panel is not None

    def test_dashboard_add_drift(self):
        from code4u.interfaces.cli.dashboard import DriftWarning, WarRoomDashboard
        dash = WarRoomDashboard(workspace="/tmp/test")
        dw = DriftWarning("r1", "R1", "error", "api.py", "Bad import")
        dash.add_drift_warning(dw)
        assert len(dash.state.drift_warnings) == 1

    def test_layout_with_drift(self):
        from code4u.interfaces.cli.dashboard import (
            DashboardState, DriftWarning, build_layout,
        )
        state = DashboardState(workspace="/tmp/test")
        state.add_drift_warning(DriftWarning("r1", "R1", "error", "x.py", "Bad"))
        layout = build_layout(state)
        assert layout is not None


# ═══════════════════════════════════════════════════════════════════════════
# ChiefArchitect JIT context tests
# ═══════════════════════════════════════════════════════════════════════════

class TestJITContext:
    def test_rules_hydrated_into_subtasks(self):
        from code4u.agents.orchestrator.chief import ChiefArchitect
        chief = ChiefArchitect()
        rules_ctx = "RULE [ERROR]: No DB in UI\n  - FORBIDDEN import: sqlalchemy in *.tsx"
        graph = chief.decompose(
            "Fix the broken test",
            workspace_path="/tmp/proj",
            context={"architectural_rules": rules_ctx},
        )
        for task in graph.tasks:
            assert "architectural_rules" in task.config
            assert "No DB in UI" in task.config["architectural_rules"]

    def test_no_rules_no_hydration(self):
        from code4u.agents.orchestrator.chief import ChiefArchitect
        chief = ChiefArchitect()
        graph = chief.decompose("Fix the broken test", workspace_path="/tmp/proj")
        for task in graph.tasks:
            assert "architectural_rules" not in task.config

    def test_registry_generates_prompt_context(self, sample_rule, naming_rule):
        reg = RuleRegistry()
        reg.register(sample_rule)
        reg.register(naming_rule)
        ctx = reg.to_prompt_context()
        assert "<architectural_rules>" in ctx
        assert "</architectural_rules>" in ctx
        assert "No Database in UI Layer" in ctx
        assert "Snake Case Functions" in ctx


# ═══════════════════════════════════════════════════════════════════════════
# DRIFT_DETECTED message type tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDriftMessageType:
    def test_drift_detected_exists(self):
        from code4u.core.presence import MessageType
        assert hasattr(MessageType, "DRIFT_DETECTED")
        assert MessageType.DRIFT_DETECTED.value == "DRIFT_DETECTED"


# ═══════════════════════════════════════════════════════════════════════════
# API tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSentinelAPI:
    @pytest.fixture(autouse=True)
    def setup(self, workspace_with_violations):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        from code4u.interfaces.api.routes import sentinel as sentinel_mod
        sentinel_mod._sentinel = None
        sentinel_mod._rule_registry = RuleRegistry()
        sentinel_mod._last_violations = {}
        self.client = TestClient(app)
        self.workspace = workspace_with_violations
        yield

    def test_add_rule_endpoint(self):
        resp = self.client.post("/api/v1/sentinel/rules", json={
            "rule": {
                "id": "test-api-rule",
                "name": "API Test Rule",
                "severity": "warning",
                "forbidden_imports": [
                    {"module_pattern": "os", "file_glob": "routes*.py", "reason": "Use config"}
                ],
            },
        })
        assert resp.status_code == 200
        assert resp.json()["registered"] == "test-api-rule"

    def test_list_rules_endpoint(self):
        self.client.post("/api/v1/sentinel/rules", json={
            "rule": {"id": "r1", "name": "R1"},
        })
        resp = self.client.get("/api/v1/sentinel/rules")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_full_scan_endpoint(self):
        self.client.post("/api/v1/sentinel/rules", json={
            "rule": {
                "id": "no-os",
                "name": "No OS",
                "severity": "error",
                "forbidden_imports": [
                    {"module_pattern": "^os$", "file_glob": "routes*.py"}
                ],
            },
        })
        resp = self.client.post("/api/v1/sentinel/scan", json={
            "workspacePath": str(self.workspace),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["filesScanned"] >= 2
        assert "violations" in data

    def test_delta_scan_endpoint(self):
        # First do a full scan to initialize
        self.client.post("/api/v1/sentinel/rules", json={
            "rule": {
                "id": "no-os",
                "name": "No OS",
                "severity": "error",
                "forbidden_imports": [
                    {"module_pattern": "^os$", "file_glob": "routes*.py"}
                ],
            },
        })
        self.client.post("/api/v1/sentinel/scan", json={
            "workspacePath": str(self.workspace),
        })
        routes_file = str(self.workspace / "routes.py")
        resp = self.client.post("/api/v1/sentinel/scan-delta", json={
            "files": [routes_file],
        })
        assert resp.status_code == 200

    def test_no_sentinel_error(self):
        resp = self.client.post("/api/v1/sentinel/scan-delta", json={
            "files": ["x.py"],
        })
        assert resp.status_code == 409

    def test_suggest_endpoint(self):
        self.client.post("/api/v1/sentinel/rules", json={
            "rule": {
                "id": "no-os",
                "name": "No OS",
                "severity": "error",
                "forbidden_imports": [
                    {"module_pattern": "^os$", "file_glob": "routes*.py", "reason": "Use config"}
                ],
            },
        })
        self.client.post("/api/v1/sentinel/scan", json={
            "workspacePath": str(self.workspace),
        })
        resp = self.client.get("/api/v1/sentinel/suggest/0")
        if resp.status_code == 200:
            data = resp.json()
            assert "action" in data


# ═══════════════════════════════════════════════════════════════════════════
# Integration: Sentinel → full pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_boundary_violation_detected(self, workspace_with_violations):
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
        indexer = SymbolIndexer()
        dm = indexer.index_workspace(str(workspace_with_violations), use_cache=False)

        rule = ArchitecturalRule(
            id="no-env-in-routes",
            name="No os.environ in Routes",
            severity="error",
            forbidden_imports=[
                ForbiddenImport(
                    module_pattern=r"^os$",
                    file_glob="routes*.py",
                    reason="Use the config module.",
                ),
            ],
        )
        reg = RuleRegistry()
        reg.register(rule)
        sentinel = Sentinel(reg, dm)
        result = sentinel.scan_full()

        assert not result.clean
        routes_violations = [v for v in result.violations if "routes" in v.file_path]
        assert len(routes_violations) >= 1
        assert routes_violations[0].severity == "error"

        # Suggest fix
        fix = sentinel.suggest_fix(routes_violations[0])
        assert fix["action"] == "replace_import"
        assert fix["automatable"]
        assert "config module" in fix["description"]

    def test_clean_workspace(self, tmp_path):
        (tmp_path / "clean.py").write_text("def hello():\n    return 'world'\n")
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
        indexer = SymbolIndexer()
        dm = indexer.index_workspace(str(tmp_path), use_cache=False)

        rule = ArchitecturalRule(
            id="no-os",
            name="No OS",
            severity="error",
            forbidden_imports=[
                ForbiddenImport(module_pattern="^os$", file_glob="routes*.py"),
            ],
        )
        reg = RuleRegistry()
        reg.register(rule)
        sentinel = Sentinel(reg, dm)
        result = sentinel.scan_full()
        assert result.clean

    def test_naming_violation_and_fix(self, workspace_with_violations):
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer
        indexer = SymbolIndexer()
        dm = indexer.index_workspace(str(workspace_with_violations), use_cache=False)

        rule = ArchitecturalRule(
            id="snake-funcs",
            name="Snake Case",
            severity="warning",
            naming_conventions=[
                NamingConvention(
                    pattern=r"^[a-z_][a-z0-9_]*$",
                    symbol_type="function",
                    file_glob="*.py",
                    reason="PEP 8: use snake_case.",
                ),
            ],
        )
        reg = RuleRegistry()
        reg.register(rule)
        sentinel = Sentinel(reg, dm)
        result = sentinel.scan_full()

        camel = [v for v in result.violations if v.symbol_name == "fetchData"]
        assert len(camel) >= 1

        fix = sentinel.suggest_fix(camel[0])
        assert fix["action"] == "rename_symbol"
        assert "PEP 8" in fix["description"]

    def test_sentinel_with_dashboard(self, workspace_with_violations):
        from code4u.interfaces.cli.dashboard import DriftWarning, WarRoomDashboard
        from code4u.code_intelligence.knowledge_graph.symbol_indexer import SymbolIndexer

        indexer = SymbolIndexer()
        dm = indexer.index_workspace(str(workspace_with_violations), use_cache=False)

        rule = ArchitecturalRule(
            id="no-os-routes",
            name="No OS in Routes",
            severity="error",
            forbidden_imports=[
                ForbiddenImport(module_pattern=r"^os$", file_glob="routes*.py"),
            ],
        )
        reg = RuleRegistry()
        reg.register(rule)

        dash = WarRoomDashboard(workspace=str(workspace_with_violations))

        def on_violation(v):
            dash.add_drift_warning(DriftWarning(
                rule_id=v.rule_id,
                rule_name=v.rule_name,
                severity=v.severity,
                file_path=v.file_path,
                message=v.message,
            ))

        sentinel = Sentinel(reg, dm, on_violation=on_violation)
        sentinel.scan_full()
        assert len(dash.state.drift_warnings) >= 1
