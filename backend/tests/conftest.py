"""Shared test fixtures for the code4u backend test suite."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from code4u.interfaces.api.app import app
from code4u.interfaces.api.deps import _auth_manager


@pytest.fixture
def auth_token() -> str:
    """Register a test user and return a valid JWT for protected routes."""
    mgr = _auth_manager()
    email = f"test-{id(mgr)}@code4u.ai"
    try:
        mgr.register(email, "testpass", name="TestBot")
    except ValueError:
        pass
    token = mgr.authenticate(email, "testpass")
    return token


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Headers dict with a valid Bearer token for TestClient requests."""
    return {"Authorization": f"Bearer {auth_token}"}
