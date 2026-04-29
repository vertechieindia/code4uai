"""GitHub PR Reviewer — automated recipe-based code review.

Fetches the PR diff from GitHub, maps changed files to the loaded
RecipeRegistry selectors, runs each matching recipe through the
PlanExecutor in dry-run mode (REVIEW_ONLY — no disk writes), and
posts the resulting suggestions as a GitHub Pull Request Review
with inline ``suggestion`` blocks.

Usage::

    reviewer = GitHubReviewer(github_token="ghp_...", repo_full_name="org/repo")
    await reviewer.review_pr(pr_number=42, head_sha="abc1234")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("github_reviewer")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FilePatch:
    """Parsed representation of a single file's diff in a PR."""
    filename: str
    status: str  # added, modified, removed, renamed
    patch: str = ""
    additions: int = 0
    deletions: int = 0
    changes: int = 0

    @property
    def is_reviewable(self) -> bool:
        return self.status in ("added", "modified") and bool(self.patch)


@dataclass
class ReviewComment:
    """A single inline review comment with an optional suggestion."""
    path: str
    body: str
    start_line: Optional[int] = None
    line: int = 0
    side: str = "RIGHT"

    def to_github_comment(self) -> Dict[str, Any]:
        """Convert to the format expected by PyGithub's create_review."""
        comment: Dict[str, Any] = {
            "path": self.path,
            "body": self.body,
            "side": self.side,
        }
        if self.start_line and self.start_line != self.line:
            comment["start_line"] = self.start_line
            comment["line"] = self.line
        else:
            comment["line"] = self.line
        return comment


@dataclass
class ReviewResult:
    """Aggregated result of a PR review."""
    repo: str = ""
    pr_number: int = 0
    head_sha: str = ""
    files_reviewed: int = 0
    recipes_matched: int = 0
    suggestions: List[ReviewComment] = field(default_factory=list)
    summary: str = ""
    posted: bool = False

    @property
    def has_suggestions(self) -> bool:
        return len(self.suggestions) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo": self.repo,
            "prNumber": self.pr_number,
            "headSha": self.head_sha,
            "filesReviewed": self.files_reviewed,
            "recipesMatched": self.recipes_matched,
            "suggestionsCount": len(self.suggestions),
            "posted": self.posted,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------

_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_pr_files(pr_files) -> List[FilePatch]:
    """Convert PyGithub PaginatedList of files into FilePatch objects."""
    patches: List[FilePatch] = []
    for f in pr_files:
        patches.append(FilePatch(
            filename=f.filename,
            status=f.status,
            patch=f.patch or "",
            additions=f.additions,
            deletions=f.deletions,
            changes=f.changes,
        ))
    return patches


def parse_patch_line_map(patch: str) -> Dict[int, str]:
    """Parse a unified diff patch into a mapping of new-file line numbers
    to their content.  Only ``+`` (addition) lines are included.
    """
    line_map: Dict[int, str] = {}
    current_line = 0

    for raw_line in patch.splitlines():
        m = _HUNK_HEADER.match(raw_line)
        if m:
            current_line = int(m.group(1))
            continue

        if raw_line.startswith("+"):
            line_map[current_line] = raw_line[1:]
            current_line += 1
        elif raw_line.startswith("-"):
            pass  # removed line — doesn't advance new-file line counter
        else:
            current_line += 1

    return line_map


# ---------------------------------------------------------------------------
# Suggestion formatter
# ---------------------------------------------------------------------------

def format_suggestion(
    original_lines: List[str],
    replacement_lines: List[str],
    recipe_name: str,
    explanation: str = "",
) -> str:
    """Format a GitHub ``suggestion`` block.

    GitHub's suggestion syntax replaces the selected line range
    with the content inside the fenced block::

        ```suggestion
        new code here
        ```
    """
    suggestion = f"**{recipe_name}**"
    if explanation:
        suggestion += f": {explanation}"
    suggestion += "\n\n"
    suggestion += "```suggestion\n"
    suggestion += "\n".join(replacement_lines)
    suggestion += "\n```"
    return suggestion


def build_review_body(result: ReviewResult) -> str:
    """Build the top-level PR review body text."""
    if not result.has_suggestions:
        return (
            "**code4u.ai Review** — No issues found.\n\n"
            f"Reviewed {result.files_reviewed} file(s) against "
            f"{result.recipes_matched} recipe(s). All checks passed."
        )

    return (
        f"**code4u.ai Review** — {len(result.suggestions)} suggestion(s)\n\n"
        f"Reviewed {result.files_reviewed} file(s) against "
        f"{result.recipes_matched} recipe(s).\n\n"
        "Each suggestion below can be applied with one click."
    )


