"""Localization Agent — i18n compliance scanner.

Scans for hardcoded user-facing strings and verifies they exist
in the i18n dictionary for all supported languages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class LocalizationIssue:
    """A localization compliance issue."""
    file_path: str
    line_number: int
    hardcoded_string: str
    suggestion: str
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "hardcodedString": self.hardcoded_string,
            "suggestion": self.suggestion,
            "severity": self.severity,
        }


class LocalizationAgent:
    """Scans for hardcoded strings and verifies i18n coverage."""

    SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "ja", "zh", "ko", "pt", "ar", "hi"]

    def scan_for_hardcoded_strings(
        self,
        source_code: str,
        file_path: str = "",
    ) -> List[LocalizationIssue]:
        """Find hardcoded user-facing strings in JSX and Python."""
        issues: List[LocalizationIssue] = []
        lines = source_code.splitlines()

        for i, line in enumerate(lines, 1):
            if file_path.endswith((".jsx", ".tsx", ".js", ".ts")):
                matches = re.findall(r'>\s*([^<{]+[a-zA-Z]{4,}[^<{}]*)\s*<', line)
                for m in matches:
                    text = m.strip()
                    if len(text) > 3 and not text.startswith("{") and "{" not in text:
                        issues.append(LocalizationIssue(
                            file_path=file_path,
                            line_number=i,
                            hardcoded_string=text[:80],
                            suggestion=f"Use t('key') or {{t('key')}} for i18n",
                            severity="medium",
                        ))
                string_literals = re.findall(
                    r'["\']([^"\']{10,})["\']',
                    line,
                )
                for s in string_literals:
                    if re.search(r'[a-zA-Z]{4,}', s) and "import" not in line:
                        issues.append(LocalizationIssue(
                            file_path=file_path,
                            line_number=i,
                            hardcoded_string=s[:80],
                            suggestion="Move to i18n dictionary",
                            severity="low",
                        ))
            elif file_path.endswith(".py"):
                if re.search(r'raise\s+\w+Error\s*\(\s*["\']', line):
                    pass
                elif re.search(r'print\s*\(\s*["\'][^"\']+["\']', line):
                    issues.append(LocalizationIssue(
                        file_path=file_path,
                        line_number=i,
                        hardcoded_string="print(...)",
                        suggestion="Use logging or i18n for user messages",
                        severity="low",
                    ))
                msg_match = re.search(
                    r'["\']([^"\']{15,}[a-zA-Z][^"\']*)["\']',
                    line,
                )
                if msg_match and "def " not in line and "import" not in line:
                    s = msg_match.group(1)
                    if "error" in line.lower() or "message" in line.lower():
                        issues.append(LocalizationIssue(
                            file_path=file_path,
                            line_number=i,
                            hardcoded_string=s[:80],
                            suggestion="Use _() or gettext for user-facing strings",
                            severity="medium",
                        ))

        return issues[:20]

    def verify_i18n_coverage(
        self,
        i18n_dict: Dict[str, Dict[str, str]],
        languages: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Check all keys exist in all languages."""
        langs = languages or self.SUPPORTED_LANGUAGES
        missing: Dict[str, List[str]] = {}
        all_keys: set = set()
        for lang_data in i18n_dict.values():
            if isinstance(lang_data, dict):
                all_keys.update(lang_data.keys())

        for lang in langs:
            lang_data = i18n_dict.get(lang, {})
            if isinstance(lang_data, dict):
                for key in all_keys:
                    if key not in lang_data or not lang_data[key]:
                        missing.setdefault(lang, []).append(key)

        return {
            "complete": len(missing) == 0,
            "missingByLanguage": missing,
            "totalKeys": len(all_keys),
            "languagesChecked": langs,
        }

    def generate_report(
        self,
        issues: List[LocalizationIssue],
    ) -> Dict[str, Any]:
        """Generate localization report."""
        critical = sum(1 for i in issues if i.severity == "critical")
        medium = sum(1 for i in issues if i.severity == "medium")
        low = sum(1 for i in issues if i.severity == "low")
        score = max(0, 100 - critical * 25 - medium * 10 - low * 3)
        return {
            "score": min(100, score),
            "issues": [i.to_dict() for i in issues],
            "summary": {
                "total": len(issues),
                "critical": critical,
                "medium": medium,
                "low": low,
            },
        }
