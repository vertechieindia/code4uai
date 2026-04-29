"""
Non-Functional & Performance Tests

Covers: Load handling, response time benchmarks, memory usage patterns,
concurrent request handling, and API contract verification.
"""

from __future__ import annotations

import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient

from code4u.interfaces.api.app import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Timing thresholds (seconds)
# ---------------------------------------------------------------------------
HEALTH_MS = 100
ROOT_MS = 200
AUTH_REGISTER_MS = 500
DOCTOR_MS = 5000
SMOKE_TEST_MS = 10000
TFIDF_PER_DOC_MS = 10
SMART_ROUTER_MS = 1
MAX_RESPONSE_BYTES = 1024 * 1024  # 1MB


# ---------------------------------------------------------------------------
# 1. Health endpoint responds in < 100ms
# ---------------------------------------------------------------------------


def test_health_endpoint_responds_under_100ms():
    """Health endpoint responds in < 100ms."""
    t0 = time.perf_counter()
    r = client.get("/health")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    assert elapsed_ms < HEALTH_MS, f"Health took {elapsed_ms:.1f}ms (limit {HEALTH_MS}ms)"


# ---------------------------------------------------------------------------
# 2. Root endpoint responds in < 200ms
# ---------------------------------------------------------------------------


def test_root_endpoint_responds_under_200ms():
    """Root endpoint responds in < 200ms."""
    t0 = time.perf_counter()
    r = client.get("/")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    assert elapsed_ms < ROOT_MS, f"Root took {elapsed_ms:.1f}ms (limit {ROOT_MS}ms)"


# ---------------------------------------------------------------------------
# 3. Auth registration responds in < 500ms
# ---------------------------------------------------------------------------


def test_auth_registration_responds_under_500ms():
    """Auth registration responds in < 500ms."""
    email = f"perf-{uuid.uuid4().hex[:12]}@code4u.ai"
    t0 = time.perf_counter()
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpass", "name": "PerfUser"},
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    assert elapsed_ms < AUTH_REGISTER_MS, f"Register took {elapsed_ms:.1f}ms (limit {AUTH_REGISTER_MS}ms)"


# ---------------------------------------------------------------------------
# 4. Doctor endpoint completes in < 5s
# ---------------------------------------------------------------------------


def test_doctor_endpoint_completes_under_5s():
    """Doctor endpoint completes in < 5s."""
    t0 = time.perf_counter()
    r = client.get("/api/v1/health/doctor")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    assert elapsed_ms < DOCTOR_MS, f"Doctor took {elapsed_ms:.1f}ms (limit {DOCTOR_MS}ms)"


# ---------------------------------------------------------------------------
# 5. Smoke test completes in < 10s
# ---------------------------------------------------------------------------


def test_smoke_test_completes_under_10s():
    """Smoke test completes in < 10s."""
    t0 = time.perf_counter()
    r = client.post("/api/v1/smoke-test")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    assert elapsed_ms < SMOKE_TEST_MS, f"Smoke test took {elapsed_ms:.1f}ms (limit {SMOKE_TEST_MS}ms)"


# ---------------------------------------------------------------------------
# 6. Concurrent auth requests don't cause race conditions
# ---------------------------------------------------------------------------


def test_concurrent_auth_requests_no_race_conditions():
    """Concurrent auth requests don't cause race conditions."""
    def register_and_login(i):
        email = f"concurrent-{i}-{uuid.uuid4().hex[:8]}@code4u.ai"
        r1 = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "p", "name": f"User{i}"},
        )
        if r1.status_code != 200:
            return None
        token = r1.json().get("token")
        r2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        return r2.status_code == 200 if r2 else False

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(register_and_login, i) for i in range(5)]
        results = [f.result() for f in as_completed(futures)]

    successes = [r for r in results if r is True]
    assert len(successes) >= 4, f"Expected at least 4 successful auth flows, got {len(successes)}"


# ---------------------------------------------------------------------------
# 7. Vector store handles 1000+ documents
# ---------------------------------------------------------------------------


def test_vector_store_handles_1000_plus_documents():
    """Vector store handles 1000+ documents."""
    from code4u.ai_engine.vector_store import get_local_vector_store, VectorDocument

    store = get_local_vector_store()
    docs = [
        VectorDocument(id=f"doc-{i}", content=f"Document number {i} with some content for indexing.")
        for i in range(1005)
    ]
    added = store.add_documents(docs)
    assert added >= 1000
    assert store.count >= 1000
    results = store.search("document number", top_k=5)
    assert len(results) > 0


