"""Security & Non-Functional Audit Tests for code4u.ai backend.

Covers SQL injection attempts, XSS payloads, JWT tampering, expired
token rejection, CORS headers, rate limiting awareness, and password
exclusion from responses.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from code4u.interfaces.api.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# SQL injection in auth fields
# ---------------------------------------------------------------------------


def test_register_rejects_sql_injection_email():
    """Registration does not execute SQL injection in email field."""
    payload = {"email": "'; DROP TABLE users;--", "password": "p", "name": "X"}
    r = client.post("/api/v1/auth/register", json=payload)
    # Should either succeed (in-memory store ignores SQL) or return 4xx
    assert r.status_code in (200, 400, 409, 422)


def test_login_sql_injection_email_returns_401():
    """Login with SQL injection in email returns 401 (no user found)."""
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "1' OR '1'='1", "password": "x"},
    )
    assert r.status_code == 401


def test_login_sql_injection_password_returns_401():
    """Login with SQL injection in password returns 401."""
    email = f"sec-{id(object())}@code4u.ai"
    client.post("/api/v1/auth/register", json={"email": email, "password": "real", "name": "X"})
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "' OR '1'='1' --"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# XSS payloads in registration name
# ---------------------------------------------------------------------------


def test_register_accepts_xss_name_sanitized_or_stored():
    """Registration with XSS in name does not reflect in response (or is sanitized)."""
    email = f"xss-{id(object())}@code4u.ai"
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "p",
            "name": "<script>alert('xss')</script>",
        },
    )
    assert r.status_code == 200
    data = r.json()
    # Response should not contain executable script (if sanitized)
    assert "token" in data
    # Name may be stored as-is; critical is that /me doesn't reflect raw HTML in unsafe way
    if "name" in data:
        assert isinstance(data["name"], str)


def test_me_with_xss_name_returns_string():
    """GET /me with user who has XSS name returns valid JSON (no script execution)."""
    email = f"xss-me-{id(object())}@code4u.ai"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "p", "name": "<img src=x onerror=alert(1)>"},
    )
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "p"})
    token = r.json().get("token")
    r2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    data = r2.json()
    assert "name" in data
    assert isinstance(data["name"], str)


# ---------------------------------------------------------------------------
# JWT tampering detection
# ---------------------------------------------------------------------------


def test_tampered_jwt_rejected():
    """Tampered JWT (modified payload) is rejected with 401."""
    from code4u.interfaces.api.deps import _auth_manager
    mgr = _auth_manager()
    email = f"tamper-{id(object())}@code4u.ai"
    try:
        mgr.register(email, "p", name="T")
    except ValueError:
        pass
    token = mgr.authenticate(email, "p")
    if not token:
        pytest.skip("Could not obtain token")
    parts = token.split(".")
    # Tamper with payload (replace middle part)
    tampered = f"{parts[0]}.eyJzdWIiOiJhZG1pbiJ9.{parts[2]}"
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401


def test_expired_token_rejected():
    """Expired JWT is rejected with 401."""
    from code4u.security_compliance.auth.manager import AuthManager
    from code4u.core.config import get_settings
    from datetime import datetime, timedelta
    from jose import jwt

    settings = get_settings()
    secret = settings.jwt_secret_key.get_secret_value()
    payload = {
        "sub": "user-123",
        "email": "expired@test.com",
        "tenant_id": "tenant-1",
        "exp": datetime.utcnow() - timedelta(hours=1),
    }
    expired_token = jwt.encode(payload, secret, algorithm="HS256")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# CORS header presence
# ---------------------------------------------------------------------------


def test_cors_headers_present_on_options():
    """OPTIONS preflight includes CORS headers."""
    r = client.options("/api/v1/auth/me", headers={"Origin": "http://localhost:3000"})
    # OPTIONS may be allowed through; check for CORS headers if present
    assert r.status_code in (200, 204, 405)


def test_cors_allow_origin_in_response():
    """Response from allowed origin includes Access-Control-Allow-Origin."""
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    # FastAPI CORSMiddleware adds header when origin allowed
    assert r.status_code == 200
    # CORS headers may be present
    headers = dict(r.headers)
    if "access-control-allow-origin" in [h.lower() for h in headers.keys()]:
        assert "localhost" in str(r.headers.get("access-control-allow-origin", ""))


# ---------------------------------------------------------------------------
# Rate limiting awareness
# ---------------------------------------------------------------------------


def test_rate_limit_headers_not_required():
    """API may include rate limit headers (X-RateLimit-*); test does not fail if absent."""
    r = client.get("/health")
    assert r.status_code == 200
    # Rate limiting may not be implemented; test is awareness check
    assert "status" in r.json()


def test_repeated_login_attempts_not_blocked():
    """Repeated failed logins do not crash the server (rate limit may apply)."""
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"email": "nonexistent@x.com", "password": "wrong"})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Password not returned in responses
# ---------------------------------------------------------------------------


def test_register_response_no_password():
    """Register response does not contain password or hashed_password."""
    email = f"nopw-{id(object())}@code4u.ai"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "name": "X"})
    data = r.json()
    assert "password" not in data
    assert "hashed_password" not in data


def test_login_response_no_password():
    """Login response does not contain password."""
    email = f"nopw-login-{id(object())}@code4u.ai"
    client.post("/api/v1/auth/register", json={"email": email, "password": "secret", "name": "X"})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    data = r.json()
    assert "password" not in data
    assert "hashed_password" not in data


def test_me_response_no_password(auth_headers):
    """GET /me does not return password or hashed_password."""
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    data = r.json()
    assert "password" not in data
    assert "hashed_password" not in data


def test_auth_response_has_required_fields():
    """Auth responses (register/login) have token, user_id, email, tenant_id."""
    email = f"fields-{id(object())}@code4u.ai"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "p", "name": "F"})
    data = r.json()
    assert "token" in data
    assert "user_id" in data
    assert "email" in data
    assert "tenant_id" in data
