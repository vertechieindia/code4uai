"""Day 4 test suite — Project Management, Analytics & Nexus Knowledge.

Covers:
  - Project CRUD (POST, GET, DELETE /api/v1/projects)
  - Project re-indexing (POST /api/v1/projects/{id}/index)
  - Health summary endpoint
  - Analytics summary, recent, heatmap
  - Auth enforcement on all project routes
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from code4u.interfaces.api.app import app
from code4u.interfaces.api.deps import _auth_manager

client = TestClient(app)


@pytest.fixture
def auth_headers() -> dict:
    mgr = _auth_manager()
    email = "project-test@code4u.ai"
    try:
        mgr.register(email, "testpass", name="ProjectBot")
    except ValueError:
        pass
    token = mgr.authenticate(email, "testpass")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_workspace(tmp_path):
    """Create a minimal Python workspace for indexing."""
    ws = tmp_path / "sample_project"
    ws.mkdir()
    (ws / "main.py").write_text("def hello():\n    return 'world'\n")
    (ws / "utils.py").write_text("import os\n\ndef get_path():\n    return os.getcwd()\n")
    (ws / "README.md").write_text("# Sample\n")
    return str(ws)


# ===================================================================
# 1. Project CRUD
# ===================================================================

class TestProjectCRUD:

    def test_create_project(self, auth_headers, sample_workspace):
        res = client.post("/api/v1/projects", json={
            "name": "test-project",
            "path": sample_workspace,
            "description": "A test project",
        }, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "test-project"
        assert data["path"] == sample_workspace
        assert data["status"] == "indexed"
        assert data["healthScore"] >= 0
        assert data["totalFiles"] >= 0
        assert "id" in data

    def test_create_project_invalid_path(self, auth_headers):
        res = client.post("/api/v1/projects", json={
            "name": "bad-project",
            "path": "/nonexistent/path/xyz123",
        }, headers=auth_headers)
        assert res.status_code == 404

    def test_list_projects(self, auth_headers, sample_workspace):
        client.post("/api/v1/projects", json={
            "name": "list-test",
            "path": sample_workspace,
        }, headers=auth_headers)

        res = client.get("/api/v1/projects", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "projects" in data
        assert data["total"] >= 1
        names = [p["name"] for p in data["projects"]]
        assert "list-test" in names

    def test_get_project_by_id(self, auth_headers, sample_workspace):
        create_res = client.post("/api/v1/projects", json={
            "name": "get-test",
            "path": sample_workspace,
        }, headers=auth_headers)
        pid = create_res.json()["id"]

        get_res = client.get(f"/api/v1/projects/{pid}", headers=auth_headers)
        assert get_res.status_code == 200
        assert get_res.json()["id"] == pid

    def test_get_unknown_project_404(self, auth_headers):
        res = client.get("/api/v1/projects/nonexistent", headers=auth_headers)
        assert res.status_code == 404

    def test_delete_project(self, auth_headers, sample_workspace):
        create_res = client.post("/api/v1/projects", json={
            "name": "delete-test",
            "path": sample_workspace,
        }, headers=auth_headers)
        pid = create_res.json()["id"]

        del_res = client.delete(f"/api/v1/projects/{pid}", headers=auth_headers)
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True

        get_res = client.get(f"/api/v1/projects/{pid}", headers=auth_headers)
        assert get_res.status_code == 404

    def test_reindex_project(self, auth_headers, sample_workspace):
        create_res = client.post("/api/v1/projects", json={
            "name": "reindex-test",
            "path": sample_workspace,
        }, headers=auth_headers)
        pid = create_res.json()["id"]

        reindex_res = client.post(f"/api/v1/projects/{pid}/index", headers=auth_headers)
        assert reindex_res.status_code == 200
        assert reindex_res.json()["status"] == "indexed"

    def test_projects_require_auth(self):
        res = client.get("/api/v1/projects")
        assert res.status_code == 401


# ===================================================================
# 2. Health Summary
# ===================================================================

class TestHealthSummary:

    def test_health_summary_empty(self, auth_headers):
        res = client.get("/api/v1/projects/health-summary", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "projectCount" in data
        assert "avgHealthScore" in data


# ===================================================================
# 3. Analytics API
# ===================================================================

class TestAnalyticsAPI:

    def test_analytics_summary(self, auth_headers):
        res = client.get("/api/v1/analytics/summary", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "totalReviews" in data
        assert "totalSuggestions" in data
        assert "totalMinutesSaved" in data
        assert "humanSummary" in data

    def test_analytics_recent(self, auth_headers):
        res = client.get("/api/v1/analytics/recent?limit=5", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "records" in data
        assert "count" in data

    def test_analytics_heatmap(self, auth_headers):
        res = client.get("/api/v1/analytics/heatmap", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "recipes" in data

    def test_record_audit(self, auth_headers):
        res = client.post("/api/v1/analytics/audit", json={
            "repoName": "test/repo",
            "prId": 42,
            "suggestionsCount": 5,
            "acceptedCount": 3,
            "triggeredRecipes": ["use-pathlib"],
            "filesReviewed": 10,
        }, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["minutesSaved"] > 0

    def test_analytics_summary_after_audit(self, auth_headers):
        client.post("/api/v1/analytics/audit", json={
            "repoName": "org/api",
            "prId": 100,
            "suggestionsCount": 10,
            "acceptedCount": 7,
            "triggeredRecipes": ["f-string"],
        }, headers=auth_headers)

        res = client.get("/api/v1/analytics/summary", headers=auth_headers)
        data = res.json()
        assert data["totalSuggestions"] >= 10
        assert data["totalMinutesSaved"] > 0

    def test_record_acceptance(self, auth_headers):
        res = client.post("/api/v1/analytics/accept", json={
            "repoName": "test/repo",
            "prId": 42,
            "acceptedCount": 2,
        }, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["minutesSaved"] == 10


# ===================================================================
# 4. Project with real indexing
# ===================================================================

class TestProjectIndexing:

    def test_project_indexes_python_files(self, auth_headers, sample_workspace):
        res = client.post("/api/v1/projects", json={
            "name": "py-index-test",
            "path": sample_workspace,
        }, headers=auth_headers)
        data = res.json()
        assert data["totalSymbols"] >= 2  # hello + get_path
        assert "Python" in data["languages"]

    def test_project_health_score_is_reasonable(self, auth_headers, sample_workspace):
        res = client.post("/api/v1/projects", json={
            "name": "health-test",
            "path": sample_workspace,
        }, headers=auth_headers)
        score = res.json()["healthScore"]
        assert 0 <= score <= 100