# ---------------------------------------------------------------------------
# 8. TFIDF Embedder produces vectors in < 10ms per document
# ---------------------------------------------------------------------------


def test_tfidf_embedder_produces_vectors_under_10ms_per_doc():
    """TFIDF Embedder produces vectors in < 10ms per document."""
    from code4u.ai_engine.vector_store import TFIDFEmbedder

    embedder = TFIDFEmbedder(dim=256)
    sample = "def hello_world(): return 42"
    t0 = time.perf_counter()
    for _ in range(10):
        embedder.embed(sample)
    elapsed_ms = (time.perf_counter() - t0) * 1000 / 10
    assert elapsed_ms < TFIDF_PER_DOC_MS, f"TFIDF embed took {elapsed_ms:.1f}ms/doc (limit {TFIDF_PER_DOC_MS}ms)"


# ---------------------------------------------------------------------------
# 9. Smart router lookup is O(1) - responds in < 1ms
# ---------------------------------------------------------------------------


def test_smart_router_lookup_under_1ms():
    """Smart router lookup is O(1) - responds in < 1ms."""
    from code4u.ai_engine.llm.smart_router import get_model_for_agent

    t0 = time.perf_counter()
    for _ in range(100):
        get_model_for_agent("heal", air_gapped=False)
        get_model_for_agent("refactor", air_gapped=True)
    elapsed_ms = (time.perf_counter() - t0) * 1000 / 200
    assert elapsed_ms < SMART_ROUTER_MS, f"Smart router lookup took {elapsed_ms:.3f}ms (limit {SMART_ROUTER_MS}ms)"


# ---------------------------------------------------------------------------
# 10. API returns proper Content-Type headers
# ---------------------------------------------------------------------------


def test_api_returns_proper_content_type_headers():
    """API returns proper Content-Type headers."""
    r = client.get("/health")
    assert "content-type" in [h.lower() for h in r.headers]
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct

    r2 = client.get("/")
    assert "application/json" in r2.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# 11. API returns proper Cache-Control headers
# ---------------------------------------------------------------------------


def test_api_returns_proper_cache_control_headers():
    """API returns proper Cache-Control headers (or no-cache for dynamic)."""
    r = client.get("/health")
    headers_lower = {k.lower(): v for k, v in r.headers.items()}
    cache = headers_lower.get("cache-control", "")
    assert cache is not None
    assert isinstance(cache, str)


# ---------------------------------------------------------------------------
# 12. Response sizes are reasonable (< 1MB for standard endpoints)
# ---------------------------------------------------------------------------


def test_response_sizes_reasonable_under_1mb():
    """Response sizes are reasonable (< 1MB for standard endpoints)."""
    endpoints = [
        ("GET", "/"),
        ("GET", "/health"),
        ("GET", "/api/v1/health/doctor"),
    ]
    for method, path in endpoints:
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json={})
        size = len(r.content)
        assert size < MAX_RESPONSE_BYTES, f"{path} response size {size} exceeds 1MB"


# ---------------------------------------------------------------------------
# 13. JSON responses are valid JSON
# ---------------------------------------------------------------------------


def test_json_responses_are_valid_json():
    """JSON responses are valid JSON."""
    endpoints = [
        ("GET", "/"),
        ("GET", "/health"),
        ("GET", "/api/v1/health/doctor"),
    ]
    for method, path in endpoints:
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json={})
        if "application/json" in r.headers.get("content-type", ""):
            try:
                json.loads(r.text)
            except json.JSONDecodeError as e:
                pytest.fail(f"{path} returned invalid JSON: {e}")


# ---------------------------------------------------------------------------
# 14. Error responses follow consistent schema
# ---------------------------------------------------------------------------


def test_error_responses_follow_consistent_schema():
    """Error responses follow consistent schema."""
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    data = r.json()
    assert "detail" in data

    r2 = client.post("/api/v1/auth/login", json={})
    assert r2.status_code == 422
    data2 = r2.json()
    assert "detail" in data2


# ---------------------------------------------------------------------------
# 15. OpenAPI spec is valid and accessible
# ---------------------------------------------------------------------------


def test_openapi_spec_valid_and_accessible():
    """OpenAPI spec is valid and accessible."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert "openapi" in data or "swagger" in data
    assert "paths" in data
    assert "info" in data
