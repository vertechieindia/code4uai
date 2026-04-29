"""Predictive Risk Agent — Proactive Bug Detection.

Analyzes code diffs against historical hotspot data to predict
where the next regression will occur. Adds "Predictive Warnings"
to the Titan Audit Report for files that "look like" past
regression patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger("predictor_agent")


@dataclass
class PredictiveWarning:
    """Single predictive warning for a file."""

    file_path: str
    risk_level: str
    confidence: float
    reason: str
    recommendation: str
    pattern_match: str
    churn_score: float
    complexity_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "riskLevel": self.risk_level,
            "confidence": self.confidence,
            "reason": self.reason,
            "recommendation": self.recommendation,
            "patternMatch": self.pattern_match,
            "churnScore": self.churn_score,
            "complexityScore": self.complexity_score,
        }


@dataclass
class DiffAnalysis:
    """Analysis of a single file diff."""

    file_path: str
    lines_added: int
    lines_removed: int
    functions_modified: List[str]
    is_new_file: bool
    touches_error_handling: bool
    touches_auth_logic: bool
    touches_data_validation: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filePath": self.file_path,
            "linesAdded": self.lines_added,
            "linesRemoved": self.lines_removed,
            "functionsModified": self.functions_modified,
            "isNewFile": self.is_new_file,
            "touchesErrorHandling": self.touches_error_handling,
            "touchesAuthLogic": self.touches_auth_logic,
            "touchesDataValidation": self.touches_data_validation,
        }


class PredictorAgent:
    """Predicts regressions based on diff patterns and historical hotspots."""

    REGRESSION_PATTERNS = [
        {
            "name": "error_handling_change",
            "pattern": r"(except|catch|try|finally|raise|throw)\b",
            "weight": 1.5,
            "reason": "Changes to error handling code frequently introduce silent failures",
        },
        {
            "name": "auth_logic_change",
            "pattern": r"(authenticate|authorize|permission|role|token|jwt|session)\b",
            "weight": 2.0,
            "reason": "Authentication/authorization changes are high-risk for security regressions",
        },
        {
            "name": "data_validation_change",
            "pattern": r"(validate|sanitize|escape|encode|decode|serialize)\b",
            "weight": 1.8,
            "reason": "Data validation changes can introduce injection vulnerabilities",
        },
        {
            "name": "concurrency_change",
            "pattern": r"(async|await|thread|lock|mutex|semaphore|atomic|concurrent)\b",
            "weight": 2.0,
            "reason": "Concurrency changes are prone to race conditions and deadlocks",
        },
        {
            "name": "database_change",
            "pattern": r"(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|migration)\b",
            "weight": 1.7,
            "reason": "Database changes risk data loss or migration failures",
        },
        {
            "name": "config_change",
            "pattern": r"(config|settings|env|environment|\.env|secret)\b",
            "weight": 1.4,
            "reason": "Configuration changes can break different environments",
        },
        {
            "name": "api_contract_change",
            "pattern": r"(endpoint|route|response|request|schema|payload|header)\b",
            "weight": 1.6,
            "reason": "API contract changes can break downstream consumers",
        },
    ]

    def __init__(self) -> None:
        self._hotspot_cache: Dict[str, Any] = {}

    def analyze_diff(self, file_path: str, diff_content: str) -> DiffAnalysis:
        """Analyze a single file diff for risk indicators."""
        lines = diff_content.splitlines()
        added = sum(
            1 for l in lines if l.startswith("+") and not l.startswith("+++")
        )
        removed = sum(
            1 for l in lines if l.startswith("-") and not l.startswith("---")
        )

        functions_modified = []
        for line in lines:
            if line.startswith("+") or line.startswith("-"):
                func_match = re.search(r"def (\w+)", line) or re.search(
                    r"function (\w+)", line
                )
                if func_match and func_match.group(1) not in functions_modified:
                    functions_modified.append(func_match.group(1))

        is_new = all(
            l.startswith("+") or l.startswith("+++") or not l.strip()
            for l in lines
            if l.strip()
        )

        touches_error = bool(
            re.search(
                r"(except|catch|try|finally|raise|throw)\b", diff_content
            )
        )
        touches_auth = bool(
            re.search(
                r"(auth|permission|role|token|jwt|session)\b",
                diff_content,
                re.I,
            )
        )
        touches_validation = bool(
            re.search(
                r"(validate|sanitize|escape|encode)\b", diff_content, re.I
            )
        )

        return DiffAnalysis(
            file_path=file_path,
            lines_added=added,
            lines_removed=removed,
            functions_modified=functions_modified,
            is_new_file=is_new,
            touches_error_handling=touches_error,
            touches_auth_logic=touches_auth,
            touches_data_validation=touches_validation,
        )

    def predict_risks(
        self,
        diffs: Dict[str, str],
        hotspots: List[Dict[str, Any]],
    ) -> List[PredictiveWarning]:
        """Predict regression risks for a set of file diffs."""
        hotspot_map = {
            h.get("filePath", h.get("file_path", "")): h for h in hotspots
        }
        warnings: List[PredictiveWarning] = []

        for file_path, diff_content in diffs.items():
            analysis = self.analyze_diff(file_path, diff_content)
            file_warnings = self._assess_file_risk(
                file_path, diff_content, analysis, hotspot_map
            )
            warnings.extend(file_warnings)

        warnings.sort(key=lambda w: w.confidence, reverse=True)
        return warnings

    def _assess_file_risk(
        self,
        file_path: str,
        diff_content: str,
        analysis: DiffAnalysis,
        hotspot_map: Dict[str, Any],
    ) -> List[PredictiveWarning]:
        """Assess risk for a single file based on patterns and hotspot data."""
        warnings: List[PredictiveWarning] = []

        hotspot = hotspot_map.get(file_path)
        churn_score = (
            hotspot.get("riskScore", hotspot.get("risk_score", 0))
            if hotspot
            else 0.0
        )
        complexity_score = 0.0
        if hotspot and "complexity" in hotspot:
            comp = hotspot["complexity"]
            complexity_score = comp.get(
                "cyclomaticComplexity",
                comp.get("cyclomatic_complexity", 0),
            )

        for pattern_def in self.REGRESSION_PATTERNS:
            matches = re.findall(
                pattern_def["pattern"], diff_content, re.I
            )
            if matches:
                base_confidence = min(len(matches) * 0.1, 0.5)

                if hotspot and churn_score > 30:
                    base_confidence = min(base_confidence + 0.3, 0.95)

                if complexity_score > 20:
                    base_confidence = min(base_confidence + 0.15, 0.95)

                if analysis.lines_added + analysis.lines_removed > 50:
                    base_confidence = min(base_confidence + 0.1, 0.95)

                risk_level = (
                    "critical"
                    if base_confidence > 0.8
                    else "high"
                    if base_confidence > 0.6
                    else "medium"
                    if base_confidence > 0.3
                    else "low"
                )

                recommendation = self._generate_recommendation(
                    pattern_def["name"], analysis, churn_score
                )

                warnings.append(
                    PredictiveWarning(
                        file_path=file_path,
                        risk_level=risk_level,
                        confidence=round(base_confidence, 2),
                        reason=pattern_def["reason"],
                        recommendation=recommendation,
                        pattern_match=pattern_def["name"],
                        churn_score=churn_score,
                        complexity_score=complexity_score,
                    )
                )

        if hotspot and churn_score > 50 and not warnings:
            warnings.append(
                PredictiveWarning(
                    file_path=file_path,
                    risk_level="high" if churn_score > 70 else "medium",
                    confidence=min(churn_score / 100, 0.9),
                    reason=f"This file is a known hotspot with {churn_score:.0f} risk score. Any change increases regression probability.",
                    recommendation="Add focused unit tests for modified functions. Consider pair review.",
                    pattern_match="hotspot_file",
                    churn_score=churn_score,
                    complexity_score=complexity_score,
                )
            )

        return warnings

    def _generate_recommendation(
        self,
        pattern_name: str,
        analysis: DiffAnalysis,
        churn_score: float,
    ) -> str:
        """Generate actionable recommendation based on pattern."""
        recs = {
            "error_handling_change": "Add explicit error recovery tests. Verify all exception paths have proper logging.",
            "auth_logic_change": "Security review required. Run penetration tests on affected endpoints. Verify token validation edge cases.",
            "data_validation_change": "Fuzz test all input paths. Verify encoding/decoding round-trips. Check for injection vectors.",
            "concurrency_change": "Add stress tests. Run race condition detector. Verify lock ordering consistency.",
            "database_change": "Test migration rollback. Verify data integrity post-migration. Check for N+1 query patterns.",
            "config_change": "Verify all environment configurations. Test with missing/malformed env vars.",
            "api_contract_change": "Run API compatibility tests. Check for breaking changes in request/response schemas.",
        }
        base = recs.get(pattern_name, "Manual review recommended.")
        if churn_score > 50:
            base += f" HIGH CHURN FILE (score: {churn_score:.0f}) — extra review needed."
        return base

    def generate_report(self, warnings: List[PredictiveWarning]) -> str:
        """Generate Markdown report of predictive warnings."""
        lines = [
            "# Predictive Risk Report",
            "",
            f"**Total Warnings:** {len(warnings)}",
            f"**Critical:** {sum(1 for w in warnings if w.risk_level == 'critical')}",
            f"**High:** {sum(1 for w in warnings if w.risk_level == 'high')}",
            "",
            "## Warnings",
            "",
        ]
        for w in warnings:
            icon = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
            }.get(w.risk_level, "⚪")
            lines.append(
                f"### {icon} {w.file_path} ({w.risk_level.upper()}, {w.confidence*100:.0f}% confidence)"
            )
            lines.append(f"- **Pattern:** {w.pattern_match}")
            lines.append(f"- **Reason:** {w.reason}")
            lines.append(f"- **Recommendation:** {w.recommendation}")
            if w.churn_score > 0:
                lines.append(f"- **Churn Score:** {w.churn_score:.0f}")
            lines.append("")
        return "\n".join(lines)
