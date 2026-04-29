"""Day 1: Security Hardening — integration tests.

Covers:
  - Typing imports are clean across security_compliance/ and change_execution/
  - AuthManager registration and login (bcrypt + JWT)
  - TenantAuthMiddleware blocks unauthenticated requests
  - Protected routes return 401 without a valid token
  - Valid token grants access and sets tenant context
"""
from __future__ import annotations

import importlib
import pytest


# ── Task 1: Typing / import stability ─────────────────────────────

MODULES_TO_IMPORT = [
    "code4u.security_compliance.security.no_ai_zones",
    "code4u.security_compliance.security.rbac",
    "code4u.security_compliance.security.tenant",
    "code4u.security_compliance.security.audit",
    "code4u.security_compliance.security.isolation",
    "code4u.security_compliance.billing.reports",
    "code4u.security_compliance.billing.pricing",
    "code4u.security_compliance.billing.metering",
    "code4u.security_compliance.compliance.monitor",
    "code4u.security_compliance.compliance.controls",
    "code4u.security_compliance.compliance.evidence",
    "code4u.change_execution.validation.diff_validator",
]


@pytest.mark.parametrize("module_path", MODULES_TO_IMPORT)
def test_module_imports_cleanly(module_path: str):
    mod = importlib.import_module(module_path)
    assert mod is not None


# ── Task 2: AuthManager unit tests ────────────────────────────────

from code4u.security_compliance.auth.manager import AuthManager, UserRecord


@pytest.fixture
def auth() -> AuthManager:
    return AuthManager(jwt_secret="test-secret-key-12345")


class TestAuthManager:
    def test_register_creates_user(self, auth: AuthManager):
        user = auth.register("dev@code4u.ai", "SecureP@ss1", name="Dev")
        assert isinstance(user, UserRecord)
        assert user.email == "dev@code4u.ai"
        assert user.name == "Dev"
        assert user.tenant_id.startswith("tenant_")
        assert user.hashed_password != "SecureP@ss1"

    def test_register_duplicate_email_raises(self, auth: AuthManager):
        auth.register("dup@test.com", "pass1")
        with pytest.raises(ValueError, match="email_already_registered"):
            auth.register("dup@test.com", "pass2")

    def test_login_returns_jwt(self, auth: AuthManager):
        auth.register("login@test.com", "MyPass123")
        token = auth.authenticate("login@test.com", "MyPass123")
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 20

    def test_login_wrong_password_returns_none(self, auth: AuthManager):
        auth.register("wrong@test.com", "correct")
        assert auth.authenticate("wrong@test.com", "incorrect") is None

    def test_login_unknown_email_returns_none(self, auth: AuthManager):
        assert auth.authenticate("ghost@test.com", "anything") is None

    def test_token_roundtrip(self, auth: AuthManager):
        auth.register("rt@test.com", "pass")
        token = auth.authenticate("rt@test.com", "pass")
        payload = auth.verify_token(token)
        assert payload is not None
        assert payload["email"] == "rt@test.com"
        assert "tenant_id" in payload

    def test_verify_bad_token_returns_none(self, auth: AuthManager):
        assert auth.verify_token("invalid.token.here") is None

    def test_get_user_by_id(self, auth: AuthManager):
        user = auth.register("byid@test.com", "pass")
        found = auth.get_user_by_id(user.user_id)
        assert found is not None
        assert found.email == "byid@test.com"


# ── Task 3: FastAPI middleware / route tests ───────────────────────

from fastapi.testclient import TestClient
from code4u.interfaces.api.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestAuthRoutes:
    def test_register_endpoint(self, client: TestClient):
        resp = client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "Str0ngP@ss!",
            "name": "Tester",
            "company": "TestCo",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["email"] == "new@example.com"
        assert data["name"] == "Tester"

    def test_login_endpoint(self, client: TestClient):
        client.post("/api/v1/auth/register", json={
            "email": "login-e2e@example.com",
            "password": "pass123",
        })
        resp = client.post("/api/v1/auth/login", json={
            "email": "login-e2e@example.com",
            "password": "pass123",
        })
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_login_bad_credentials(self, client: TestClient):
        resp = client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "wrong",
        })
        assert resp.status_code == 401


class TestMiddleware:
    def test_public_health_no_auth(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_public_docs_no_auth(self, client: TestClient):
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_protected_route_requires_token(self, client: TestClient):
        resp = client.get("/api/v1/refactor/jobs")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Not authenticated"

    def test_protected_route_rejects_bad_token(self, client: TestClient):
        resp = client.get(
            "/api/v1/refactor/jobs",
            headers={"Authorization": "Bearer fake.token.here"},
        )
        assert resp.status_code == 401

    def test_protected_route_accepts_valid_token(self, client: TestClient):
        reg = client.post("/api/v1/auth/register", json={
            "email": "valid@example.com",
            "password": "pass",
        })
        token = reg.json()["token"]
        resp = client.get(
            "/api/v1/refactor/jobs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code != 401

    def test_auth_me_returns_user(self, client: TestClient):
        reg = client.post("/api/v1/auth/register", json={
            "email": "me@example.com",
            "password": "pass",
            "name": "Me",
        })
        token = reg.json()["token"]
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"
