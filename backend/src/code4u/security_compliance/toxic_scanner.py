"""Toxic Snippet Scanner — Forbidden Pattern Detection.

Scans proposed code against a database of forbidden patterns:
- Known leaked codebase signatures
- Ethically questionable algorithms
- Unauthorized scraping patterns
- Discriminatory/biased code patterns
- License-contaminated snippets
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("toxic_scanner")


@dataclass
class ToxicMatch:
    """A detected forbidden pattern match."""
    match_id: str
    category: str
    severity: str
    pattern_name: str
    file_path: str
    line_number: int
    matched_text: str
    description: str
    remediation: str
    blocked: bool
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matchId": self.match_id,
            "category": self.category,
            "severity": self.severity,
            "patternName": self.pattern_name,
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "matchedText": self.matched_text[:200],
            "description": self.description,
            "remediation": self.remediation,
            "blocked": self.blocked,
            "timestamp": self.timestamp,
        }


FORBIDDEN_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "unauthorized_scraping_headers",
        "category": "ethical",
        "severity": "high",
        "pattern": r"(?:User-Agent|user-agent)\s*[=:]\s*['\"](?:Googlebot|Bingbot|Mozilla/5\.0.*Googlebot)",
        "description": "Unauthorized impersonation of search engine crawlers",
        "remediation": "Use your own User-Agent string that identifies your application",
        "blocked": True,
    },
    {
        "name": "scraping_rate_bypass",
        "category": "ethical",
        "severity": "high",
        "pattern": r"robots\.txt.*(?:ignore|bypass|skip|disable)",
        "description": "Attempting to bypass robots.txt restrictions",
        "remediation": "Respect robots.txt and implement proper rate limiting",
        "blocked": True,
    },
    {
        "name": "biased_threshold_gender",
        "category": "bias",
        "severity": "critical",
        "pattern": r"(?:if|when|where)\s*.*(?:gender|sex)\s*(?:==|===|!=|!==|is)\s*['\"](?:male|female|man|woman)",
        "description": "Gender-based conditional logic that may introduce discrimination",
        "remediation": "Remove gender-based branching unless medically/legally required. Use inclusive logic.",
        "blocked": False,
    },
    {
        "name": "biased_threshold_race",
        "category": "bias",
        "severity": "critical",
        "pattern": r"(?:if|when|where)\s*.*(?:race|ethnicity|skin_color)\s*(?:==|===|!=|!==|is)\s*['\"]",
        "description": "Race/ethnicity-based conditional logic that may introduce discrimination",
        "remediation": "Remove race-based branching. Ensure algorithms are fair and unbiased.",
        "blocked": True,
    },
    {
        "name": "facial_recognition_untrained",
        "category": "bias",
        "severity": "high",
        "pattern": r"(?:face_recognition|deepface|dlib\.face|cv2\.CascadeClassifier).*(?:predict|detect|classify)",
        "description": "Facial recognition without documented bias mitigation",
        "remediation": "Ensure facial recognition models are tested for bias across demographics. Add bias audit documentation.",
        "blocked": False,
    },
    {
        "name": "credit_scoring_discrimination",
        "category": "bias",
        "severity": "critical",
        "pattern": r"(?:credit_score|risk_score|loan_approval)\s*.*(?:zip_code|postal_code|neighborhood|address)",
        "description": "Location-based credit scoring may constitute redlining",
        "remediation": "Remove geographic proxies from credit decisions. Use only permissible factors.",
        "blocked": True,
    },
    {
        "name": "leaked_codebase_oracle",
        "category": "leaked_code",
        "severity": "critical",
        "pattern": r"(?:OracleJDBC|oracle\.jdbc|ojdbc)\s*.*(?:Copyright\s*\(c\)\s*Oracle|ORACLE PROPRIETARY)",
        "description": "Potentially leaked Oracle proprietary code signatures detected",
        "remediation": "Remove proprietary Oracle code. Use officially licensed libraries.",
        "blocked": True,
    },
    {
        "name": "leaked_codebase_windows",
        "category": "leaked_code",
        "severity": "critical",
        "pattern": r"(?:Microsoft\s+Corporation\s+proprietary|WINDOWS\s+SOURCE\s+CODE|ntoskrnl|win32kfull)",
        "description": "Potentially leaked Microsoft/Windows proprietary code signatures",
        "remediation": "Remove proprietary Microsoft code immediately.",
        "blocked": True,
    },
    {
        "name": "crypto_mining_stealth",
        "category": "malware",
        "severity": "critical",
        "pattern": r"(?:coinhive|cryptonight|stratum\+tcp://|xmrig|minergate|pool\.mining)",
        "description": "Cryptocurrency mining code detected",
        "remediation": "Remove crypto mining code unless it is the intended purpose of the application.",
        "blocked": True,
    },
    {
        "name": "data_exfiltration",
        "category": "malware",
        "severity": "critical",
        "pattern": r"(?:btoa|encode)\s*\(\s*(?:document\.cookie|localStorage|sessionStorage).*(?:fetch|XMLHttpRequest|navigator\.sendBeacon)",
        "description": "Data exfiltration pattern: encoding sensitive browser data and sending externally",
        "remediation": "Remove data exfiltration logic. Audit all outbound data flows.",
        "blocked": True,
    },
    {
        "name": "keylogger_pattern",
        "category": "malware",
        "severity": "critical",
        "pattern": r"(?:addEventListener|on)\s*\(\s*['\"]key(?:down|press|up)['\"]\s*.*(?:fetch|XMLHttpRequest|navigator\.sendBeacon|WebSocket)",
        "description": "Potential keylogger: capturing keystrokes and transmitting externally",
        "remediation": "Remove keylogging code. Only capture keyboard events for legitimate UI functionality.",
        "blocked": True,
    },
    {
        "name": "backdoor_eval",
        "category": "malware",
        "severity": "critical",
        "pattern": r"eval\s*\(\s*(?:atob|Buffer\.from|base64_decode)\s*\(",
        "description": "Encoded eval/exec — potential backdoor or obfuscated malware",
        "remediation": "Remove obfuscated code execution. All code must be readable and auditable.",
        "blocked": True,
    },
    {
        "name": "surveillance_camera_access",
        "category": "ethical",
        "severity": "high",
        "pattern": r"(?:navigator\.mediaDevices|getUserMedia|rtsp://|onvif)\s*.*(?:without.*consent|hidden|stealth|background)",
        "description": "Camera/microphone access without explicit user consent",
        "remediation": "Always request and display user consent before accessing camera or microphone.",
        "blocked": True,
    },
    {
        "name": "dark_pattern_forced_consent",
        "category": "ethical",
        "severity": "high",
        "pattern": r"(?:opt_out|unsubscribe|reject)\s*.*(?:display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0|font-size\s*:\s*0)",
        "description": "Dark pattern: hiding opt-out/unsubscribe controls from users",
        "remediation": "Make all user choice controls clearly visible and accessible.",
        "blocked": True,
    },
    {
        "name": "price_discrimination",
        "category": "ethical",
        "severity": "high",
        "pattern": r"(?:price|cost|fee|rate)\s*.*(?:user_agent|platform|os_version|device_type|location|ip_address)",
        "description": "Dynamic pricing based on user device/location may constitute price discrimination",
        "remediation": "Ensure pricing is transparent and not discriminatory based on device or location.",
        "blocked": False,
    },
]


class ToxicScanner:
    """Scans code for forbidden/toxic patterns."""

    def __init__(self) -> None:
        self._matches: List[ToxicMatch] = []
        self._custom_patterns: List[Dict[str, Any]] = []

    def scan_code(
        self,
        code_map: Dict[str, str],
    ) -> List[ToxicMatch]:
        """Scan a code map for forbidden patterns."""
        matches: List[ToxicMatch] = []
        all_patterns = FORBIDDEN_PATTERNS + self._custom_patterns

        for filepath, content in code_map.items():
            lines = content.splitlines()
            for pattern_def in all_patterns:
                regex = pattern_def["pattern"]
                try:
                    for i, line in enumerate(lines, 1):
                        if re.search(regex, line, re.IGNORECASE):
                            match = ToxicMatch(
                                match_id=str(uuid.uuid4()),
                                category=pattern_def["category"],
                                severity=pattern_def["severity"],
                                pattern_name=pattern_def["name"],
                                file_path=filepath,
                                line_number=i,
                                matched_text=line.strip(),
                                description=pattern_def["description"],
                                remediation=pattern_def["remediation"],
                                blocked=pattern_def.get("blocked", False),
                                timestamp=time.time(),
                            )
                            matches.append(match)
                except re.error:
                    logger.warning("invalid_pattern", name=pattern_def["name"])
                    continue

        self._matches.extend(matches)
        logger.info("toxic_scan_complete", files=len(code_map), matches=len(matches))
        return matches

    def scan_text(self, text: str, filepath: str = "<inline>") -> List[ToxicMatch]:
        """Scan a single text for forbidden patterns."""
        return self.scan_code({filepath: text})

    def add_custom_pattern(
        self,
        name: str,
        pattern: str,
        category: str = "custom",
        severity: str = "medium",
        description: str = "",
        remediation: str = "",
        blocked: bool = False,
    ) -> None:
        """Add a custom forbidden pattern."""
        self._custom_patterns.append({
            "name": name,
            "pattern": pattern,
            "category": category,
            "severity": severity,
            "description": description or f"Custom pattern: {name}",
            "remediation": remediation or "Review and remove flagged code.",
            "blocked": blocked,
        })
        logger.info("custom_pattern_added", name=name)

    def has_blocking_matches(self, matches: Optional[List[ToxicMatch]] = None) -> bool:
        """Check if any matches require blocking."""
        target = matches if matches is not None else self._matches
        return any(m.blocked for m in target)

    def get_all_matches(self) -> List[ToxicMatch]:
        return list(self._matches)

    def get_stats(self) -> Dict[str, Any]:
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        blocked_count = 0
        for m in self._matches:
            by_category[m.category] = by_category.get(m.category, 0) + 1
            by_severity[m.severity] = by_severity.get(m.severity, 0) + 1
            if m.blocked:
                blocked_count += 1
        return {
            "totalMatches": len(self._matches),
            "blockedMatches": blocked_count,
            "byCategory": by_category,
            "bySeverity": by_severity,
            "customPatterns": len(self._custom_patterns),
        }

    def clear(self) -> int:
        count = len(self._matches)
        self._matches.clear()
        return count

    def generate_report(self) -> str:
        """Generate a Markdown toxic scan report."""
        lines = [
            "# Toxic Snippet Scan Report",
            "",
            f"**Total Matches:** {len(self._matches)}",
            f"**Blocked:** {sum(1 for m in self._matches if m.blocked)}",
            "",
        ]
        if not self._matches:
            lines.append("No forbidden patterns detected. Code is clean.")
        else:
            by_cat: Dict[str, List[ToxicMatch]] = {}
            for m in self._matches:
                by_cat.setdefault(m.category, []).append(m)
            for cat, matches in by_cat.items():
                lines.append(f"## {cat.replace('_', ' ').title()}")
                lines.append("")
                for m in matches:
                    icon = "BLOCKED" if m.blocked else "WARNING"
                    lines.append(f"### [{icon}] {m.pattern_name}")
                    lines.append(f"- **File:** {m.file_path}:{m.line_number}")
                    lines.append(f"- **Severity:** {m.severity}")
                    lines.append(f"- **Description:** {m.description}")
                    lines.append(f"- **Remediation:** {m.remediation}")
                    lines.append("")
        return "\n".join(lines)


_scanner_singleton: Optional[ToxicScanner] = None


def get_toxic_scanner() -> ToxicScanner:
    global _scanner_singleton
    if _scanner_singleton is None:
        _scanner_singleton = ToxicScanner()
    return _scanner_singleton
