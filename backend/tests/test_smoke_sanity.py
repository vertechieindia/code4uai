"""Smoke & Sanity Tests for code4u.ai backend.

Verifies that public endpoints return expected status codes, protected
endpoints return 401 without auth, and critical paths (register→login→me)
work end-to-end.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from code4u.interfaces.api.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Public endpoints return 200
# ---------------------------------------------------------------------------


def test_root_returns_200():
    """GET / returns 200."""
    assert client.get("/").status_code == 200


def test_health_returns_200():
    """GET /health returns 200."""
    assert client.get("/health").status_code == 200


def test_doctor_returns_200():
    """GET /api/v1/health/doctor returns 200."""
    assert client.get("/api/v1/health/doctor").status_code == 200


def test_smoke_test_returns_200():
    """POST /api/v1/smoke-test returns 200."""
    assert client.post("/api/v1/smoke-test").status_code == 200


def test_docs_returns_200():
    """GET /docs returns 200 (OpenAPI UI)."""
    assert client.get("/docs").status_code == 200


def test_openapi_json_returns_200():
    """GET /openapi.json returns 200."""
    assert client.get("/openapi.json").status_code == 200


# ---------------------------------------------------------------------------
# Protected endpoints return 401 without auth
# ---------------------------------------------------------------------------


def test_me_without_auth_returns_401():
    """GET /api/v1/auth/me returns 401 without token."""
    assert client.get("/api/v1/auth/me").status_code == 401


def test_airgap_status_without_auth_returns_401():
    """GET /api/v1/airgap/status returns 401 without token."""
    assert client.get("/api/v1/airgap/status").status_code == 401


def test_models_list_without_auth_returns_401():
    """GET /api/v1/models/ returns 401 without token."""
    assert client.get("/api/v1/models/").status_code == 401


def test_swarm_kill_all_without_auth_returns_401():
    """POST /api/v1/swarm/kill-all returns 401 without token."""
    assert client.get("/api/v1/swarm").status_code == 401


def test_distill_stats_without_auth_returns_401():
    """GET /api/v1/distill/stats returns 401 without token."""
    assert client.get("/api/v1/distill/stats").status_code == 401


def test_collab_active_without_auth_returns_401():
    """GET /api/v1/collab/active returns 401 without token."""
    assert client.get("/api/v1/collab/active").status_code == 401


def test_staging_environments_without_auth_returns_401():
    """GET /api/v1/staging/environments returns 401 without token."""
    assert client.get("/api/v1/staging/environments").status_code == 401


# ---------------------------------------------------------------------------
# Critical path: register → login → access protected route
# ---------------------------------------------------------------------------


def test_register_login_me_flow():
    """Full flow: register, login, then access /me with token."""
    email = f"flow-{id(object())}@code4u.ai"
    r1 = client.post("/api/v1/auth/register", json={"email": email, "password": "p", "name": "Flow"})
    assert r1.status_code == 200
    token = r1.json().get("token")
    assert token

    r2 = client.post("/api/v1/auth/login", json={"email": email, "password": "p"})
    assert r2.status_code == 200

    r3 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 200
    assert r3.json().get("email") == email


def test_health_response_structure():
    """Health endpoint returns status and version."""
    r = client.get("/health")
    data = r.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "version" in data


def test_doctor_returns_readiness_score():
    """Doctor endpoint returns readiness score 0-100."""
    r = client.get("/api/v1/health/doctor")
    data = r.json()
    assert "readinessScore" in data
    assert 0 <= data["readinessScore"] <= 100


def test_smoke_test_overall_status():
    """Smoke test returns PASS, PARTIAL, or FAIL."""
    r = client.post("/api/v1/smoke-test")
    data = r.json()
    assert data["overall"] in ("PASS", "PARTIAL", "FAIL")


def test_root_contains_endpoints():
    """Root response includes endpoints map."""
    r = client.get("/")
    data = r.json()
    assert "endpoints" in data
    assert "health" in data["endpoints"]
    assert "docs" in data["endpoints"]