# ---------------------------------------------------------------------------
# GitHubReviewer
# ---------------------------------------------------------------------------

class GitHubReviewer:
    """Automated PR reviewer powered by the Recipe Engine.

    Connects to GitHub via PyGithub, fetches the PR diff, matches
    changed files to recipes, and posts inline suggestions.
    """

    def __init__(
        self,
        github_token: str = "",
        repo_full_name: str = "",
        workspace_path: Optional[str] = None,
        recipes_workspace: Optional[str] = None,
    ):
        self._token = github_token
        self._repo_name = repo_full_name
        self._workspace_path = workspace_path or "."
        self._recipes_workspace = recipes_workspace
        self._github = None
        self._repo = None

    def _ensure_github(self):
        """Lazily initialize the PyGithub client."""
        if self._github is not None:
            return
        from github import Github
        self._github = Github(self._token)
        self._repo = self._github.get_repo(self._repo_name)

    async def review_pr(
        self,
        pr_number: int,
        head_sha: str = "",
    ) -> ReviewResult:
        """Run the full review pipeline on a PR.

        1. Fetch PR files (diff) from GitHub.
        2. Load recipes and match changed files to selectors.
        3. For each match, analyze via recipe prompt template.
        4. Post suggestions as a PR review.
        """
        self._ensure_github()
        assert self._repo is not None

        result = ReviewResult(
            repo=self._repo_name,
            pr_number=pr_number,
            head_sha=head_sha,
        )

        pr = self._repo.get_pull(pr_number)
        pr_files_raw = pr.get_files()
        patches = parse_pr_files(pr_files_raw)
        reviewable = [p for p in patches if p.is_reviewable]
        result.files_reviewed = len(reviewable)

        if not reviewable:
            result.summary = "No reviewable files in PR."
            logger.info("pr_no_reviewable_files", pr=pr_number)
            return result

        import time as _time
        t0 = _time.time()

        from code4u.core.recipes import RecipeRegistry

        registry = RecipeRegistry(workspace_path=self._recipes_workspace)
        registry.load()
        all_recipes = registry.list_recipes()

        # Filter out globally disabled recipes
        try:
            from code4u.interfaces.api.routes.admin import get_disabled_recipes
            disabled = get_disabled_recipes()
            all_recipes = [r for r in all_recipes if r.id not in disabled]
        except Exception:
            pass

        if not all_recipes:
            result.summary = "No recipes loaded."
            logger.info("pr_no_recipes", pr=pr_number)
            return result

        changed_filenames = [p.filename for p in reviewable]
        matched_recipe_count = 0
        triggered_ids: List[str] = []

        for recipe in all_recipes:
            matching_files = recipe.selector.filter_files(changed_filenames)
            if not matching_files:
                continue
            matched_recipe_count += 1
            triggered_ids.append(recipe.id)

            for patch in reviewable:
                if patch.filename not in matching_files:
                    continue

                line_map = parse_patch_line_map(patch.patch)
                if not line_map:
                    continue

                suggestions = self._analyze_patch(
                    patch=patch,
                    line_map=line_map,
                    recipe=recipe,
                )
                result.suggestions.extend(suggestions)

        result.recipes_matched = matched_recipe_count
        result.summary = build_review_body(result)

        if result.has_suggestions:
            await self._post_review(pr, result)
            result.posted = True

        review_duration = (_time.time() - t0) * 1000

        # Record audit entry
        try:
            from code4u.models.analytics import AuditStore, ReviewAudit
            audit = ReviewAudit(
                repo_name=self._repo_name,
                pr_id=pr_number,
                pr_url=result.suggestions[0].path if result.suggestions else "",
                author=pr.user.login if hasattr(pr, "user") else "",
                head_sha=head_sha,
                suggestions_count=len(result.suggestions),
                triggered_recipes=triggered_ids,
                files_reviewed=result.files_reviewed,
                review_duration_ms=review_duration,
            )
            AuditStore().record(audit)
        except Exception:
            pass

        logger.info(
            "pr_review_complete",
            pr=pr_number,
            files=result.files_reviewed,
            recipes=result.recipes_matched,
            suggestions=len(result.suggestions),
        )

        return result

    def _analyze_patch(
        self,
        patch: FilePatch,
        line_map: Dict[int, str],
        recipe,
    ) -> List[ReviewComment]:
        """Analyze a file's patch against a recipe and generate comments.

        This uses pattern-based analysis from the recipe's prompt
        template keywords.  For LLM-powered analysis, the PlanExecutor
        would be invoked in dry-run mode on the file content.
        """
        from code4u.core.recipes import Recipe

        comments: List[ReviewComment] = []
        prompt_lower = recipe.prompt_template.lower()

        checks = _build_pattern_checks(prompt_lower)
        if not checks:
            return comments

        for line_num, content in sorted(line_map.items()):
            for check in checks:
                if check["pattern"].search(content):
                    suggestion_text = format_suggestion(
                        original_lines=[content],
                        replacement_lines=[check["replacement_fn"](content)],
                        recipe_name=recipe.name,
                        explanation=check["explanation"],
                    )
                    comments.append(ReviewComment(
                        path=patch.filename,
                        body=suggestion_text,
                        line=line_num,
                    ))
                    break  # one suggestion per line

        return comments

    async def _post_review(self, pr, result: ReviewResult) -> None:
        """Post the review to GitHub using the Reviews API."""
        comments = [c.to_github_comment() for c in result.suggestions[:50]]

        try:
            pr.create_review(
                body=result.summary,
                event="COMMENT",
                comments=comments,
            )
            logger.info(
                "review_posted",
                pr=result.pr_number,
                comments=len(comments),
            )
        except Exception as exc:
            logger.error(
                "review_post_failed",
                pr=result.pr_number,
                error=str(exc)[:300],
            )
            raise


