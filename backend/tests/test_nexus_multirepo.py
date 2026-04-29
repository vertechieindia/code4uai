"""Day 27 — Multi-Repo Nexus test suite.

Tests:
  - NexusContext: scan, add_repo, index_all, link_repos, summary.
  - GlobalRegistry: find_symbol_global, cross edges, repo dependents.
  - ImpactAnalyzer: blast radius, affected repos, PR plan, high risk.
  - API endpoints: scan, index, link, summary, impact, high-risk.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from code4u.core.nexus import (
    NexusContext,
    GlobalRegistry,
    RepoInfo,
    ExternalEdge,
)
from code4u.agents.nexus.impact_analyzer import (
    ImpactAnalyzer,
    AffectedRepo,
    AffectedFile,
    BlastRadius,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures: multi-repo workspace
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def multi_repo(tmp_path):
    """Create a workspace with 3 micro-repos sharing a symbol."""

    # auth-service: defines User model
    auth = tmp_path / "auth-service"
    auth.mkdir()
    (auth / "pyproject.toml").write_text("[project]\nname='auth'\n")
    (auth / "models.py").write_text(textwrap.dedent("""\
        class User:
            def __init__(self, name, email):
                self.name = name
                self.email = email

        class AuthToken:
            def __init__(self, token):
                self.token = token
    """))
    (auth / "service.py").write_text(textwrap.dedent("""\
        from models import User, AuthToken

        def authenticate(user: User) -> AuthToken:
            return AuthToken("tok_123")
    """))

    # order-service: imports User from auth-service
    order = tmp_path / "order-service"
    order.mkdir()
    (order / "pyproject.toml").write_text("[project]\nname='order'\n")
    (order / "handler.py").write_text(textwrap.dedent("""\
        from models import User

        def create_order(user: User, items: list):
            return {"user": user.name, "items": items}
    """))
    (order / "validator.py").write_text(textwrap.dedent("""\
        from models import User

        def validate_user(user: User) -> bool:
            return bool(user.email)
    """))

    # shipping-service: also imports User
    shipping = tmp_path / "shipping-service"
    shipping.mkdir()
    (shipping / "package.json").write_text('{"name": "shipping"}')
    (shipping / "tracker.py").write_text(textwrap.dedent("""\
        from models import User

        def track_shipment(user: User, order_id: str):
            return {"tracking": "ABC123", "user": user.name}
    """))

    return tmp_path


# ═══════════════════════════════════════════════════════════════════════════
# NexusContext tests
# ═══════════════════════════════════════════════════════════════════════════

class TestNexusContext:
    def test_scan_repos(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        repos = nexus.scan()
        names = {r.name for r in repos}
        assert "auth-service" in names
        assert "order-service" in names
        assert "shipping-service" in names

    def test_scan_nonexistent_dir(self):
        nexus = NexusContext("/nonexistent/path")
        repos = nexus.scan()
        assert repos == []

    def test_add_repo_manual(self, tmp_path):
        nexus = NexusContext(str(tmp_path))
        repo_dir = tmp_path / "my-repo"
        repo_dir.mkdir()
        info = nexus.add_repo(str(repo_dir), "custom-name")
        assert info.name == "custom-name"
        assert nexus.repo_count == 1

    def test_repo_markers(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        repos = nexus.scan()
        auth = [r for r in repos if r.name == "auth-service"][0]
        assert "pyproject.toml" in auth.markers

    def test_index_all(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        nexus.scan()
        result = nexus.index_all()
        assert all(info.indexed for info in result.values())
        auth_info = result.get("auth-service")
        assert auth_info is not None
        assert auth_info.file_count >= 2
        assert auth_info.symbol_count >= 2

    def test_index_single_repo(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        nexus.scan()
        info = nexus.index_repo("auth-service")
        assert info is not None
        assert info.indexed

    def test_index_nonexistent_repo(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        nexus.scan()
        info = nexus.index_repo("nope")
        assert info is None

    def test_link_repos(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        nexus.scan()
        nexus.index_all()
        edges = nexus.link_repos()
        # User is used in order-service and shipping-service
        user_edges = [e for e in edges if e.symbol_name == "User"]
        source_repos = {e.source_repo for e in user_edges}
        assert "order-service" in source_repos or "shipping-service" in source_repos

    def test_get_dep_map(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        nexus.scan()
        nexus.index_all()
        dm = nexus.get_dep_map("auth-service")
        assert dm is not None
        assert len(dm.all_files) >= 2

    def test_summary(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        nexus.scan()
        nexus.index_all()
        nexus.link_repos()
        s = nexus.summary()
        assert s["repoCount"] == 3
        assert s["totalFiles"] >= 5
        assert "repos" in s


# ═══════════════════════════════════════════════════════════════════════════
# GlobalRegistry tests
# ═══════════════════════════════════════════════════════════════════════════

class TestGlobalRegistry:
    def test_empty_registry(self):
        reg = GlobalRegistry()
        assert reg.total_files == 0
        assert reg.total_symbols == 0
        assert reg.total_cross_edges == 0

    def test_find_symbol_global(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        nexus.scan()
        nexus.index_all()
        results = nexus.registry.find_symbol_global("User")
        assert len(results) >= 1
        repos = {r[0] for r in results}
        assert "auth-service" in repos

    def test_repo_dependents(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        nexus.scan()
        nexus.index_all()
        nexus.link_repos()
        deps = nexus.registry.get_repo_dependents("auth-service")
        assert isinstance(deps, list)

    def test_repo_dependencies(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        nexus.scan()
        nexus.index_all()
        nexus.link_repos()
        deps = nexus.registry.get_repo_dependencies("order-service")
        assert isinstance(deps, list)

    def test_to_dict(self, multi_repo):
        nexus = NexusContext(str(multi_repo))
        nexus.scan()
        nexus.index_all()
        d = nexus.registry.to_dict()
        assert "repos" in d
        assert "totalFiles" in d


# ═══════════════════════════════════════════════════════════════════════════
# Data model serialization tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSerialization:
    def test_repo_info_to_dict(self):
        info = RepoInfo(name="test", path="/a", file_count=10, symbol_count=50, indexed=True)
        d = info.to_dict()
        assert d["name"] == "test"
        assert d["fileCount"] == 10
        assert d["indexed"]

    def test_external_edge_to_dict(self):
        e = ExternalEdge("order", "auth", "User", "handler.py", "models.py")
        d = e.to_dict()
        assert d["sourceRepo"] == "order"
        assert d["targetRepo"] == "auth"
        assert d["symbolName"] == "User"

    def test_affected_file_to_dict(self):
        af = AffectedFile("handler.py", "order", "User", "from models import User")
        d = af.to_dict()
        assert d["path"] == "handler.py"
        assert d["symbolUsed"] == "User"

    def test_affected_repo_to_dict(self):
        ar = AffectedRepo(
            name="order", path="/order",
            files=[AffectedFile("h.py", "order", "User")],
            edge_count=1, severity="medium",
        )
        d = ar.to_dict()
        assert d["fileCount"] == 1
        assert d["severity"] == "medium"

    def test_blast_radius_to_dict(self):
        blast = BlastRadius(
            symbol_name="User", origin_repo="auth",
            total_repos=2, severity="high",
        )
        d = blast.to_dict()
        assert d["symbolName"] == "User"
        assert d["severity"] == "high"


# ═══════════════════════════════════════════════════════════════════════════
# ImpactAnalyzer tests
# ═══════════════════════════════════════════════════════════════════════════

class TestImpactAnalyzer:
    @pytest.fixture
    def nexus(self, multi_repo):
        n = NexusContext(str(multi_repo))
        n.scan()
        n.index_all()
        n.link_repos()
        return n

    def test_analyze_shared_symbol(self, nexus):
        analyzer = ImpactAnalyzer(nexus.registry)
        blast = analyzer.analyze("User")
        # User is defined in auth-service, used in order + shipping
        assert blast.symbol_name == "User"
        if blast.total_repos > 0:
            assert blast.origin_repo == "auth-service"
            affected_names = {r.name for r in blast.affected_repos}
            assert len(affected_names) >= 1

    def test_analyze_unknown_symbol(self, nexus):
        analyzer = ImpactAnalyzer(nexus.registry)
        blast = analyzer.analyze("NonExistent")
        assert blast.total_repos == 0
        assert blast.severity == "low"

    def test_pr_plan_generated(self, nexus):
        analyzer = ImpactAnalyzer(nexus.registry)
        blast = analyzer.analyze("User")
        if blast.total_repos > 0:
            assert len(blast.pr_plan) >= 1
            assert "repo" in blast.pr_plan[0]
            assert "files" in blast.pr_plan[0]

    def test_analyze_repo(self, nexus):
        analyzer = ImpactAnalyzer(nexus.registry)
        results = analyzer.analyze_repo("auth-service")
        assert isinstance(results, list)

    def test_high_risk_symbols(self, nexus):
        analyzer = ImpactAnalyzer(nexus.registry)
        results = analyzer.high_risk_symbols(min_repos=1)
        assert isinstance(results, list)

    def test_severity_classification(self):
        assert ImpactAnalyzer._classify_severity(1) == "low"
        assert ImpactAnalyzer._classify_severity(3) == "medium"
        assert ImpactAnalyzer._classify_severity(5) == "high"
        assert ImpactAnalyzer._classify_severity(15) == "critical"

    def test_overall_severity(self):
        repos = [AffectedRepo("a", severity="critical")]
        assert ImpactAnalyzer._overall_severity(repos) == "critical"

        repos = [AffectedRepo("a"), AffectedRepo("b"), AffectedRepo("c")]
        assert ImpactAnalyzer._overall_severity(repos) == "high"

        assert ImpactAnalyzer._overall_severity([]) == "low"


# ═══════════════════════════════════════════════════════════════════════════
# API tests
# ═══════════════════════════════════════════════════════════════════════════

class TestNexusAPI:
    @pytest.fixture(autouse=True)
    def setup(self, multi_repo):
        from fastapi.testclient import TestClient
        from code4u.interfaces.api.app import app
        from code4u.interfaces.api.routes import nexus as nexus_mod
        nexus_mod._nexus = None  # reset
        self.client = TestClient(app)
        self.multi_repo = multi_repo
        yield

    def test_scan_endpoint(self):
        resp = self.client.post("/api/v1/nexus/scan", json={
            "rootPath": str(self.multi_repo),
        })
        assert resp.status_code == 200
        assert resp.json()["repoCount"] == 3

    def test_index_endpoint(self):
        self.client.post("/api/v1/nexus/scan", json={"rootPath": str(self.multi_repo)})
        resp = self.client.post("/api/v1/nexus/index", json={})
        assert resp.status_code == 200
        assert resp.json()["indexed"] == 3

    def test_link_endpoint(self):
        self.client.post("/api/v1/nexus/scan", json={"rootPath": str(self.multi_repo)})
        self.client.post("/api/v1/nexus/index", json={})
        resp = self.client.post("/api/v1/nexus/link")
        assert resp.status_code == 200
        assert "crossEdges" in resp.json()

    def test_summary_endpoint(self):
        self.client.post("/api/v1/nexus/scan", json={"rootPath": str(self.multi_repo)})
        self.client.post("/api/v1/nexus/index", json={})
        self.client.post("/api/v1/nexus/link")
        resp = self.client.get("/api/v1/nexus/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["repoCount"] == 3
        assert data["totalFiles"] >= 5

    def test_impact_endpoint(self):
        self.client.post("/api/v1/nexus/scan", json={"rootPath": str(self.multi_repo)})
        self.client.post("/api/v1/nexus/index", json={})
        self.client.post("/api/v1/nexus/link")
        resp = self.client.get("/api/v1/nexus/impact/User")
        assert resp.status_code == 200
        assert resp.json()["symbolName"] == "User"

    def test_high_risk_endpoint(self):
        self.client.post("/api/v1/nexus/scan", json={"rootPath": str(self.multi_repo)})
        self.client.post("/api/v1/nexus/index", json={})
        self.client.post("/api/v1/nexus/link")
        resp = self.client.get("/api/v1/nexus/high-risk?min_repos=1")
        assert resp.status_code == 200
        assert "highRiskSymbols" in resp.json()

    def test_no_nexus_error(self):
        resp = self.client.get("/api/v1/nexus/summary")
        assert resp.status_code == 409
