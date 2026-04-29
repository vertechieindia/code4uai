"""Git Manager — clone, pull, and manage remote repositories.

Uses subprocess to call ``git`` directly, avoiding heavy GitPython
dependencies. Supports authenticated HTTPS clones using OAuth tokens.

Usage::

    mgr = GitManager(base_dir="/tmp/code4u-repos")
    result = mgr.clone("https://github.com/org/repo.git", token="ghp_...")
    print(result.local_path)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger("git_manager")


@dataclass
class CloneResult:
    """Outcome of a git clone operation."""
    success: bool
    local_path: str = ""
    repo_name: str = ""
    owner: str = ""
    branch: str = "main"
    duration_ms: float = 0.0
    error: str = ""
    commit_sha: str = ""

    def to_dict(self):
        return {
            "success": self.success,
            "localPath": self.local_path,
            "repoName": self.repo_name,
            "owner": self.owner,
            "branch": self.branch,
            "durationMs": round(self.duration_ms, 1),
            "error": self.error,
            "commitSha": self.commit_sha,
        }


@dataclass
class PullResult:
    """Outcome of a git pull operation."""
    success: bool
    updated: bool = False
    new_commits: int = 0
    changed_files: List[str] = field(default_factory=list)
    error: str = ""


def _parse_repo_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo_name) from a git URL.

    Supports:
      - https://github.com/owner/repo.git
      - https://github.com/owner/repo
      - git@github.com:owner/repo.git
    """
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    if url.startswith("git@"):
        match = re.match(r"git@[\w.]+:(.+)/(.+)", url)
        if match:
            return match.group(1), match.group(2)

    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]

    return "", Path(url).stem


def _inject_token(url: str, token: str) -> str:
    """Inject an OAuth token into an HTTPS git URL for authenticated clone."""
    if not token or not url.startswith("https://"):
        return url
    parsed = urlparse(url)
    authed = parsed._replace(netloc=f"x-access-token:{token}@{parsed.hostname}")
    return authed.geturl()


class GitManager:
    """Manages local clones of remote Git repositories."""

    def __init__(self, base_dir: str = "/tmp/code4u-repos") -> None:
        self._base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def clone(
        self,
        url: str,
        token: str = "",
        branch: str = "",
        shallow: bool = True,
    ) -> CloneResult:
        """Clone a remote repository to a local directory.

        Args:
            url: HTTPS or SSH git URL.
            token: GitHub/GitLab OAuth token for private repos.
            branch: Specific branch to clone (default: repo default).
            shallow: If True, clone with ``--depth 1`` for speed.

        Returns:
            CloneResult with the local path and metadata.
        """
        owner, repo_name = _parse_repo_url(url)
        local_path = os.path.join(self._base_dir, owner, repo_name)

        if os.path.isdir(os.path.join(local_path, ".git")):
            logger.info("repo_already_cloned", path=local_path)
            sha = self._get_head_sha(local_path)
            br = self._get_current_branch(local_path)
            return CloneResult(
                success=True,
                local_path=local_path,
                repo_name=repo_name,
                owner=owner,
                branch=br,
                commit_sha=sha,
            )

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        authed_url = _inject_token(url, token)

        cmd = ["git", "clone"]
        if shallow:
            cmd.extend(["--depth", "1"])
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([authed_url, local_path])

        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except subprocess.TimeoutExpired:
            return CloneResult(
                success=False,
                error="Clone timed out after 120 seconds",
                repo_name=repo_name,
                owner=owner,
                duration_ms=(time.monotonic() - t0) * 1000,
            )

        duration = (time.monotonic() - t0) * 1000

        if proc.returncode != 0:
            stderr = proc.stderr or ""
            clean_err = re.sub(r"x-access-token:[^@]+@", "***@", stderr)
            logger.error("clone_failed", url=url, error=clean_err[:300])
            return CloneResult(
                success=False,
                error=clean_err.strip()[:500],
                repo_name=repo_name,
                owner=owner,
                duration_ms=duration,
            )

        sha = self._get_head_sha(local_path)
        br = self._get_current_branch(local_path) or branch or "main"

        logger.info(
            "clone_complete",
            repo=f"{owner}/{repo_name}",
            path=local_path,
            sha=sha[:8] if sha else "",
            duration_ms=round(duration, 1),
        )

        return CloneResult(
            success=True,
            local_path=local_path,
            repo_name=repo_name,
            owner=owner,
            branch=br,
            duration_ms=duration,
            commit_sha=sha,
        )

    def pull(self, local_path: str) -> PullResult:
        """Pull latest changes for an already-cloned repository."""
        if not os.path.isdir(os.path.join(local_path, ".git")):
            return PullResult(success=False, error="Not a git repository")

        old_sha = self._get_head_sha(local_path)

        try:
            proc = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=local_path,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except subprocess.TimeoutExpired:
            return PullResult(success=False, error="Pull timed out")

        if proc.returncode != 0:
            return PullResult(success=False, error=proc.stderr.strip()[:300])

        new_sha = self._get_head_sha(local_path)
        updated = old_sha != new_sha

        changed: List[str] = []
        if updated and old_sha:
            try:
                diff_proc = subprocess.run(
                    ["git", "diff", "--name-only", old_sha, new_sha],
                    cwd=local_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if diff_proc.returncode == 0:
                    changed = [f for f in diff_proc.stdout.strip().split("\n") if f]
            except Exception:
                pass

        return PullResult(
            success=True,
            updated=updated,
            changed_files=changed,
        )

    def delete(self, local_path: str) -> bool:
        """Remove a cloned repository from disk."""
        if not local_path.startswith(self._base_dir):
            return False
        try:
            shutil.rmtree(local_path)
            return True
        except Exception:
            return False

    def _get_head_sha(self, local_path: str) -> str:
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=local_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return proc.stdout.strip() if proc.returncode == 0 else ""
        except Exception:
            return ""

    def _get_current_branch(self, local_path: str) -> str:
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=local_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return proc.stdout.strip() if proc.returncode == 0 else ""
        except Exception:
            return ""
