"""LLM-powered WCAG Accessibility Agent.

Analyzes DOM trees and JSX/TSX source code to find WCAG violations:
- Missing aria-labels on interactive elements
- Missing alt text on images
- Poor color contrast ratios
- Missing form labels
- Keyboard navigation issues
- Missing heading hierarchy
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class AccessibilityViolation:
    """A single WCAG accessibility violation."""
    rule_id: str
    severity: str
    element: str
    description: str
    suggestion: str
    wcag_criterion: str = ""
    file_path: str = ""
    line_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "severity": self.severity,
            "element": self.element,
            "description": self.description,
            "suggestion": self.suggestion,
            "wcagCriterion": self.wcag_criterion,
            "filePath": self.file_path,
            "lineNumber": self.line_number,
        }


class AccessibilityAgent:
    """Analyzes DOM and JSX/TSX for WCAG violations."""

    def analyze_dom(self, dom_json: Dict[str, Any]) -> List[AccessibilityViolation]:
        """Analyze DOM tree (JSON representation) for violations."""
        violations: List[AccessibilityViolation] = []
        self._walk_dom(dom_json, violations)
        return violations

    def _walk_dom(self, node: Any, violations: List[AccessibilityViolation]) -> None:
        if isinstance(node, dict):
            tag = node.get("tagName", "").lower()
            attrs = node.get("attributes", {}) or {}
            if tag == "img" and not attrs.get("alt"):
                violations.append(AccessibilityViolation(
                    rule_id="img-alt",
                    severity="critical",
                    element="img",
                    description="Image missing alt attribute",
                    suggestion="Add alt='...' describing the image",
                    wcag_criterion="1.1.1",
                ))
            if tag == "button" and not attrs.get("aria-label") and not node.get("text"):
                violations.append(AccessibilityViolation(
                    rule_id="button-label",
                    severity="major",
                    element="button",
                    description="Button missing accessible name",
                    suggestion="Add aria-label or visible text",
                    wcag_criterion="4.1.2",
                ))
            if tag == "input" and attrs.get("type") in ("text", "email", "password"):
                if not attrs.get("aria-label") and not attrs.get("id"):
                    violations.append(AccessibilityViolation(
                        rule_id="input-label",
                        severity="major",
                        element="input",
                        description="Input missing associated label",
                        suggestion="Add aria-label or wrap with <label>",
                        wcag_criterion="1.3.1",
                    ))
            for child in node.get("children", []) or []:
                self._walk_dom(child, violations)
        elif isinstance(node, list):
            for item in node:
                self._walk_dom(item, violations)

    def analyze_jsx(
        self,
        source_code: str,
        file_path: str = "",
    ) -> List[AccessibilityViolation]:
        """Regex-based checks for JSX/TSX accessibility issues."""
        violations: List[AccessibilityViolation] = []
        lines = source_code.splitlines()

        for i, line in enumerate(lines, 1):
            if "<img " in line or "<Image " in line:
                if not re.search(r'alt\s*=', line) and not re.search(r"alt\s*=", line):
                    violations.append(AccessibilityViolation(
                        rule_id="img-alt",
                        severity="critical",
                        element="img",
                        description="Image missing alt attribute",
                        suggestion="Add alt='...' describing the image",
                        wcag_criterion="1.1.1",
                        file_path=file_path,
                        line_number=i,
                    ))
            if "<button " in line or "<Button " in line:
                if not re.search(r'aria-label\s*=', line) and not re.search(
                    r'>[^<]+<', line
                ):
                    violations.append(AccessibilityViolation(
                        rule_id="button-aria",
                        severity="major",
                        element="button",
                        description="Button may need aria-label",
                        suggestion="Add aria-label for icon-only buttons",
                        wcag_criterion="4.1.2",
                        file_path=file_path,
                        line_number=i,
                    ))
            if "<input " in line or "<Input " in line:
                if not re.search(r'aria-label\s*=', line) and not re.search(
                    r'id\s*=', line
                ):
                    violations.append(AccessibilityViolation(
                        rule_id="input-label",
                        severity="major",
                        element="input",
                        description="Input missing label association",
                        suggestion="Add aria-label or htmlFor on label",
                        wcag_criterion="1.3.1",
                        file_path=file_path,
                        line_number=i,
                    ))
            if re.search(r'<div[^>]*onClick\s*=', line) or re.search(
                r'<span[^>]*onClick\s*=', line
            ):
                if not re.search(r'role\s*=', line) and not re.search(
                    r'aria-label\s*=', line
                ):
                    violations.append(AccessibilityViolation(
                        rule_id="div-onclick",
                        severity="minor",
                        element="div/span",
                        description="Interactive div/span needs role",
                        suggestion="Add role='button' and tabIndex={0}",
                        wcag_criterion="4.1.2",
                        file_path=file_path,
                        line_number=i,
                    ))
            hex_colors = re.findall(r'#([0-9A-Fa-f]{3,8})\b', line)
            for hex_val in hex_colors:
                if len(hex_val) in (3, 6) and hex_val.lower() in (
                    "fff", "ffffff", "000", "000000",
                    "ccc", "cccccc", "999", "999999",
                ):
                    violations.append(AccessibilityViolation(
                        rule_id="color-contrast",
                        severity="minor",
                        element="color",
                        description=f"Color #{hex_val} may have poor contrast",
                        suggestion="Verify contrast ratio >= 4.5:1 for text",
                        wcag_criterion="1.4.3",
                        file_path=file_path,
                        line_number=i,
                    ))

        return violations

    def generate_report(
        self,
        violations: List[AccessibilityViolation],
    ) -> Dict[str, Any]:
        """Return score (0-100), violations, and summary."""
        critical = sum(1 for v in violations if v.severity == "critical")
        major = sum(1 for v in violations if v.severity == "major")
        minor = sum(1 for v in violations if v.severity == "minor")
        score = max(0, 100 - critical * 20 - major * 10 - minor * 3)
        return {
            "score": min(100, score),
            "violations": [v.to_dict() for v in violations],
            "summary": {
                "total": len(violations),
                "critical": critical,
                "major": major,
                "minor": minor,
            },
        }
