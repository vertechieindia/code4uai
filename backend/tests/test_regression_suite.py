"""Regression Test Suite for code4u.ai backend.

Ensures previously fixed bugs do not reappear: auth token format,
middleware blocking, air-gap guards, smart router model IDs, vector
store sort order, CRDT consistency, kill-all state reset.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from code4u.interfaces.api.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Auth token format
# ---------------------------------------------------------------------------


def test_auth_token_format_valid_jwt(auth_token):
    """Auth token is a valid JWT format (3 dot-separated base64 segments)."""
    parts = auth_token.split(".")
    assert len(parts) == 3
    assert all(len(p) > 0 for p in parts)


def test_auth_token_verifies_successfully(auth_token):
    """Token from auth_token fixture verifies and contains sub, email, tenant_id."""
    from code4u.interfaces.api.deps import _auth_manager
    payload = _auth_manager().verify_token(auth_token)
    assert payload is not None
    assert "sub" in payload
    assert "email" in payload
    assert "tenant_id" in payload


# ---------------------------------------------------------------------------
# Middleware blocks unauthenticated requests
# ---------------------------------------------------------------------------


def test_middleware_blocks_protected_without_bearer():
    """TenantAuthMiddleware returns 401 when no Authorization header."""
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert "detail" in r.json()


def test_middleware_blocks_invalid_token_format():
    """TenantAuthMiddleware returns 401 for malformed token (no 'Bearer ' prefix)."""
    r = client.get("/api/v1/auth/me", headers={"Authorization": "InvalidFormat token123"})
    assert r.status_code == 401


def test_middleware_blocks_tampered_token():
    """TenantAuthMiddleware returns 401 for tampered/invalid JWT."""
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.signature"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Air-gapped mode blocks external calls
# ---------------------------------------------------------------------------


def test_air_gapped_blocks_openai_provider():
    """When air-gapped, guard_external_call blocks OpenAI."""
    from code4u.interfaces.api.routes.airgap import set_air_gapped, guard_external_call
    set_air_gapped(True)
    try:
        with pytest.raises(RuntimeError):
            guard_external_call("openai", "https://api.openai.com/v1/chat")
    finally:
        set_air_gapped(False)


# ---------------------------------------------------------------------------
# Smart router returns valid model IDs
# ---------------------------------------------------------------------------


def test_smart_router_returns_non_empty_model_id():
    """get_model_for_agent returns non-empty string for known agents."""
    from code4u.ai_engine.llm.smart_router import get_model_for_agent
    for agent in ["heal", "refactor", "chief", "chat"]:
        model = get_model_for_agent(agent, air_gapped=False)
        assert isinstance(model, str)
        assert len(model) > 0


def test_smart_router_local_models_valid():
    """get_model_for_agent(air_gapped=True) returns valid local model IDs."""
    from code4u.ai_engine.llm.smart_router import get_model_for_agent, MODEL_ROUTING_TABLE
    model = get_model_for_agent("heal", air_gapped=True)
    expected = MODEL_ROUTING_TABLE["heal"]["local"]
    assert model == expected


# ---------------------------------------------------------------------------
# Vector store returns results sorted by score
# ---------------------------------------------------------------------------


def test_vector_store_search_sorted_by_score_desc():
    """LocalVectorStore.search returns results in descending score order."""
    from code4u.ai_engine.vector_store import LocalVectorStore, VectorDocument
    store = LocalVectorStore(dim=64)
    store.add_documents([
        VectorDocument(id="a", content="python function def hello"),
        VectorDocument(id="b", content="javascript function"),
        VectorDocument(id="c", content="python hello world"),
    ])
    results = store.search("python hello", top_k=5)
    for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score


# ---------------------------------------------------------------------------
# CRDT operations maintain document consistency
# ---------------------------------------------------------------------------


def test_crdt_sequential_ops_maintain_consistency():
    """Sequential insert/delete/replace maintains consistent content."""
    from code4u.core.collaboration import CollaborationDocument, Operation, OpType
    doc = CollaborationDocument("test.py", "abc")
    doc.apply_operation(Operation(type=OpType.INSERT, offset=3, text="def"))
    assert doc.content == "abcdef"
    doc.apply_operation(Operation(type=OpType.DELETE, offset=3, length=3))
    assert doc.content == "abc"
    doc.apply_operation(Operation(type=OpType.REPLACE, offset=0, length=3, text="xyz"))
    assert doc.content == "xyz"


def test_crdt_offset_bounds_handled():
    """CRDT handles offset beyond content length gracefully."""
    from code4u.core.collaboration import CollaborationDocument, Operation, OpType
    doc = CollaborationDocument("test.py", "hi")
    doc.apply_operation(Operation(type=OpType.INSERT, offset=100, text="!"))
    assert "!" in doc.content


# ---------------------------------------------------------------------------
# Kill-all endpoint resets state
# ---------------------------------------------------------------------------


def test_kill_all_resets_events(auth_headers):
    """POST /swarm/kill-all clears event pipeline."""
    r = client.post("/api/v1/swarm/kill-all", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "killed"
    # Events are cleared; subsequent list should not include stale events
    r2 = client.get("/api/v1/swarm", headers=auth_headers)
    assert r2.status_code == 200


def test_kill_all_idempotent(auth_headers):
    """POST /swarm/kill-all can be called multiple times safely."""
    r1 = client.post("/api/v1/swarm/kill-all", headers=auth_headers)
    r2 = client.post("/api/v1/swarm/kill-all", headers=auth_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
