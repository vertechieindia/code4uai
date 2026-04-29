"""Comprehensive Integration Tests for code4u.ai API routes.

Uses FastAPI TestClient to exercise full request/response cycles.
Covers auth, health, doctor, smoke, airgap, models, swarm, distill,
collaboration, and staging endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from code4u.interfaces.api.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Root & Health (public)
# ---------------------------------------------------------------------------


def test_get_root_returns_200():
    """GET / returns 200 with platform info."""
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("name") == "code4u.ai"
    assert "endpoints" in data


def test_get_health_returns_200():
    """GET /health returns 200 with status healthy."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "healthy"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_post_register_success():
    """POST /api/v1/auth/register succeeds with new user."""
    email = f"integration-{id(object())}@code4u.ai"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpass123", "name": "Integration Test"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert data.get("email") == email
    assert "user_id" in data
    assert "tenant_id" in data


def test_post_register_duplicate_returns_409():
    """POST /api/v1/auth/register returns 409 for duplicate email."""
    email = f"dup-{id(object())}@code4u.ai"
    client.post("/api/v1/auth/register", json={"email": email, "password": "p", "name": "Dup"})
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "p", "name": "Dup"})
    assert r.status_code == 409


def test_post_login_success():
    """POST /api/v1/auth/login succeeds with valid credentials."""
    email = f"login-{id(object())}@code4u.ai"
    client.post("/api/v1/auth/register", json={"email": email, "password": "testpass", "name": "Login"})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass"})
    assert r.status_code == 200
    assert "token" in r.json()


def test_post_login_wrong_password_returns_401():
    """POST /api/v1/auth/login returns 401 for wrong password."""
    email = f"wrongpw-{id(object())}@code4u.ai"
    client.post("/api/v1/auth/register", json={"email": email, "password": "correct", "name": "X"})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
    assert r.status_code == 401


def test_get_me_with_auth(auth_headers):
    """GET /api/v1/auth/me returns user info with valid token."""
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "email" in data
    assert "user_id" in data
    assert "tenant_id" in data


def test_get_me_without_auth_returns_401():
    """GET /api/v1/auth/me returns 401 without token."""
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Doctor (public)
# ---------------------------------------------------------------------------


def test_get_doctor_returns_200():
    """GET /api/v1/health/doctor returns 200 with readiness score."""
    r = client.get("/api/v1/health/doctor")
    assert r.status_code == 200
    data = r.json()
    assert "readinessScore" in data
    assert "probes" in data
    assert "overall" in data


def test_doctor_readiness_score_in_range():
    """Doctor readiness score is 0-100."""
    r = client.get("/api/v1/health/doctor")
    data = r.json()
    score = data.get("readinessScore", 0)
    assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# Smoke test (public)
# ---------------------------------------------------------------------------


def test_post_smoke_test_returns_200():
    """POST /api/v1/smoke-test returns 200."""
    r = client.post("/api/v1/smoke-test")
    assert r.status_code == 200
    data = r.json()
    assert "overall" in data
    assert "checks" in data
    assert "passed" in data


def test_smoke_test_has_signature_chain():
    """Smoke test response includes signature chain for audit."""
    r = client.post("/api/v1/smoke-test")
    data = r.json()
    assert "signatureChain" in data
    assert isinstance(data["signatureChain"], str)
    assert len(data["signatureChain"]) > 0


# ---------------------------------------------------------------------------
# Airgap (protected)
# ---------------------------------------------------------------------------


