"""Day 16 — Admin Dashboard & ROI Analytics test suite.

Tests:
  - ReviewAudit model serialization / deserialization.
  - AuditStore CRUD: record, load_all, load_recent, load_since, clear.
  - Aggregation: summary, recipe_heatmap.
  - ROI math: minutes saved, days saved, adoption rate.
  - Admin toggle: enable/disable recipes, persistence.
  - GitHubReviewer integration: disabled recipes skipped, audits recorded.
  - FastAPI endpoints via TestClient.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from code4u.models.analytics import (
    AuditStore,
    ReviewAudit,
    MINUTES_PER_SUGGESTION,
    MINUTES_PER_WORKDAY,
)
from code4u.interfaces.api.routes.admin import (
    _load_disabled,
    _save_disabled,
    is_recipe_disabled,
    get_disabled_recipes,
    _DISABLED_FILE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_audit(tmp_path):
    """AuditStore backed by a temporary file."""
    audit_file = tmp_path / "test_audit.jsonl"
    return AuditStore(audit_file=audit_file)


@pytest.fixture
def sample_audit():
    return ReviewAudit(
        repo_name="acme/api",
        pr_id=42,
        pr_url="https://github.com/acme/api/pull/42",
        author="alice",
        head_sha="abc123",
        suggestions_count=5,
        accepted_count=3,
        triggered_recipes=["use-pathlib", "no-print"],
        files_reviewed=4,
        review_duration_ms=1234.5,
        timestamp=1700000000.0,
    )


@pytest.fixture
def tmp_disabled(tmp_path):
    """Temporarily redirect the disabled-recipes file."""
    disabled_file = tmp_path / "disabled_recipes.json"
    with patch("code4u.interfaces.api.routes.admin._DISABLED_FILE", disabled_file):
        yield disabled_file


# ═══════════════════════════════════════════════════════════════════════════
# ReviewAudit model tests
# ═══════════════════════════════════════════════════════════════════════════

class TestReviewAudit:
    def test_minutes_saved(self, sample_audit):
        assert sample_audit.minutes_saved == 3 * MINUTES_PER_SUGGESTION

    def test_adoption_rate(self, sample_audit):
        assert sample_audit.adoption_rate == 3 / 5

    def test_adoption_rate_zero_suggestions(self):
        a = ReviewAudit(repo_name="x", pr_id=1, suggestions_count=0)
        assert a.adoption_rate == 0.0

    def test_to_dict_round_trip(self, sample_audit):
        d = sample_audit.to_dict()
        rebuilt = ReviewAudit.from_dict(d)
        assert rebuilt.repo_name == sample_audit.repo_name
        assert rebuilt.pr_id == sample_audit.pr_id
        assert rebuilt.author == sample_audit.author
        assert rebuilt.suggestions_count == sample_audit.suggestions_count
        assert rebuilt.accepted_count == sample_audit.accepted_count
        assert rebuilt.triggered_recipes == sample_audit.triggered_recipes

    def test_to_dict_has_camel_keys(self, sample_audit):
        d = sample_audit.to_dict()
        assert "repoName" in d
        assert "prId" in d
        assert "suggestionsCount" in d
        assert "adoptionRate" in d
        assert "minutesSaved" in d

    def test_from_dict_snake_case_fallback(self):
        data = {
            "repo_name": "org/repo",
            "pr_id": 7,
            "suggestions_count": 10,
            "accepted_count": 6,
        }
        a = ReviewAudit.from_dict(data)
        assert a.repo_name == "org/repo"
        assert a.pr_id == 7
        assert a.suggestions_count == 10

    def test_default_status(self):
        a = ReviewAudit(repo_name="x", pr_id=1)
        assert a.status == "completed"

    def test_timestamp_auto(self):
        before = time.time()
        a = ReviewAudit(repo_name="x", pr_id=1)
        after = time.time()
        assert before <= a.timestamp <= after


# ═══════════════════════════════════════════════════════════════════════════
# AuditStore tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAuditStore:
    def test_record_and_load(self, tmp_audit, sample_audit):
        tmp_audit.record(sample_audit)
        records = tmp_audit.load_all()
        assert len(records) == 1
        assert records[0].repo_name == "acme/api"
        assert records[0].pr_id == 42

    def test_multiple_records(self, tmp_audit):
        for i in range(5):
            tmp_audit.record(
                ReviewAudit(repo_name=f"org/repo{i}", pr_id=i, suggestions_count=i)
            )
        assert len(tmp_audit.load_all()) == 5

    def test_load_recent_limit(self, tmp_audit):
        for i in range(10):
            tmp_audit.record(
                ReviewAudit(
                    repo_name="org/repo",
                    pr_id=i,
                    timestamp=1700000000.0 + i,
                )
            )
        recent = tmp_audit.load_recent(limit=3)
        assert len(recent) == 3
        assert recent[0].pr_id == 9  # most recent first

    def test_load_since(self, tmp_audit):
        for i in range(5):
            tmp_audit.record(
                ReviewAudit(repo_name="org/repo", pr_id=i, timestamp=100.0 + i)
            )
        since = tmp_audit.load_since(103.0)
        assert len(since) == 2
        assert {r.pr_id for r in since} == {3, 4}

    def test_clear(self, tmp_audit, sample_audit):
        tmp_audit.record(sample_audit)
        tmp_audit.clear()
        assert tmp_audit.load_all() == []

    def test_empty_store(self, tmp_audit):
        assert tmp_audit.load_all() == []
        assert tmp_audit.load_recent() == []

    def test_corrupted_line_skipped(self, tmp_audit, sample_audit):
        tmp_audit.record(sample_audit)
        with open(tmp_audit._file, "a") as f:
            f.write("NOT VALID JSON\n")
        records = tmp_audit.load_all()
        assert len(records) == 1  # corrupted line skipped


# ═══════════════════════════════════════════════════════════════════════════
# Aggregation & ROI math tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAggregation:
    def _populate(self, store):
        audits = [
            ReviewAudit(
                repo_name="acme/api",
                pr_id=1,
                author="alice",
                suggestions_count=10,
                accepted_count=7,
                triggered_recipes=["use-pathlib", "no-print"],
                files_reviewed=6,
                timestamp=1700000000.0,
            ),
            ReviewAudit(
                repo_name="acme/web",
                pr_id=2,
                author="bob",
                suggestions_count=4,
                accepted_count=4,
                triggered_recipes=["no-print"],
                files_reviewed=2,
                timestamp=1700001000.0,
            ),
            ReviewAudit(
                repo_name="acme/api",
                pr_id=3,
                author="alice",
                suggestions_count=6,
                accepted_count=2,
                triggered_recipes=["use-pathlib", "async-await"],
                files_reviewed=3,
                timestamp=1700002000.0,
            ),
        ]
        for a in audits:
            store.record(a)
        return audits

    def test_summary_totals(self, tmp_audit):
        self._populate(tmp_audit)
        s = tmp_audit.summary()
        assert s["totalReviews"] == 3
        assert s["totalSuggestions"] == 20  # 10+4+6
        assert s["totalAccepted"] == 13  # 7+4+2
        assert s["totalFilesReviewed"] == 11  # 6+2+3

    def test_roi_minutes_saved(self, tmp_audit):
        self._populate(tmp_audit)
        s = tmp_audit.summary()
        expected_minutes = 13 * MINUTES_PER_SUGGESTION
        assert s["totalMinutesSaved"] == expected_minutes

    def test_roi_days_saved(self, tmp_audit):
        self._populate(tmp_audit)
        s = tmp_audit.summary()
        expected_days = round(13 * MINUTES_PER_SUGGESTION / MINUTES_PER_WORKDAY, 2)
        assert s["totalDaysSaved"] == expected_days

    def test_adoption_rate(self, tmp_audit):
        self._populate(tmp_audit)
        s = tmp_audit.summary()
        assert s["adoptionRate"] == round(13 / 20, 3)

    def test_per_repo_breakdown(self, tmp_audit):
        self._populate(tmp_audit)
        s = tmp_audit.summary()
        repos = s["repos"]
        assert "acme/api" in repos
        assert "acme/web" in repos
        assert repos["acme/api"]["reviews"] == 2
        assert repos["acme/web"]["reviews"] == 1
        assert repos["acme/api"]["suggestions"] == 16  # 10+6
        assert repos["acme/web"]["accepted"] == 4

    def test_top_recipes(self, tmp_audit):
        self._populate(tmp_audit)
        s = tmp_audit.summary()
        top = s["topRecipes"]
        ids = [t["recipeId"] for t in top]
        assert "use-pathlib" in ids
        assert "no-print" in ids

    def test_recipe_heatmap_order(self, tmp_audit):
        self._populate(tmp_audit)
        heatmap = tmp_audit.recipe_heatmap()
        # use-pathlib appears in 2 records, no-print in 2, async-await in 1
        assert heatmap[0]["triggerCount"] >= heatmap[-1]["triggerCount"]

    def test_author_stats(self, tmp_audit):
        self._populate(tmp_audit)
        s = tmp_audit.summary()
        assert s["authorStats"]["alice"]["reviews"] == 2
        assert s["authorStats"]["bob"]["reviews"] == 1
        assert s["authorStats"]["alice"]["suggestions"] == 16
        assert s["authorStats"]["bob"]["accepted"] == 4

    def test_period_bounds(self, tmp_audit):
        self._populate(tmp_audit)
        s = tmp_audit.summary()
        assert s["period"]["from"] == 1700000000.0
        assert s["period"]["to"] == 1700002000.0

    def test_summary_empty_store(self, tmp_audit):
        s = tmp_audit.summary()
        assert s["totalReviews"] == 0
        assert s["totalMinutesSaved"] == 0.0
        assert s["totalDaysSaved"] == 0.0

    def test_summary_with_since(self, tmp_audit):
        self._populate(tmp_audit)
        s = tmp_audit.summary(since_ts=1700001500.0)
        assert s["totalReviews"] == 1
        assert s["totalSuggestions"] == 6


# ═══════════════════════════════════════════════════════════════════════════
# Admin toggle tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAdminToggle:
    def test_disable_recipe(self, tmp_disabled):
        _save_disabled({"use-pathlib"})
        assert is_recipe_disabled("use-pathlib")
        assert not is_recipe_disabled("no-print")

    def test_enable_recipe(self, tmp_disabled):
        _save_disabled({"use-pathlib", "no-print"})
        disabled = _load_disabled()
        disabled.discard("use-pathlib")
        _save_disabled(disabled)
        assert not is_recipe_disabled("use-pathlib")
        assert is_recipe_disabled("no-print")

    def test_empty_disabled_set(self, tmp_disabled):
        assert get_disabled_recipes() == set()

    def test_persistence(self, tmp_disabled):
        _save_disabled({"a", "b", "c"})
        loaded = _load_disabled()
        assert loaded == {"a", "b", "c"}

    def test_get_disabled_returns_set(self, tmp_disabled):
        _save_disabled({"x"})
        result = get_disabled_recipes()
        assert isinstance(result, set)
        assert "x" in result


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI endpoint tests (via TestClient)
# ═══════════════════════════════════════════════════════════════════════════

class TestAnalyticsAPI:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Redirect the audit store to a temp file for each test."""
        audit_file = tmp_path / "api_audit.jsonl"
        self._store = AuditStore(audit_file=audit_file)
        with patch("code4u.interfaces.api.routes.analytics._store", self._store):
            from fastapi.testclient import TestClient
            from code4u.interfaces.api.app import app
            self.client = TestClient(app)
            yield

    def test_summary_empty(self):
        resp = self.client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalReviews"] == 0
        assert "humanSummary" in data

    def test_record_and_summary(self):
        self.client.post("/api/v1/analytics/audit", json={
            "repoName": "acme/api",
            "prId": 1,
            "suggestionsCount": 8,
            "acceptedCount": 5,
            "triggeredRecipes": ["no-print"],
            "filesReviewed": 3,
        })
        resp = self.client.get("/api/v1/analytics/summary")
        data = resp.json()
        assert data["totalReviews"] == 1
        assert data["totalSuggestions"] == 8
        assert data["totalAccepted"] == 5
        assert data["totalMinutesSaved"] == 5 * MINUTES_PER_SUGGESTION

    def test_human_summary_text(self):
        self.client.post("/api/v1/analytics/audit", json={
            "repoName": "acme/api",
            "prId": 1,
            "suggestionsCount": 4,
            "acceptedCount": 2,
        })
        self.client.post("/api/v1/analytics/audit", json={
            "repoName": "acme/web",
            "prId": 2,
            "suggestionsCount": 6,
            "acceptedCount": 4,
        })
        resp = self.client.get("/api/v1/analytics/summary")
        summary = resp.json()["humanSummary"]
        assert "Code4u saved" in summary
        assert "repositories" in summary

    def test_summary_since_days(self):
        # Record an old audit and a recent one
        self._store.record(ReviewAudit(
            repo_name="old/repo",
            pr_id=1,
            suggestions_count=10,
            timestamp=time.time() - 86400 * 30,  # 30 days ago
        ))
        self._store.record(ReviewAudit(
            repo_name="new/repo",
            pr_id=2,
            suggestions_count=5,
            timestamp=time.time(),
        ))
        resp = self.client.get("/api/v1/analytics/summary?since_days=7")
        data = resp.json()
        assert data["totalReviews"] == 1  # only the recent one
        assert data["totalSuggestions"] == 5

    def test_recent_endpoint(self):
        for i in range(5):
            self.client.post("/api/v1/analytics/audit", json={
                "repoName": "org/repo",
                "prId": i,
                "suggestionsCount": i,
            })
        resp = self.client.get("/api/v1/analytics/recent?limit=3")
        data = resp.json()
        assert data["count"] == 3

    def test_heatmap_endpoint(self):
        self.client.post("/api/v1/analytics/audit", json={
            "repoName": "org/repo",
            "prId": 1,
            "suggestionsCount": 3,
            "triggeredRecipes": ["no-print", "use-pathlib"],
        })
        self.client.post("/api/v1/analytics/audit", json={
            "repoName": "org/repo",
            "prId": 2,
            "suggestionsCount": 2,
            "triggeredRecipes": ["no-print"],
        })
        resp = self.client.get("/api/v1/analytics/heatmap")
        data = resp.json()
        assert data["count"] >= 1
        top = data["recipes"][0]
        assert top["recipeId"] == "no-print"
        assert top["triggerCount"] == 2

    def test_accept_endpoint(self):
        self.client.post("/api/v1/analytics/accept", json={
            "repoName": "org/repo",
            "prId": 5,
            "acceptedCount": 3,
        })
        resp = self.client.get("/api/v1/analytics/summary")
        data = resp.json()
        assert data["totalAccepted"] == 3


