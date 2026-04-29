"""Provenance & Attribution Tracker.

Tracks the origin of every AI-generated snippet. When a fix is applied
based on a Wisdom Nugget, the tracker records the attribution — crediting
the original internal source.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("provenance_tracker")


@dataclass
class ProvenanceRecord:
    """Attribution record for an AI-generated or suggested change."""
    record_id: str
    change_type: str
    file_path: str
    description: str
    source_type: str
    source_nugget_id: Optional[str] = None
    source_project_hash: Optional[str] = None
    source_author_hash: Optional[str] = None
    confidence: float = 0.0
    license_verified: bool = False
    license_id: Optional[str] = None
    applied: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recordId": self.record_id,
            "changeType": self.change_type,
            "filePath": self.file_path,
            "description": self.description,
            "sourceType": self.source_type,
            "sourceNuggetId": self.source_nugget_id,
            "sourceProjectHash": self.source_project_hash,
            "sourceAuthorHash": self.source_author_hash,
            "confidence": self.confidence,
            "licenseVerified": self.license_verified,
            "licenseId": self.license_id,
            "applied": self.applied,
            "timestamp": self.timestamp,
        }


class ProvenanceTracker:
    """Tracks provenance and attribution for all AI-assisted changes."""

    def __init__(self) -> None:
        self._records: List[ProvenanceRecord] = []

    def record_attribution(
        self,
        file_path: str,
        description: str,
        change_type: str = "ai_suggestion",
        source_type: str = "wisdom_nugget",
        source_nugget_id: Optional[str] = None,
        source_project_hash: Optional[str] = None,
        source_author_hash: Optional[str] = None,
        confidence: float = 0.0,
        license_verified: bool = False,
        license_id: Optional[str] = None,
    ) -> ProvenanceRecord:
        """Record a new provenance attribution."""
        record = ProvenanceRecord(
            record_id=str(uuid.uuid4()),
            change_type=change_type,
            file_path=file_path,
            description=description,
            source_type=source_type,
            source_nugget_id=source_nugget_id,
            source_project_hash=source_project_hash,
            source_author_hash=source_author_hash,
            confidence=confidence,
            license_verified=license_verified,
            license_id=license_id,
        )
        self._records.append(record)
        logger.info(
            "provenance_recorded",
            record_id=record.record_id,
            source_type=source_type,
            file_path=file_path,
        )
        return record

    def mark_applied(self, record_id: str) -> bool:
        """Mark a provenance record as having been applied."""
        for r in self._records:
            if r.record_id == record_id:
                r.applied = True
                return True
        return False

    def export_attribution_json(self, project_path: str = "") -> str:
        """Generate attribution.json content for the project."""
        applied = [r for r in self._records if r.applied]
        data = {
            "schemaVersion": "1.0",
            "generatedAt": time.time(),
            "projectPath": project_path,
            "totalAttributions": len(applied),
            "attributions": [
                {
                    "id": r.record_id,
                    "file": r.file_path,
                    "change": r.description,
                    "source": {
                        "type": r.source_type,
                        "nuggetId": r.source_nugget_id,
                        "projectHash": r.source_project_hash,
                        "authorHash": r.source_author_hash,
                        "license": r.license_id,
                        "licenseVerified": r.license_verified,
                    },
                    "confidence": r.confidence,
                    "timestamp": r.timestamp,
                }
                for r in applied
            ],
        }
        return json.dumps(data, indent=2)

    def save_attribution_file(self, project_path: str) -> str:
        """Save attribution.json to the project root."""
        content = self.export_attribution_json(project_path)
        filepath = os.path.join(project_path, "attribution.json") if project_path else "attribution.json"
        try:
            with open(filepath, "w") as f:
                f.write(content)
            logger.info("attribution_file_saved", path=filepath)
            return filepath
        except (OSError, PermissionError) as exc:
            logger.error("attribution_file_failed", error=str(exc))
            return ""

    def get_records(self, applied_only: bool = False) -> List[ProvenanceRecord]:
        if applied_only:
            return [r for r in self._records if r.applied]
        return list(self._records)

    def get_stats(self) -> Dict[str, Any]:
        records = self._records
        by_source: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        for r in records:
            by_source[r.source_type] = by_source.get(r.source_type, 0) + 1
            by_type[r.change_type] = by_type.get(r.change_type, 0) + 1
        return {
            "totalRecords": len(records),
            "appliedRecords": sum(1 for r in records if r.applied),
            "licenseVerified": sum(1 for r in records if r.license_verified),
            "bySourceType": by_source,
            "byChangeType": by_type,
        }

    def clear(self) -> int:
        count = len(self._records)
        self._records.clear()
        return count


_tracker_singleton: Optional[ProvenanceTracker] = None


def get_provenance_tracker() -> ProvenanceTracker:
    global _tracker_singleton
    if _tracker_singleton is None:
        _tracker_singleton = ProvenanceTracker()
    return _tracker_singleton