def test_get_airgap_status_with_auth(auth_headers):
    """GET /api/v1/airgap/status returns status with auth."""
    r = client.get("/api/v1/airgap/status", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "enabled" in data
    assert "allowedProviders" in data
    assert "blockedDomains" in data


def test_post_airgap_toggle_with_auth(auth_headers):
    """POST /api/v1/airgap/toggle toggles mode with auth."""
    r = client.post("/api/v1/airgap/toggle", headers=auth_headers, json={"enabled": True})
    assert r.status_code == 200
    assert r.json().get("airGapped") is True
    r2 = client.post("/api/v1/airgap/toggle", headers=auth_headers, json={"enabled": False})
    assert r2.json().get("airGapped") is False


# ---------------------------------------------------------------------------
# Models (protected)
# ---------------------------------------------------------------------------


def test_get_models_list_with_auth(auth_headers):
    """GET /api/v1/models/ returns model list with auth."""
    r = client.get("/api/v1/models/", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_post_models_smart_route_with_auth(auth_headers):
    """POST /api/v1/models/smart-route returns routing decision with auth."""
    r = client.post(
        "/api/v1/models/smart-route",
        headers=auth_headers,
        json={"agentType": "heal", "intent": "fix the bug", "airGapped": False},
    )
    assert r.status_code == 200
    data = r.json()
    assert "model" in data
    assert "complexity" in data
    assert "mode" in data


def test_get_models_routing_table_with_auth(auth_headers):
    """GET /api/v1/models/routing-table returns table with auth."""
    r = client.get("/api/v1/models/routing-table", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "routingTable" in data
    assert isinstance(data["routingTable"], dict)


# ---------------------------------------------------------------------------
# Swarm (protected)
# ---------------------------------------------------------------------------


def test_post_swarm_kill_all_with_auth(auth_headers):
    """POST /api/v1/swarm/kill-all returns 200 with auth."""
    r = client.post("/api/v1/swarm/kill-all", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "killed"
    assert "killedGraphs" in data


def test_get_swarm_list_with_auth(auth_headers):
    """GET /api/v1/swarm returns list with auth."""
    r = client.get("/api/v1/swarm", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "graphs" in data
    assert "total" in data


def test_post_swarm_plan_with_auth(auth_headers):
    """POST /api/v1/swarm/plan decomposes goal with auth."""
    r = client.post(
        "/api/v1/swarm/plan",
        headers=auth_headers,
        json={"goal": "Add unit tests for auth", "workspacePath": "/tmp"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "graph" in data
    assert "summary" in data
    assert data["graph"].get("taskCount", 0) >= 0


# ---------------------------------------------------------------------------
# Distillation (protected)
# ---------------------------------------------------------------------------


def test_get_distill_stats_with_auth(auth_headers):
    """GET /api/v1/distill/stats returns stats with auth."""
    r = client.get("/api/v1/distill/stats", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "totalExamples" in data
    assert "byAgent" in data


# ---------------------------------------------------------------------------
# Collaboration (protected)
# ---------------------------------------------------------------------------


def test_get_collab_active_with_auth(auth_headers):
    """GET /api/v1/collab/active returns sessions with auth."""
    r = client.get("/api/v1/collab/active", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "sessions" in data
    assert "totalActive" in data


def test_post_collab_join_with_auth(auth_headers):
    """POST /api/v1/collab/join creates session with auth."""
    path = f"/tmp/collab-test-{id(object())}.py"
    r = client.post(
        "/api/v1/collab/join",
        headers=auth_headers,
        json={"filePath": path, "participantId": "tester", "name": "Test", "initialContent": "# test"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "joined"


# ---------------------------------------------------------------------------
# Staging (protected)
# ---------------------------------------------------------------------------


def test_get_staging_environments_with_auth(auth_headers):
    """GET /api/v1/staging/environments returns list with auth."""
    r = client.get("/api/v1/staging/environments", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "environments" in data
    assert "total" in data


def test_models_smart_route_air_gapped(auth_headers):
    """Smart route with airGapped=True returns local model."""
    r = client.post(
        "/api/v1/models/smart-route",
        headers=auth_headers,
        json={"agentType": "heal", "intent": "", "airGapped": True},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("airGapped") is True
    assert data.get("mode") == "local"


def test_distill_add_example_with_auth(auth_headers):
    """POST /api/v1/distill/add adds example with auth."""
    r = client.post(
        "/api/v1/distill/add",
        headers=auth_headers,
        json={
            "userInput": "refactor x",
            "assistantOutput": "def x(): pass",
            "agentType": "refactor",
            "modelUsed": "gpt-4o-mini",
        },
    )
    assert r.status_code == 200
    assert "status" in r.json()


def test_distill_export_data_with_auth(auth_headers):
    """GET /api/v1/distill/export-data returns data with auth."""
    r = client.get("/api/v1/distill/export-data", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "format" in data
    assert "data" in data


def test_airgap_providers_with_auth(auth_headers):
    """GET /api/v1/airgap/providers returns provider list with auth."""
    r = client.get("/api/v1/airgap/providers", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "airGapped" in data
    assert "models" in data