# ---------------------------------------------------------------------------
# Built-in pattern checks derived from recipe prompt keywords
# ---------------------------------------------------------------------------

def _build_pattern_checks(prompt_lower: str) -> List[Dict]:
    """Build regex-based checks from common recipe prompt patterns.

    This provides instant, deterministic analysis without an LLM call.
    For more complex recipes, the full LLM pipeline would be used.
    """
    checks: List[Dict] = []

    if "f-string" in prompt_lower or "format(" in prompt_lower:
        checks.append({
            "pattern": re.compile(r'["\'][^"\']*%[sdrfx][^"\']*["\']\s*%\s*'),
            "replacement_fn": _suggest_fstring_percent,
            "explanation": "Use f-string instead of % formatting.",
        })
        checks.append({
            "pattern": re.compile(r'\.format\('),
            "replacement_fn": _suggest_fstring_format,
            "explanation": "Use f-string instead of .format().",
        })

    if "print" in prompt_lower and ("log" in prompt_lower or "debug" in prompt_lower):
        checks.append({
            "pattern": re.compile(r'\bprint\s*\('),
            "replacement_fn": _suggest_logger,
            "explanation": "Replace print() with structured logging.",
        })

    if "pathlib" in prompt_lower or "os.path" in prompt_lower:
        checks.append({
            "pattern": re.compile(r'\bos\.path\.\w+'),
            "replacement_fn": _suggest_pathlib,
            "explanation": "Use pathlib instead of os.path.",
        })

    if "type hint" in prompt_lower or "annotation" in prompt_lower:
        checks.append({
            "pattern": re.compile(r'^def\s+\w+\([^)]*\)\s*:'),
            "replacement_fn": lambda line: line,
            "explanation": "Consider adding type hints to function parameters.",
        })

    return checks


def _suggest_fstring_percent(line: str) -> str:
    return re.sub(
        r'"([^"]*?)"\s*%\s*\(([^)]+)\)',
        lambda m: f'f"{m.group(1).replace("%s", "{" + m.group(2).strip() + "}")}"',
        line,
    )


def _suggest_fstring_format(line: str) -> str:
    return line.replace('.format(', '  # TODO: convert to f-string: .format(')


def _suggest_logger(line: str) -> str:
    return re.sub(
        r'\bprint\s*\(',
        'logger.debug(',
        line,
    )


def _suggest_pathlib(line: str) -> str:
    replacements = {
        "os.path.join": "Path(...) / ...",
        "os.path.exists": "Path(...).exists()",
        "os.path.isfile": "Path(...).is_file()",
        "os.path.isdir": "Path(...).is_dir()",
        "os.path.basename": "Path(...).name",
        "os.path.dirname": "Path(...).parent",
        "os.path.abspath": "Path(...).resolve()",
    }
    result = line
    for old, new in replacements.items():
        if old in result:
            result = result.replace(old, f"{new}  # was: {old}")
            break
    return result
