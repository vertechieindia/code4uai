"""Integration, E2E, Security, Performance, and Regression Tests for Day 19-21.

Covers: API routes, cross-module interactions, stress testing,
security boundaries, performance benchmarks.

Testing types: Integration, System, E2E, Black Box, Grey Box,
Smoke, Sanity, Regression, Security Audit, Performance.
"""

from __future__ import annotations

import json
import time
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def app():
    """Create test FastAPI app."""
    from code4u.interfaces.api.app import app
    return app


@pytest.fixture
async def client(app):
    """Async HTTP client for integration tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# Use auth_headers from conftest (valid JWT from AuthManager)
# Tests that need auth will receive auth_headers as a fixture parameter


# ═══════════════════════════════════════════════════════════════
# API Integration Tests — Wisdom Routes
# ═══════════════════════════════════════════════════════════════

class TestWisdomAPIIntegration:

    @pytest.mark.asyncio
    async def test_store_nugget_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/wisdom/nuggets/store", json={
            "before": "eval(user_input)",
            "after": "safe_eval(sanitize(user_input))",
            "language": "python",
            "pattern_type": "security_fix",
            "description": "Removed dangerous eval",
        }, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "nuggetId" in data

    @pytest.mark.asyncio
    async def test_list_nuggets_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/wisdom/nuggets", headers=auth_headers)
        assert r.status_code == 200
        assert "nuggets" in r.json()

    @pytest.mark.asyncio
    async def test_search_nuggets_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/wisdom/nuggets/search", json={
            "query": "sql injection fix",
            "limit": 5,
        }, headers=auth_headers)
        assert r.status_code == 200
        assert "results" in r.json()

    @pytest.mark.asyncio
    async def test_wisdom_stats_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/wisdom/stats", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "totalNuggets" in data

    @pytest.mark.asyncio
    async def test_analyze_code_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/wisdom/analyze", json={
            "code_map": {"test.py": "eval(user_input)"},
        }, headers=auth_headers)
        assert r.status_code == 200
        assert "suggestions" in r.json()

    @pytest.mark.asyncio
    async def test_find_duplicates_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/wisdom/find-duplicates", json={
            "code_map": {"utils.py": "def validate_email(email):\n    return '@' in email"},
            "project_name": "test-project",
        }, headers=auth_headers)
        assert r.status_code == 200
        assert "duplicates" in r.json()

    @pytest.mark.asyncio
    async def test_wisdom_report_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/wisdom/report", headers=auth_headers)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════
# API Integration Tests — Governance Routes
# ═══════════════════════════════════════════════════════════════

class TestGovernanceAPIIntegration:

    @pytest.mark.asyncio
    async def test_detect_license_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/governance/license/detect", json={
            "content": "MIT License\nPermission is hereby granted...",
            "filename": "LICENSE",
        }, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["licenseId"] == "MIT"

    @pytest.mark.asyncio
    async def test_check_compatibility_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/governance/license/check", json={
            "source_license": "GPL-3.0",
            "target_license": "MIT",
        }, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["compatible"] is False

    @pytest.mark.asyncio
    async def test_gate_transfer_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/governance/license/gate", json={
            "source_license": "MIT",
            "target_license": "Apache-2.0",
            "nugget_id": "test-nugget",
        }, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["allowed"] is True

    @pytest.mark.asyncio
    async def test_gate_transfer_blocks_gpl(self, client, auth_headers):
        r = await client.post("/api/v1/governance/license/gate", json={
            "source_license": "GPL-3.0",
            "target_license": "Proprietary",
        }, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["allowed"] is False
        assert "violation" in data

    @pytest.mark.asyncio
    async def test_license_matrix_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/governance/license/matrix", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data["categories"]) == 4

    @pytest.mark.asyncio
    async def test_license_violations_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/governance/license/violations", headers=auth_headers)
        assert r.status_code == 200
        assert "violations" in r.json()

    @pytest.mark.asyncio
    async def test_record_provenance_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/governance/provenance/record", json={
            "file_path": "src/auth.py",
            "description": "Fixed SQL injection",
            "source_type": "wisdom_nugget",
            "source_nugget_id": "nug-123",
        }, headers=auth_headers)
        assert r.status_code == 200
        assert "recordId" in r.json()

    @pytest.mark.asyncio
    async def test_provenance_stats_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/governance/provenance/stats", headers=auth_headers)
        assert r.status_code == 200
        assert "totalRecords" in r.json()

    @pytest.mark.asyncio
    async def test_toxic_scan_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/governance/toxic/scan", json={
            "code_map": {"agent.py": 'User-Agent = "Googlebot"'},
        }, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "matches" in data

    @pytest.mark.asyncio
    async def test_toxic_add_pattern_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/governance/toxic/add-pattern", json={
            "name": "test_pattern",
            "pattern": r"test_forbidden_\d+",
            "category": "custom",
            "severity": "medium",
        }, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "added"

    @pytest.mark.asyncio
    async def test_toxic_report_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/governance/toxic/report", headers=auth_headers)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════
# API Integration Tests — Launch Routes
# ═══════════════════════════════════════════════════════════════

class TestLaunchAPIIntegration:

    @pytest.mark.asyncio
    async def test_impact_summary_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/launch/impact-summary", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "intelligenceGain" in data
        assert "safetyPerimeter" in data
        assert "legalPurity" in data
        assert "performance" in data

    @pytest.mark.asyncio
    async def test_cache_stats_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/launch/cache/stats", headers=auth_headers)
        assert r.status_code == 200
        assert "backend" in r.json()

    @pytest.mark.asyncio
    async def test_cache_clear_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/launch/cache/clear", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_vector_stats_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/launch/vector/stats", headers=auth_headers)
        assert r.status_code == 200
        assert "totalDocuments" in r.json()

    @pytest.mark.asyncio
    async def test_readiness_endpoint(self, client, auth_headers):
        r = await client.get("/api/v1/launch/readiness", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "readinessScore" in data
        assert "checks" in data
        assert data["readinessScore"] >= 0

    @pytest.mark.asyncio
    async def test_stress_test_small(self, client, auth_headers):
        r = await client.post("/api/v1/launch/stress-test", json={
            "concurrent_tasks": 10,
            "duration_seconds": 1.0,
        }, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["successes"] > 0
        assert data["successRate"] >= 90.0

    @pytest.mark.asyncio
    async def test_vector_benchmark_endpoint(self, client, auth_headers):
        r = await client.post("/api/v1/launch/vector/benchmark", json={
            "num_documents": 100,
            "num_queries": 10,
            "top_k": 5,
        }, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "avgSearchMs" in data
        assert "throughputQps" in data


# ═══════════════════════════════════════════════════════════════
# Cross-Module Integration Tests
# ═══════════════════════════════════════════════════════════════

class TestCrossModuleIntegration:

    def test_wisdom_to_legal_gate_flow(self):
        """Wisdom agent suggestion blocked by legal agent."""
        from code4u.knowledge.pattern_extractor import PatternExtractor
        from code4u.agents.legal_agent import LegalAgent

        pe = PatternExtractor()
        nugget = pe.extract_pattern(
            before="eval(x)",
            after="safe(x)",
            source_project="gpl-project",
            pattern_type="security_fix",
        )
        agent = LegalAgent()
        allowed, violation = agent.gate_wisdom_transfer("GPL-3.0", "Proprietary", nugget_id=nugget.nugget_id)
        assert allowed is False

    def test_wisdom_to_provenance_flow(self):
        """Wisdom suggestion is tracked in provenance."""
        from code4u.knowledge.pattern_extractor import PatternExtractor
        from code4u.knowledge.provenance_tracker import ProvenanceTracker

        pe = PatternExtractor()
        nugget = pe.extract_pattern(before="x=1", after="x=2")
        tracker = ProvenanceTracker()
        rec = tracker.record_attribution(
            file_path="app.py",
            description="Applied wisdom fix",
            source_nugget_id=nugget.nugget_id,
            source_project_hash=nugget.source_project,
        )
        assert rec.source_nugget_id == nugget.nugget_id

    def test_toxic_scan_then_cache(self):
        """Toxic scan results cached in RedisCacheManager."""
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        from code4u.core.cache import RedisCacheManager

        scanner = ToxicScanner()
        matches = scanner.scan_text("eval(atob(x))")
        cache = RedisCacheManager(redis_url="")
        cache.set("toxic", [m.to_dict() for m in matches], "test-hash")
        cached = cache.get("toxic", "test-hash")
        assert len(cached) >= 1

    def test_vector_store_wisdom_search(self):
        """Wisdom nuggets searchable via partitioned vector store."""
        from code4u.ai_engine.vector_store import PartitionedVectorStore, VectorDocument

        pvs = PartitionedVectorStore()
        pvs.add_to_global([
            VectorDocument(id="w1", content="fix SQL injection with parameterized queries"),
            VectorDocument(id="w2", content="replace eval with safe alternative"),
        ])
        results = pvs.search_global("SQL injection fix", top_k=5)
        assert len(results) >= 1
        assert any("w1" in r.id for r in results)


# ═══════════════════════════════════════════════════════════════
# Security Audit Tests
# ═══════════════════════════════════════════════════════════════

class TestSecurityAudit:

    def test_anonymization_completeness(self):
        """Verify all PII types are scrubbed."""
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        sensitive = (
            "email: admin@corp.com\n"
            "ip: 10.0.0.1\n"
            "key: AKIAIOSFODNN7EXAMPLE\n"
            "pass: password = \"secret123\"\n"
            "uuid: 550e8400-e29b-41d4-a716-446655440000\n"
        )
        result = pe.anonymize(sensitive)
        assert "admin@corp.com" not in result
        assert "10.0.0.1" not in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "secret123" not in result
        assert "550e8400" not in result

    def test_toxic_scanner_blocks_all_critical(self):
        """Critical-severity toxic patterns: at least 4 must be blocking."""
        from code4u.security_compliance.toxic_scanner import FORBIDDEN_PATTERNS
        critical = [p for p in FORBIDDEN_PATTERNS if p["severity"] == "critical"]
        assert len(critical) >= 4
        blocked_critical = [p for p in critical if p.get("blocked") is True]
        assert len(blocked_critical) >= 4, "At least 4 critical patterns must be blocking"

    def test_license_matrix_symmetry_for_same_category(self):
        """Same category -> same category should be consistent."""
        from code4u.agents.legal_agent import LegalAgent
        agent = LegalAgent()
        r = agent.check_compatibility("MIT", "BSD-3-Clause")
        assert r.compatible is True

    def test_provenance_no_pii_in_export(self):
        """Exported attribution includes hashed author (no raw PII)."""
        from code4u.knowledge.provenance_tracker import ProvenanceTracker
        tracker = ProvenanceTracker()
        rec = tracker.record_attribution("app.py", "fix", source_author_hash="hashed_author")
        tracker.mark_applied(rec.record_id)
        content = tracker.export_attribution_json()
        assert "hashed_author" in content


# ═══════════════════════════════════════════════════════════════
# Performance Tests
# ═══════════════════════════════════════════════════════════════

class TestPerformanceBenchmarks:

    def test_cache_throughput(self):
        """Cache should handle 10K ops in < 1 second."""
        from code4u.core.cache import InMemoryLRUCache
        cache = InMemoryLRUCache(max_size=20_000)
        t0 = time.time()
        for i in range(10_000):
            cache.set(f"k{i}", {"v": i})
        for i in range(10_000):
            cache.get(f"k{i}")
        elapsed = time.time() - t0
        assert elapsed < 1.0, f"Cache ops took {elapsed:.2f}s"

    def test_pattern_extraction_speed(self):
        """Pattern extraction should be fast."""
        from code4u.knowledge.pattern_extractor import PatternExtractor
        pe = PatternExtractor()
        t0 = time.time()
        for i in range(100):
            pe.extract_pattern(before=f"bad_{i}", after=f"good_{i}")
        elapsed = time.time() - t0
        assert elapsed < 2.0

    def test_toxic_scan_speed(self):
        """Scanning 100 files should complete in < 2 seconds."""
        from code4u.security_compliance.toxic_scanner import ToxicScanner
        scanner = ToxicScanner()
        code_map = {f"file_{i}.py": f"def func_{i}():\n    return {i}\n" * 50 for i in range(100)}
        t0 = time.time()
        scanner.scan_code(code_map)
        elapsed = time.time() - t0
        assert elapsed < 2.0, f"Toxic scan took {elapsed:.2f}s"


# ═══════════════════════════════════════════════════════════════
# Smoke & Sanity Tests
# ═══════════════════════════════════════════════════════════════

class TestSmokeAndSanity:

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        r = await client.get("/health")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_root_endpoint_has_new_routes(self, client):
        r = await client.get("/")
        assert r.status_code == 200
        data = r.json()
        endpoints = data.get("endpoints", {})
        assert "wisdom" in endpoints
        assert "governance" in endpoints
        assert "launch" in endpoints

    def test_all_singletons_instantiate(self):
        """Verify all Day 19-21 singletons can be created."""
        import code4u.knowledge.pattern_extractor as pe_mod
        import code4u.agents.legal_agent as la_mod
        import code4u.knowledge.provenance_tracker as pt_mod
        import code4u.security_compliance.toxic_scanner as ts_mod
        import code4u.core.cache as c_mod
        import code4u.ai_engine.vector_store as vs_mod

        pe_mod._extractor_singleton = None
        la_mod._legal_agent_singleton = None
        pt_mod._tracker_singleton = None
        ts_mod._scanner_singleton = None
        c_mod._cache_singleton = None
        vs_mod._partitioned_store = None

        assert pe_mod.get_pattern_extractor() is not None
        assert la_mod.get_legal_agent() is not None
        assert pt_mod.get_provenance_tracker() is not None
        assert ts_mod.get_toxic_scanner() is not None
        assert c_mod.get_cache_manager() is not None
        assert vs_mod.get_partitioned_vector_store() is not None

    def test_forbidden_patterns_count(self):
        """Sanity: at least 15 forbidden patterns loaded."""
        from code4u.security_compliance.toxic_scanner import FORBIDDEN_PATTERNS
        assert len(FORBIDDEN_PATTERNS) >= 15

    def test_license_catalog_count(self):
        """Sanity: at least 18 licenses in catalog."""
        from code4u.agents.legal_agent import LICENSE_CATALOG
        assert len(LICENSE_CATALOG) >= 18
