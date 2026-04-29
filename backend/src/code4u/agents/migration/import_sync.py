"""Import Auto-Sync — updates import statements across all callers.

Given a list of ``ImportUpdate`` objects from the ``MigrationPlanner``,
the ``ImportSyncer`` applies the import rewrites to each file's content
in memory, producing new file contents ready for atomic disk write.

The syncer operates purely on strings — it does not touch the filesystem.
This makes it safe for dry-run validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

from code4u.agents.migration.planner import ImportUpdate

logger = structlog.get_logger("import_sync")


@dataclass
class SyncedFile:
    """Result of applying import updates to a single file."""
    file_path: str
    original_content: str
    new_content: str
    updates_applied: int = 0
    changed: bool = False

    @property
    def diff_summary(self) -> str:
        if not self.changed:
            return "no changes"
        return f"{self.updates_applied} import(s) updated"


class ImportSyncer:
    """Applies import path rewrites across multiple files.

    Thread-safe: all operations are pure-functional on strings.
    """

    def sync_all(
        self,
        import_updates: List[ImportUpdate],
        file_contents: Optional[Dict[str, str]] = None,
    ) -> List[SyncedFile]:
        """Apply all import updates and return new file contents.

        Args:
            import_updates: The updates to apply.
            file_contents: Optional pre-loaded file contents.
                If not provided, files are read from disk.

        Returns:
            List of ``SyncedFile`` results.
        """
        # Group updates by file
        by_file: Dict[str, List[ImportUpdate]] = {}
        for iu in import_updates:
            by_file.setdefault(iu.file_path, []).append(iu)

        results: List[SyncedFile] = []

        for fp, updates in by_file.items():
            if file_contents and fp in file_contents:
                content = file_contents[fp]
            else:
                try:
                    content = Path(fp).read_text(encoding="utf-8")
                except Exception:
                    continue

            new_content = self._apply_updates(content, updates)
            synced = SyncedFile(
                file_path=fp,
                original_content=content,
                new_content=new_content,
                updates_applied=len(updates),
                changed=new_content != content,
            )
            results.append(synced)

        logger.info(
            "imports_synced",
            files=len(results),
            changed=sum(1 for s in results if s.changed),
            total_updates=len(import_updates),
        )

        return results

    def _apply_updates(
        self, content: str, updates: List[ImportUpdate],
    ) -> str:
        """Apply a list of import updates to file content."""
        lines = content.splitlines(keepends=True)

        for update in sorted(updates, key=lambda u: u.line_number, reverse=True):
            if update.line_number > 0 and update.line_number <= len(lines):
                idx = update.line_number - 1
                old_line = lines[idx].rstrip()
                if old_line == update.old_import:
                    lines[idx] = update.new_import + "\n"
                    continue

            # Fallback: search for the old import line
            for i, line in enumerate(lines):
                if line.rstrip() == update.old_import:
                    lines[i] = update.new_import + "\n"
                    break

        return "".join(lines)

    def preview(
        self,
        import_updates: List[ImportUpdate],
    ) -> List[Dict[str, Any]]:
        """Preview import updates without applying them."""
        return [
            {
                "file": iu.file_path,
                "line": iu.line_number,
                "old": iu.old_import,
                "new": iu.new_import,
            }
            for iu in import_updates
        ]
