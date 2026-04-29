"""Legal Agent — License Compliance & Compatibility Enforcement.

Detects project licenses, checks compatibility between source and
target projects when sharing Wisdom Nuggets, and blocks transfers
that would cause license contamination.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger("legal_agent")


class LicenseCategory(str, Enum):
    """License families grouped by copyleft strength."""
    PERMISSIVE = "permissive"
    WEAK_COPYLEFT = "weak_copyleft"
    STRONG_COPYLEFT = "strong_copyleft"
    PROPRIETARY = "proprietary"
    UNKNOWN = "unknown"


LICENSE_CATALOG: Dict[str, Dict[str, Any]] = {
    "MIT": {"spdx": "MIT", "category": LicenseCategory.PERMISSIVE, "copyleft": False},
    "Apache-2.0": {"spdx": "Apache-2.0", "category": LicenseCategory.PERMISSIVE, "copyleft": False},
    "BSD-2-Clause": {"spdx": "BSD-2-Clause", "category": LicenseCategory.PERMISSIVE, "copyleft": False},
    "BSD-3-Clause": {"spdx": "BSD-3-Clause", "category": LicenseCategory.PERMISSIVE, "copyleft": False},
    "ISC": {"spdx": "ISC", "category": LicenseCategory.PERMISSIVE, "copyleft": False},
    "Unlicense": {"spdx": "Unlicense", "category": LicenseCategory.PERMISSIVE, "copyleft": False},
    "CC0-1.0": {"spdx": "CC0-1.0", "category": LicenseCategory.PERMISSIVE, "copyleft": False},
    "0BSD": {"spdx": "0BSD", "category": LicenseCategory.PERMISSIVE, "copyleft": False},
    "LGPL-2.1": {"spdx": "LGPL-2.1-only", "category": LicenseCategory.WEAK_COPYLEFT, "copyleft": True},
    "LGPL-3.0": {"spdx": "LGPL-3.0-only", "category": LicenseCategory.WEAK_COPYLEFT, "copyleft": True},
    "MPL-2.0": {"spdx": "MPL-2.0", "category": LicenseCategory.WEAK_COPYLEFT, "copyleft": True},
    "EPL-2.0": {"spdx": "EPL-2.0", "category": LicenseCategory.WEAK_COPYLEFT, "copyleft": True},
    "CDDL-1.0": {"spdx": "CDDL-1.0", "category": LicenseCategory.WEAK_COPYLEFT, "copyleft": True},
    "GPL-2.0": {"spdx": "GPL-2.0-only", "category": LicenseCategory.STRONG_COPYLEFT, "copyleft": True},
    "GPL-3.0": {"spdx": "GPL-3.0-only", "category": LicenseCategory.STRONG_COPYLEFT, "copyleft": True},
    "AGPL-3.0": {"spdx": "AGPL-3.0-only", "category": LicenseCategory.STRONG_COPYLEFT, "copyleft": True},
    "SSPL-1.0": {"spdx": "SSPL-1.0", "category": LicenseCategory.STRONG_COPYLEFT, "copyleft": True},
    "Proprietary": {"spdx": "LicenseRef-Proprietary", "category": LicenseCategory.PROPRIETARY, "copyleft": False},
    "Commercial": {"spdx": "LicenseRef-Commercial", "category": LicenseCategory.PROPRIETARY, "copyleft": False},
}

COMPATIBILITY_MATRIX: Dict[Tuple[LicenseCategory, LicenseCategory], bool] = {
    (LicenseCategory.PERMISSIVE, LicenseCategory.PERMISSIVE): True,
    (LicenseCategory.PERMISSIVE, LicenseCategory.WEAK_COPYLEFT): True,
    (LicenseCategory.PERMISSIVE, LicenseCategory.STRONG_COPYLEFT): True,
    (LicenseCategory.PERMISSIVE, LicenseCategory.PROPRIETARY): True,
    (LicenseCategory.WEAK_COPYLEFT, LicenseCategory.PERMISSIVE): True,
    (LicenseCategory.WEAK_COPYLEFT, LicenseCategory.WEAK_COPYLEFT): True,
    (LicenseCategory.WEAK_COPYLEFT, LicenseCategory.STRONG_COPYLEFT): True,
    (LicenseCategory.WEAK_COPYLEFT, LicenseCategory.PROPRIETARY): False,
    (LicenseCategory.STRONG_COPYLEFT, LicenseCategory.PERMISSIVE): False,
    (LicenseCategory.STRONG_COPYLEFT, LicenseCategory.WEAK_COPYLEFT): False,
    (LicenseCategory.STRONG_COPYLEFT, LicenseCategory.STRONG_COPYLEFT): True,
    (LicenseCategory.STRONG_COPYLEFT, LicenseCategory.PROPRIETARY): False,
    (LicenseCategory.PROPRIETARY, LicenseCategory.PERMISSIVE): True,
    (LicenseCategory.PROPRIETARY, LicenseCategory.WEAK_COPYLEFT): False,
    (LicenseCategory.PROPRIETARY, LicenseCategory.STRONG_COPYLEFT): False,
    (LicenseCategory.PROPRIETARY, LicenseCategory.PROPRIETARY): False,
    (LicenseCategory.UNKNOWN, LicenseCategory.PERMISSIVE): False,
    (LicenseCategory.UNKNOWN, LicenseCategory.WEAK_COPYLEFT): False,
    (LicenseCategory.UNKNOWN, LicenseCategory.STRONG_COPYLEFT): False,
    (LicenseCategory.UNKNOWN, LicenseCategory.PROPRIETARY): False,
}


@dataclass
class LicenseInfo:
    """Detected license for a project."""
    license_id: str
    spdx_id: str
    category: LicenseCategory
    copyleft: bool
    source: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "licenseId": self.license_id,
            "spdxId": self.spdx_id,
            "category": self.category.value,
            "copyleft": self.copyleft,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class CompatibilityResult:
    """Result of checking license compatibility between two projects."""
    compatible: bool
    source_license: str
    target_license: str
    source_category: str
    target_category: str
    reason: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compatible": self.compatible,
            "sourceLicense": self.source_license,
            "targetLicense": self.target_license,
            "sourceCategory": self.source_category,
            "targetCategory": self.target_category,
            "reason": self.reason,
            "recommendation": self.recommendation,
        }


@dataclass
class LicenseViolation:
    """A detected license violation."""
    violation_id: str
    severity: str
    source_project: str
    target_project: str
    source_license: str
    target_license: str
    file_path: str
    description: str
    blocked: bool
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violationId": self.violation_id,
            "severity": self.severity,
            "sourceProject": self.source_project,
            "targetProject": self.target_project,
            "sourceLicense": self.source_license,
            "targetLicense": self.target_license,
            "filePath": self.file_path,
            "description": self.description,
            "blocked": self.blocked,
            "timestamp": self.timestamp,
        }


class LegalAgent:
    """License compliance enforcement for cross-project code sharing."""

    LICENSE_FILE_PATTERNS = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENCE.md",
        "COPYING", "COPYING.md", "COPYING.txt",
    ]

    LICENSE_SIGNATURES: List[Tuple[str, str]] = [
        ("MIT License", "MIT"),
        ("Permission is hereby granted, free of charge", "MIT"),
        ("Apache License, Version 2.0", "Apache-2.0"),
        ("Licensed under the Apache License", "Apache-2.0"),
        ("BSD 2-Clause", "BSD-2-Clause"),
        ("BSD 3-Clause", "BSD-3-Clause"),
        ("Redistribution and use in source and binary forms", "BSD-3-Clause"),
        ("ISC License", "ISC"),
        ("GNU General Public License", "GPL-3.0"),
        ("GNU GENERAL PUBLIC LICENSE", "GPL-3.0"),
        ("Version 2, June 1991", "GPL-2.0"),
        ("Version 3, 29 June 2007", "GPL-3.0"),
        ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL-3.0"),
        ("GNU Lesser General Public", "LGPL-3.0"),
        ("Mozilla Public License Version 2.0", "MPL-2.0"),
        ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
        ("Server Side Public License", "SSPL-1.0"),
        ("Eclipse Public License", "EPL-2.0"),
        ("This is free and unencumbered software", "Unlicense"),
        ("CC0 1.0 Universal", "CC0-1.0"),
        ("All rights reserved", "Proprietary"),
        ("PROPRIETARY AND CONFIDENTIAL", "Proprietary"),
    ]

    def __init__(self) -> None:
        self._violations: List[LicenseViolation] = []
        self._project_licenses: Dict[str, LicenseInfo] = {}

    def detect_license(self, workspace_path: str = "") -> LicenseInfo:
        """Detect the license of a project from its workspace."""
        # Try LICENSE file
        for filename in self.LICENSE_FILE_PATTERNS:
            filepath = os.path.join(workspace_path, filename) if workspace_path else filename
            try:
                with open(filepath) as f:
                    content = f.read()
                license_id = self._match_license_text(content)
                if license_id:
                    info = self._build_license_info(license_id, f"file:{filename}", 0.95)
                    self._project_licenses[workspace_path or "current"] = info
                    logger.info("license_detected", license=license_id, source=filename)
                    return info
            except (FileNotFoundError, PermissionError):
                continue

        # Try package.json
        pkg_path = os.path.join(workspace_path, "package.json") if workspace_path else "package.json"
        try:
            with open(pkg_path) as f:
                pkg = json.load(f)
            license_field = pkg.get("license", "")
            if license_field and license_field in LICENSE_CATALOG:
                info = self._build_license_info(license_field, "package.json", 0.90)
                self._project_licenses[workspace_path or "current"] = info
                return info
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            pass

        # Try pyproject.toml
        pyproject_path = os.path.join(workspace_path, "pyproject.toml") if workspace_path else "pyproject.toml"
        try:
            with open(pyproject_path) as f:
                content = f.read()
            m = re.search(r'license\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                license_id = self._normalize_license(m.group(1))
                if license_id:
                    info = self._build_license_info(license_id, "pyproject.toml", 0.85)
                    self._project_licenses[workspace_path or "current"] = info
                    return info
        except (FileNotFoundError, PermissionError):
            pass

        # Try Cargo.toml
        cargo_path = os.path.join(workspace_path, "Cargo.toml") if workspace_path else "Cargo.toml"
        try:
            with open(cargo_path) as f:
                content = f.read()
            m = re.search(r'license\s*=\s*"([^"]+)"', content)
            if m:
                license_id = self._normalize_license(m.group(1))
                if license_id:
                    info = self._build_license_info(license_id, "Cargo.toml", 0.85)
                    self._project_licenses[workspace_path or "current"] = info
                    return info
        except (FileNotFoundError, PermissionError):
            pass

        logger.warning("license_not_found", workspace=workspace_path)
        unknown = LicenseInfo(
            license_id="Unknown",
            spdx_id="LicenseRef-Unknown",
            category=LicenseCategory.UNKNOWN,
            copyleft=False,
            source="not_found",
            confidence=0.0,
        )
        self._project_licenses[workspace_path or "current"] = unknown
        return unknown

    def detect_license_from_content(self, content: str, filename: str = "") -> LicenseInfo:
        """Detect license from raw content (for non-filesystem use)."""
        if filename in ("package.json",):
            try:
                pkg = json.loads(content)
                license_field = pkg.get("license", "")
                if license_field:
                    normalized = self._normalize_license(license_field)
                    if normalized:
                        return self._build_license_info(normalized, "package.json", 0.90)
            except json.JSONDecodeError:
                pass

        license_id = self._match_license_text(content)
        if license_id:
            return self._build_license_info(license_id, filename or "content", 0.80)

        return LicenseInfo("Unknown", "LicenseRef-Unknown", LicenseCategory.UNKNOWN, False, "content", 0.0)

    def check_compatibility(
        self,
        source_license: str,
        target_license: str,
    ) -> CompatibilityResult:
        """Check if code from source_license can be used in target_license project."""
        src_norm = self._normalize_license(source_license)
        tgt_norm = self._normalize_license(target_license)

        src_info = LICENSE_CATALOG.get(src_norm or source_license, {"category": LicenseCategory.UNKNOWN})
        tgt_info = LICENSE_CATALOG.get(tgt_norm or target_license, {"category": LicenseCategory.UNKNOWN})

        src_cat = src_info["category"] if isinstance(src_info["category"], LicenseCategory) else LicenseCategory(src_info["category"])
        tgt_cat = tgt_info["category"] if isinstance(tgt_info["category"], LicenseCategory) else LicenseCategory(tgt_info["category"])

        compatible = COMPATIBILITY_MATRIX.get((src_cat, tgt_cat), False)

        if compatible:
            reason = f"{src_norm or source_license} ({src_cat.value}) is compatible with {tgt_norm or target_license} ({tgt_cat.value})"
            recommendation = "Transfer is allowed."
        else:
            reason = f"License contamination risk: {src_norm or source_license} ({src_cat.value}) code cannot be used in {tgt_norm or target_license} ({tgt_cat.value}) project"
            if src_cat == LicenseCategory.STRONG_COPYLEFT:
                recommendation = "Strong copyleft code requires the entire target project to adopt the same license. Consider rewriting the fix from scratch."
            elif src_cat == LicenseCategory.UNKNOWN:
                recommendation = "Source license is unknown. Identify the license before transferring code."
            elif tgt_cat == LicenseCategory.PROPRIETARY:
                recommendation = "Copyleft-licensed code cannot be used in proprietary projects. Write an independent implementation."
            else:
                recommendation = "Review license terms manually before proceeding."

        return CompatibilityResult(
            compatible=compatible,
            source_license=src_norm or source_license,
            target_license=tgt_norm or target_license,
            source_category=src_cat.value,
            target_category=tgt_cat.value,
            reason=reason,
            recommendation=recommendation,
        )

    def gate_wisdom_transfer(
        self,
        source_project_license: str,
        target_project_license: str,
        nugget_id: str = "",
        file_path: str = "",
    ) -> Tuple[bool, Optional[LicenseViolation]]:
        """Gate a Wisdom Nugget transfer between projects. Returns (allowed, violation_or_None)."""
        result = self.check_compatibility(source_project_license, target_project_license)

        if result.compatible:
            logger.info("wisdom_transfer_allowed", nugget_id=nugget_id)
            return True, None

        violation = LicenseViolation(
            violation_id=str(uuid.uuid4()),
            severity="critical" if "copyleft" in result.reason.lower() else "high",
            source_project=source_project_license,
            target_project=target_project_license,
            source_license=result.source_license,
            target_license=result.target_license,
            file_path=file_path,
            description=result.reason,
            blocked=True,
            timestamp=time.time(),
        )
        self._violations.append(violation)
        logger.warning("wisdom_transfer_blocked", nugget_id=nugget_id, reason=result.reason)
        return False, violation

    def _match_license_text(self, text: str) -> Optional[str]:
        for signature, license_id in self.LICENSE_SIGNATURES:
            if signature.lower() in text.lower():
                return license_id
        return None

    def _normalize_license(self, raw: str) -> Optional[str]:
        """Normalize a license string to a known ID."""
        raw_lower = raw.strip().lower()
        for key in LICENSE_CATALOG:
            if key.lower() == raw_lower:
                return key
        aliases = {
            "mit": "MIT", "apache 2.0": "Apache-2.0", "apache-2": "Apache-2.0",
            "bsd": "BSD-3-Clause", "bsd-2": "BSD-2-Clause", "bsd-3": "BSD-3-Clause",
            "gpl": "GPL-3.0", "gpl2": "GPL-2.0", "gpl3": "GPL-3.0", "gplv2": "GPL-2.0", "gplv3": "GPL-3.0",
            "lgpl": "LGPL-3.0", "lgpl3": "LGPL-3.0", "lgplv3": "LGPL-3.0",
            "agpl": "AGPL-3.0", "agpl3": "AGPL-3.0", "agplv3": "AGPL-3.0",
            "mpl": "MPL-2.0", "mpl2": "MPL-2.0",
            "isc": "ISC", "unlicense": "Unlicense",
            "proprietary": "Proprietary", "commercial": "Commercial",
        }
        return aliases.get(raw_lower)

    def _build_license_info(self, license_id: str, source: str, confidence: float) -> LicenseInfo:
        catalog_entry = LICENSE_CATALOG.get(license_id, {})
        return LicenseInfo(
            license_id=license_id,
            spdx_id=catalog_entry.get("spdx", f"LicenseRef-{license_id}"),
            category=catalog_entry.get("category", LicenseCategory.UNKNOWN),
            copyleft=catalog_entry.get("copyleft", False),
            source=source,
            confidence=confidence,
        )

    def get_violations(self) -> List[LicenseViolation]:
        return list(self._violations)

    def get_compatibility_matrix(self) -> Dict[str, Any]:
        """Return the full compatibility matrix for UI display."""
        categories = [c.value for c in LicenseCategory if c != LicenseCategory.UNKNOWN]
        matrix: Dict[str, Dict[str, bool]] = {}
        for src in LicenseCategory:
            if src == LicenseCategory.UNKNOWN:
                continue
            row: Dict[str, bool] = {}
            for tgt in LicenseCategory:
                if tgt == LicenseCategory.UNKNOWN:
                    continue
                row[tgt.value] = COMPATIBILITY_MATRIX.get((src, tgt), False)
            matrix[src.value] = row
        return {"categories": categories, "matrix": matrix}

    def get_project_license(self, workspace: str = "") -> Optional[LicenseInfo]:
        return self._project_licenses.get(workspace or "current")

    def generate_report(self) -> str:
        """Generate a Markdown legal compliance report."""
        lines = [
            "# Legal & License Compliance Report",
            "",
            f"**Violations Found:** {len(self._violations)}",
            f"**Projects Scanned:** {len(self._project_licenses)}",
            "",
        ]
        if self._violations:
            lines.append("## License Violations")
            lines.append("")
            for v in self._violations:
                lines.append(f"### [{v.severity.upper()}] {v.violation_id[:8]}")
                lines.append(f"- **Source:** {v.source_license} ({v.source_project})")
                lines.append(f"- **Target:** {v.target_license} ({v.target_project})")
                lines.append(f"- **File:** {v.file_path}")
                lines.append(f"- **Description:** {v.description}")
                lines.append(f"- **Blocked:** {'Yes' if v.blocked else 'No'}")
                lines.append("")
        else:
            lines.append("No license violations detected.")
        return "\n".join(lines)


_legal_agent_singleton: Optional[LegalAgent] = None


def get_legal_agent() -> LegalAgent:
    global _legal_agent_singleton
    if _legal_agent_singleton is None:
        _legal_agent_singleton = LegalAgent()
    return _legal_agent_singleton
