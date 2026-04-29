"""Tests for Day 15: GitHub PR Automation.

Covers:
  - Webhook signature verification (HMAC-SHA256).
  - PR event parsing (opened, synchronize, ignored actions).
  - Diff patch line mapping.
  - Suggestion block formatting.
  - Review body generation.
  - Pattern-based code checks (print→logger, %→f-string, os.path→pathlib).
  - ReviewComment serialization.
  - FilePatch reviewability.
  - End-to-end review pipeline with mocked GitHub.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from code4u.interfaces.api.routes.webhooks import (
    verify_github_signature,
    parse_pr_event,
)
from code4u.agents.github_reviewer import (
    FilePatch,
    ReviewComment,
    ReviewResult,
    parse_patch_line_map,
    format_suggestion,
    build_review_body,
    _build_pattern_checks,
    _suggest_logger,
    _suggest_pathlib,
    _suggest_fstring_percent,
    GitHubReviewer,
)


# ---------------------------------------------------------------------------
# Test: Signature verification
# ---------------------------------------------------------------------------

class TestSignatureVerification:
    def test_valid_signature(self):
        secret = "my-webhook-secret"
        payload = b'{"action": "opened"}'
        expected_sig = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        assert verify_github_signature(payload, expected_sig, secret) is True

    def test_invalid_signature(self):
        secret = "my-webhook-secret"
        payload = b'{"action": "opened"}'
        assert verify_github_signature(payload, "sha256=bad", secret) is False

    def test_missing_signature_with_secret(self):
        assert verify_github_signature(b"data", "", "secret") is False
        assert verify_github_signature(b"data", None, "secret") is False

    def test_no_secret_always_passes(self):
        assert verify_github_signature(b"anything", "", "") is True
        assert verify_github_signature(b"anything", "sha256=bad", "") is True

    def test_signature_without_sha256_prefix(self):
        secret = "s"
        payload = b"x"
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_github_signature(payload, sig, secret) is False

    def test_timing_safe_comparison(self):
        secret = "secret"
        payload = b'test'
        correct = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        almost = correct[:-1] + ("a" if correct[-1] != "a" else "b")
        assert verify_github_signature(payload, almost, secret) is False


# ---------------------------------------------------------------------------
# Test: PR event parsing
# ---------------------------------------------------------------------------

class TestPREventParsing:
    def _make_payload(self, action="opened", pr_number=42):
        return {
            "action": action,
            "pull_request": {
                "number": pr_number,
                "title": "Fix the thing",
                "html_url": "https://github.com/org/repo/pull/42",
                "head": {"sha": "abc1234def", "ref": "feature-branch"},
                "base": {"ref": "main"},
                "diff_url": "https://github.com/org/repo/pull/42.diff",
                "changed_files": 3,
            },
            "repository": {
                "full_name": "org/repo",
                "clone_url": "https://github.com/org/repo.git",
            },
            "sender": {"login": "developer"},
        }

    def test_opened_event(self):
        result = parse_pr_event(self._make_payload("opened"))
        assert result is not None
        assert result["action"] == "opened"
        assert result["pr_number"] == 42
        assert result["repo_full_name"] == "org/repo"
        assert result["head_sha"] == "abc1234def"
        assert result["sender"] == "developer"

    def test_synchronize_event(self):
        result = parse_pr_event(self._make_payload("synchronize"))
        assert result is not None
        assert result["action"] == "synchronize"

    def test_reopened_event(self):
        result = parse_pr_event(self._make_payload("reopened"))
        assert result is not None

    def test_closed_event_ignored(self):
        result = parse_pr_event(self._make_payload("closed"))
        assert result is None

    def test_labeled_event_ignored(self):
        result = parse_pr_event(self._make_payload("labeled"))
        assert result is None

    def test_missing_pr_ignored(self):
        result = parse_pr_event({"action": "opened"})
        assert result is None

    def test_empty_payload(self):
        result = parse_pr_event({})
        assert result is None


# ---------------------------------------------------------------------------
# Test: Diff patch line mapping
# ---------------------------------------------------------------------------

class TestPatchLineMap:
    def test_simple_addition(self):
        patch = (
            "@@ -1,3 +1,4 @@\n"
            " line 1\n"
            "+new line 2\n"
            " line 3\n"
            " line 4\n"
        )
        line_map = parse_patch_line_map(patch)
        assert 2 in line_map
        assert line_map[2] == "new line 2"

    def test_multiple_additions(self):
        patch = (
            "@@ -1,2 +1,4 @@\n"
            " existing\n"
            "+added1\n"
            "+added2\n"
            " end\n"
        )
        line_map = parse_patch_line_map(patch)
        assert len(line_map) == 2
        assert line_map[2] == "added1"
        assert line_map[3] == "added2"

    def test_deletion_not_in_map(self):
        patch = (
            "@@ -1,3 +1,2 @@\n"
            " keep\n"
            "-removed\n"
            " end\n"
        )
        line_map = parse_patch_line_map(patch)
        assert len(line_map) == 0

    def test_multi_hunk(self):
        patch = (
            "@@ -1,2 +1,3 @@\n"
            " first\n"
            "+added_early\n"
            " second\n"
            "@@ -10,2 +11,3 @@\n"
            " tenth\n"
            "+added_late\n"
            " eleventh\n"
        )
        line_map = parse_patch_line_map(patch)
        assert 2 in line_map
        assert 12 in line_map

    def test_empty_patch(self):
        assert parse_patch_line_map("") == {}


# ---------------------------------------------------------------------------
# Test: Suggestion formatting
# ---------------------------------------------------------------------------

class TestSuggestionFormatting:
    def test_basic_suggestion(self):
        result = format_suggestion(
            original_lines=['print("hello")'],
            replacement_lines=['logger.debug("hello")'],
            recipe_name="Logging",
            explanation="Use structured logging.",
        )
        assert "```suggestion" in result
        assert 'logger.debug("hello")' in result
        assert "**Logging**" in result
        assert "Use structured logging." in result

    def test_suggestion_without_explanation(self):
        result = format_suggestion(
            original_lines=["old"],
            replacement_lines=["new"],
            recipe_name="Fix",
        )
        assert "**Fix**" in result
        assert "```suggestion" in result
        assert "new" in result

    def test_multiline_suggestion(self):
        result = format_suggestion(
            original_lines=["line1", "line2"],
            replacement_lines=["new1", "new2", "new3"],
            recipe_name="Multi",
        )
        assert "new1" in result
        assert "new3" in result


# ---------------------------------------------------------------------------
# Test: Review body generation
# ---------------------------------------------------------------------------

class TestReviewBody:
    def test_no_suggestions(self):
        result = ReviewResult(files_reviewed=5, recipes_matched=3)
        body = build_review_body(result)
        assert "No issues found" in body
        assert "5 file(s)" in body

    def test_with_suggestions(self):
        result = ReviewResult(
            files_reviewed=5,
            recipes_matched=3,
            suggestions=[ReviewComment(path="a.py", body="fix", line=1)],
        )
        body = build_review_body(result)
        assert "1 suggestion(s)" in body
        assert "one click" in body.lower()


# ---------------------------------------------------------------------------
# Test: ReviewComment serialization
# ---------------------------------------------------------------------------

class TestReviewComment:
    def test_single_line(self):
        c = ReviewComment(path="utils.py", body="fix", line=10)
        d = c.to_github_comment()
        assert d["path"] == "utils.py"
        assert d["line"] == 10
        assert "start_line" not in d

    def test_multi_line(self):
        c = ReviewComment(path="main.py", body="fix", start_line=5, line=10)
        d = c.to_github_comment()
        assert d["start_line"] == 5
        assert d["line"] == 10

    def test_same_start_and_line(self):
        c = ReviewComment(path="a.py", body="x", start_line=7, line=7)
        d = c.to_github_comment()
        assert d["line"] == 7
        assert "start_line" not in d


# ---------------------------------------------------------------------------
# Test: FilePatch reviewability
# ---------------------------------------------------------------------------

class TestFilePatch:
    def test_added_with_patch_is_reviewable(self):
        p = FilePatch(filename="new.py", status="added", patch="@@ +1 @@\n+hello")
        assert p.is_reviewable is True

    def test_modified_with_patch_is_reviewable(self):
        p = FilePatch(filename="old.py", status="modified", patch="@@ +1 @@\n+hello")
        assert p.is_reviewable is True

    def test_removed_not_reviewable(self):
        p = FilePatch(filename="gone.py", status="removed", patch="")
        assert p.is_reviewable is False

    def test_modified_no_patch_not_reviewable(self):
        p = FilePatch(filename="empty.py", status="modified", patch="")
        assert p.is_reviewable is False


# ---------------------------------------------------------------------------
# Test: Pattern-based checks
# ---------------------------------------------------------------------------

class TestPatternChecks:
    def test_print_to_logger_pattern(self):
        checks = _build_pattern_checks("replace print with logger.debug calls")
        assert len(checks) >= 1
        matched = [c for c in checks if c["pattern"].search('print("hello")')]
        assert len(matched) == 1

    def test_fstring_pattern(self):
        checks = _build_pattern_checks("convert format() to f-string")
        assert len(checks) >= 1
        matched = [c for c in checks if c["pattern"].search('"hello %s" % name')]
        assert len(matched) >= 1

    def test_pathlib_pattern(self):
        checks = _build_pattern_checks("use pathlib instead of os.path")
        assert len(checks) >= 1
        matched = [c for c in checks if c["pattern"].search("os.path.join(a, b)")]
        assert len(matched) == 1

    def test_no_matching_keywords(self):
        checks = _build_pattern_checks("add documentation comments")
        assert len(checks) == 0


# ---------------------------------------------------------------------------
# Test: Suggest functions
# ---------------------------------------------------------------------------

class TestSuggestFunctions:
    def test_suggest_logger(self):
        result = _suggest_logger('    print("debug info")')
        assert "logger.debug" in result
        assert "print" not in result

    def test_suggest_pathlib_join(self):
        result = _suggest_pathlib("path = os.path.join(a, b)")
        assert "Path" in result
        assert "was: os.path.join" in result

    def test_suggest_pathlib_exists(self):
        result = _suggest_pathlib("if os.path.exists(f):")
        assert ".exists()" in result


# ---------------------------------------------------------------------------
# Test: ReviewResult
# ---------------------------------------------------------------------------

class TestReviewResult:
    def test_has_suggestions_false(self):
        r = ReviewResult()
        assert r.has_suggestions is False

    def test_has_suggestions_true(self):
        r = ReviewResult(suggestions=[ReviewComment(path="a", body="b", line=1)])
        assert r.has_suggestions is True

    def test_to_dict(self):
        r = ReviewResult(
            repo="org/repo",
            pr_number=42,
            head_sha="abc",
            files_reviewed=3,
            recipes_matched=2,
            posted=True,
        )
        d = r.to_dict()
        assert d["repo"] == "org/repo"
        assert d["prNumber"] == 42
        assert d["suggestionsCount"] == 0
        assert d["posted"] is True


# ---------------------------------------------------------------------------
# Test: E2E review pipeline with mocks
# ---------------------------------------------------------------------------

class TestGitHubReviewerE2E:
    def _mock_pr_file(self, filename, status, patch, additions=1, deletions=0, changes=1):
        f = MagicMock()
        f.filename = filename
        f.status = status
        f.patch = patch
        f.additions = additions
        f.deletions = deletions
        f.changes = changes
        return f

    def _mock_recipe(self, recipe_id, file_glob, prompt_template, name=None):
        from code4u.core.recipes import Recipe, RecipeSelector
        return Recipe(
            id=recipe_id,
            name=name or recipe_id,
            description="test",
            prompt_template=prompt_template,
            selector=RecipeSelector(file_glob=file_glob),
        )

    @pytest.mark.asyncio
    async def test_review_finds_print_statements(self):
        patch_content = (
            "@@ -1,3 +1,4 @@\n"
            " import os\n"
            "+print('debug info')\n"
            " def main():\n"
            "     pass\n"
        )

        mock_file = self._mock_pr_file("app.py", "modified", patch_content)
        mock_pr = MagicMock()
        mock_pr.get_files.return_value = [mock_file]

        recipe = self._mock_recipe(
            "no-print", "*.py",
            "Replace print statements with logger.debug calls",
            name="No Print",
        )

        reviewer = GitHubReviewer(github_token="fake", repo_full_name="org/repo")
        reviewer._github = MagicMock()
        reviewer._repo = MagicMock()
        reviewer._repo.get_pull.return_value = mock_pr

        with patch("code4u.agents.github_reviewer.GitHubReviewer._post_review", new_callable=AsyncMock):
            with patch("code4u.core.recipes.RecipeRegistry.list_recipes", return_value=[recipe]):
                with patch("code4u.core.recipes.RecipeRegistry.load"):
                    result = await reviewer.review_pr(pr_number=42, head_sha="abc123")

        assert result.files_reviewed == 1
        assert result.recipes_matched == 1
        assert result.has_suggestions
        assert any("logger.debug" in s.body for s in result.suggestions)

    @pytest.mark.asyncio
    async def test_review_no_matching_files(self):
        mock_file = self._mock_pr_file("style.css", "modified", "@@ +1 @@\n+body {}")
        mock_pr = MagicMock()
        mock_pr.get_files.return_value = [mock_file]

        recipe = self._mock_recipe("py-only", "*.py", "Fix python code")

        reviewer = GitHubReviewer(github_token="fake", repo_full_name="org/repo")
        reviewer._github = MagicMock()
        reviewer._repo = MagicMock()
        reviewer._repo.get_pull.return_value = mock_pr

        with patch("code4u.core.recipes.RecipeRegistry.list_recipes", return_value=[recipe]):
            with patch("code4u.core.recipes.RecipeRegistry.load"):
                result = await reviewer.review_pr(pr_number=1, head_sha="def456")

        assert result.files_reviewed == 1
        assert result.recipes_matched == 0
        assert not result.has_suggestions

    @pytest.mark.asyncio
    async def test_review_css_selector_ignores_py(self):
        py_file = self._mock_pr_file("utils.py", "modified", "@@ +1 @@\n+pass")
        css_file = self._mock_pr_file("app.css", "modified", "@@ +1 @@\n+.btn {}")
        mock_pr = MagicMock()
        mock_pr.get_files.return_value = [py_file, css_file]

        recipe = self._mock_recipe("css-only", "*.css", "Fix CSS naming")

        reviewer = GitHubReviewer(github_token="fake", repo_full_name="org/repo")
        reviewer._github = MagicMock()
        reviewer._repo = MagicMock()
        reviewer._repo.get_pull.return_value = mock_pr

        with patch("code4u.core.recipes.RecipeRegistry.list_recipes", return_value=[recipe]):
            with patch("code4u.core.recipes.RecipeRegistry.load"):
                result = await reviewer.review_pr(pr_number=2, head_sha="ghi789")

        assert result.files_reviewed == 2
        assert result.recipes_matched == 1

    @pytest.mark.asyncio
    async def test_review_detects_os_path(self):
        patch_content = (
            "@@ -1,2 +1,3 @@\n"
            " import os\n"
            "+path = os.path.join(base, name)\n"
            " result = process(path)\n"
        )
        mock_file = self._mock_pr_file("io_utils.py", "modified", patch_content)
        mock_pr = MagicMock()
        mock_pr.get_files.return_value = [mock_file]

        recipe = self._mock_recipe(
            "use-pathlib", "*.py",
            "Use pathlib instead of os.path for all path operations",
            name="Pathlib Migration",
        )

        reviewer = GitHubReviewer(github_token="fake", repo_full_name="org/repo")
        reviewer._github = MagicMock()
        reviewer._repo = MagicMock()
        reviewer._repo.get_pull.return_value = mock_pr

        with patch("code4u.agents.github_reviewer.GitHubReviewer._post_review", new_callable=AsyncMock):
            with patch("code4u.core.recipes.RecipeRegistry.list_recipes", return_value=[recipe]):
                with patch("code4u.core.recipes.RecipeRegistry.load"):
                    result = await reviewer.review_pr(pr_number=10, head_sha="xyz")

        assert result.has_suggestions
        assert any("pathlib" in s.body.lower() for s in result.suggestions)
        assert result.suggestions[0].line == 2