class TestAdminAPI:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        disabled_file = tmp_path / "disabled_recipes.json"
        with patch("code4u.interfaces.api.routes.admin._DISABLED_FILE", disabled_file):
            from fastapi.testclient import TestClient
            from code4u.interfaces.api.app import app
            self.client = TestClient(app)
            yield

    def test_toggle_disable(self):
        resp = self.client.patch(
            "/api/v1/admin/recipes/use-pathlib/toggle",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["recipeId"] == "use-pathlib"
        assert data["enabled"] is False
        assert data["action"] == "disabled"

    def test_toggle_enable(self):
        # First disable
        self.client.patch(
            "/api/v1/admin/recipes/use-pathlib/toggle",
            json={"enabled": False},
        )
        # Then enable
        resp = self.client.patch(
            "/api/v1/admin/recipes/use-pathlib/toggle",
            json={"enabled": True},
        )
        data = resp.json()
        assert data["enabled"] is True
        assert data["action"] == "enabled"

    def test_disabled_list(self):
        self.client.patch(
            "/api/v1/admin/recipes/a/toggle", json={"enabled": False},
        )
        self.client.patch(
            "/api/v1/admin/recipes/b/toggle", json={"enabled": False},
        )
        resp = self.client.get("/api/v1/admin/recipes/disabled")
        data = resp.json()
        assert data["count"] == 2
        assert set(data["disabled"]) == {"a", "b"}

    def test_toggle_idempotent(self):
        self.client.patch(
            "/api/v1/admin/recipes/x/toggle", json={"enabled": False},
        )
        self.client.patch(
            "/api/v1/admin/recipes/x/toggle", json={"enabled": False},
        )
        resp = self.client.get("/api/v1/admin/recipes/disabled")
        assert resp.json()["count"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Integration: GitHubReviewer respects disabled recipes
# ═══════════════════════════════════════════════════════════════════════════

class TestReviewerDisabledRecipes:
    """Verify that the GitHubReviewer skips globally disabled recipes."""

    def test_disabled_recipe_skipped(self, tmp_path):
        recipe_dir = tmp_path / ".code4u" / "recipes"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "no-print.yaml").write_text(
            "id: no-print\nname: No Print\n"
            'selector:\n  file_glob: "*.py"\n'
            "prompt_template: Replace print with logger.debug\n"
        )

        disabled_file = tmp_path / "disabled_recipes.json"
        disabled_file.write_text('["no-print"]')

        from code4u.agents.github_reviewer import GitHubReviewer

        reviewer = GitHubReviewer(
            github_token="fake",
            repo_full_name="org/repo",
            recipes_workspace=str(tmp_path),
        )

        mock_github = MagicMock()
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_file = MagicMock()
        mock_file.filename = "app.py"
        mock_file.status = "modified"
        mock_file.patch = "@@ -1,3 +1,3 @@\n-old\n+print('debug')"
        mock_file.additions = 1
        mock_file.deletions = 1
        mock_pr.get_files.return_value = [mock_file]
        mock_pr.user = MagicMock()
        mock_pr.user.login = "test"
        mock_repo.get_pull.return_value = mock_pr
        reviewer._github = mock_github
        reviewer._repo = mock_repo

        import asyncio

        with patch(
            "code4u.interfaces.api.routes.admin._DISABLED_FILE",
            disabled_file,
        ):
            result = asyncio.get_event_loop().run_until_complete(
                reviewer.review_pr(pr_number=1, head_sha="abc")
            )

        assert result.recipes_matched == 0
        assert len(result.suggestions) == 0


# ═══════════════════════════════════════════════════════════════════════════
# ROI formula correctness
# ═══════════════════════════════════════════════════════════════════════════

class TestROIFormula:
    def test_minutes_per_suggestion_constant(self):
        assert MINUTES_PER_SUGGESTION == 5

    def test_workday_minutes_constant(self):
        assert MINUTES_PER_WORKDAY == 480

    def test_12_hours_from_144_accepted(self, tmp_audit):
        """12 hours = 720 minutes = 144 accepted * 5 min each."""
        for i in range(12):
            tmp_audit.record(ReviewAudit(
                repo_name="org/repo",
                pr_id=i,
                suggestions_count=15,
                accepted_count=12,
                triggered_recipes=["test-recipe"],
            ))
        s = tmp_audit.summary()
        assert s["totalAccepted"] == 144
        assert s["totalMinutesSaved"] == 720
        assert s["totalDaysSaved"] == round(720 / 480, 2)  # 1.5 days

    def test_human_readable_report(self, tmp_audit):
        """The goal: 'Code4u saved 12 hours ... across 4 repositories.'"""
        repos = ["org/api", "org/web", "org/mobile", "org/infra"]
        for i, repo in enumerate(repos):
            for j in range(10):
                tmp_audit.record(ReviewAudit(
                    repo_name=repo,
                    pr_id=i * 100 + j,
                    suggestions_count=5,
                    accepted_count=4,
                    triggered_recipes=["style"],
                ))
        s = tmp_audit.summary()
        total_accepted = 4 * 10 * 4  # 160
        expected_hours = round(total_accepted * 5 / 60, 1)  # 13.3 hours
        assert s["totalAccepted"] == total_accepted
        assert len(s["repos"]) == 4
