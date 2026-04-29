"""Atomic Migration Executor.

Takes a ``MigrationPlan`` and executes it as a single atomic
transaction.  If any file write fails, ALL changes are rolled back
to the pre-migration state.

Execution order:
  1. Backup all files that will be touched.
  2. Write the new target file (with moved symbols).
  3. Write the new source file (with symbols removed).
  4. Write all impacted files (with updated imports).
  5. On any failure → restore all backups.

This is the "Day 1 Safety Cage" applied to structural migrations.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from code4u.agents.migration.planner import MigrationPlan
from code4u.agents.migration.import_sync import ImportSyncer, SyncedFile

logger = structlog.get_logger("migration_executor")


@dataclass
class MigrationResult:
    """Outcome of a migration execution."""
    success: bool = False
    files_written: int = 0
    files_rolled_back: int = 0
    duration_ms: float = 0.0
    error: str = ""
    dry_run: bool = False
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "filesWritten": self.files_written,
            "filesRolledBack": self.files_rolled_back,
            "durationMs": round(self.duration_ms, 1),
            "error": self.error,
            "dryRun": self.dry_run,
            "validationErrors": self.validation_errors,
        }


class MigrationExecutor:
    """Executes a ``MigrationPlan`` with full atomic rollback.

    Every file touched during the migration is backed up first.
    If any write fails, all files are restored to their original state.
    """

    def execute(
        self,
        plan: MigrationPlan,
        *,
        dry_run: bool = False,
    ) -> MigrationResult:
        """Execute the migration plan.

        Args:
            plan: The migration plan to execute.
            dry_run: If True, validate but don't write to disk.

        Returns:
            ``MigrationResult`` with outcome details.
        """
        t0 = time.monotonic()
        result = MigrationResult(dry_run=dry_run)

        if not plan.is_valid:
            result.validation_errors = list(plan.validation_errors)
            result.error = "Plan has validation errors"
            result.duration_ms = (time.monotonic() - t0) * 1000
            return result

        # Dry-run validation
        validation = self._validate_in_memory(plan)
        if validation:
            result.validation_errors = validation
            result.error = "In-memory validation failed"
            result.duration_ms = (time.monotonic() - t0) * 1000
            return result

        if dry_run:
            result.success = True
            result.files_written = plan.total_operations
            result.duration_ms = (time.monotonic() - t0) * 1000
            return result

        # Execute with atomic rollback
        backups: Dict[str, Optional[str]] = {}
        written: List[str] = []

        try:
            # Phase 1: Backup all affected files
            all_files = self._collect_affected_files(plan)
            for fp in all_files:
                backups[fp] = self._backup_file(fp)

            # Phase 2: Write target file
            self._write_file(plan.target_file, plan.target_new_content)
            written.append(plan.target_file)

            # Phase 3: Write source file
            self._write_file(plan.source_file, plan.source_new_content)
            written.append(plan.source_file)

            # Phase 4: Apply import updates
            syncer = ImportSyncer()
            synced_files = syncer.sync_all(plan.import_updates)
            for sf in synced_files:
                if sf.changed:
                    self._write_file(sf.file_path, sf.new_content)
                    written.append(sf.file_path)

            result.success = True
            result.files_written = len(written)

        except Exception as exc:
            result.error = str(exc)
            result.success = False

            # Rollback all written files
            rolled_back = 0
            for fp, backup_content in backups.items():
                try:
                    if backup_content is None:
                        # File didn't exist before — remove it
                        p = Path(fp)
                        if p.is_file():
                            p.unlink()
                            rolled_back += 1
                    else:
                        Path(fp).write_text(backup_content, encoding="utf-8")
                        rolled_back += 1
                except Exception:
                    pass

            result.files_rolled_back = rolled_back

        result.duration_ms = (time.monotonic() - t0) * 1000

        logger.info(
            "migration_executed",
            success=result.success,
            written=result.files_written,
            rolled_back=result.files_rolled_back,
            duration_ms=round(result.duration_ms, 1),
            dry_run=dry_run,
        )

        return result

    def _validate_in_memory(self, plan: MigrationPlan) -> List[str]:
        """Simulate the migration in memory and check for errors."""
        errors: List[str] = []

        # Validate target will have valid syntax
        try:
            ast.parse(plan.target_new_content)
        except SyntaxError as e:
            errors.append(f"Target file would have syntax error: {e}")

        # Validate source (after removal) has valid syntax
        if plan.source_new_content.strip():
            try:
                ast.parse(plan.source_new_content)
            except SyntaxError as e:
                errors.append(f"Source file would have syntax error after removal: {e}")

        # Validate each import update produces valid syntax
        syncer = ImportSyncer()
        synced = syncer.sync_all(plan.import_updates)
        for sf in synced:
            if sf.changed:
                ext = Path(sf.file_path).suffix
                if ext == ".py":
                    try:
                        ast.parse(sf.new_content)
                    except SyntaxError as e:
                        errors.append(
                            f"Import update in {Path(sf.file_path).name} "
                            f"would cause syntax error: {e}"
                        )

        # Check for circular dependency introduction
        # (target importing from source which re-exports from target)
        source_module = Path(plan.source_file).stem
        target_module = Path(plan.target_file).stem
        if (f"from {target_module}" in plan.source_new_content
                and f"from {source_module}" in plan.target_new_content):
            errors.append(
                f"Migration would create circular dependency between "
                f"{source_module} and {target_module}"
            )

        return errors

    def _collect_affected_files(self, plan: MigrationPlan) -> List[str]:
        """Return all files that will be modified."""
        files = [plan.source_file, plan.target_file]
        for iu in plan.import_updates:
            if iu.file_path not in files:
                files.append(iu.file_path)
        return files

    def _backup_file(self, file_path: str) -> Optional[str]:
        """Read a file's content for backup, or None if it doesn't exist."""
        p = Path(file_path)
        if p.is_file():
            return p.read_text(encoding="utf-8")
        return None

    def _write_file(self, file_path: str, content: str) -> None:
        """Write content to a file, creating parent dirs if needed."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
