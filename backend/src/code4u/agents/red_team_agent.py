"""Red Team Agent — Logic Exploitation & Zero-Day Discovery.

Performs offensive security analysis to find:
- Unprotected API endpoints
- Race conditions (TOCTOU)
- Business logic flaws
- Privilege escalation paths
- State manipulation vulnerabilities
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger("red_team_agent")


@dataclass
class Exploit:
    """A discovered logic exploit."""
    exploit_id: str
    category: str
    title: str
    description: str
    severity: str
    file_path: str = ""
    line_number: int = 0
    evidence: str = ""
    remediation: str = ""
    exploitability: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exploitId": self.exploit_id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "evidence": self.evidence[:200] if self.evidence else "",
            "remediation": self.remediation,
            "exploitability": round(self.exploitability, 2),
        }


class RedTeamAgent:
    """Offensive security agent that searches for zero-day-like logic flaws."""

    def __init__(self) -> None:
        self._exploits: List[Exploit] = []
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"RT-{self._counter:04d}"

    def scan_for_race_conditions(self, code_map: Dict[str, str]) -> List[Exploit]:
        """Detect Time-of-Check to Time-of-Use (TOCTOU) patterns."""
        exploits: List[Exploit] = []
        toctou_patterns = [
            (r'if\s+os\.path\.exists\(.+\).*\n.*open\(', "File TOCTOU: check-then-open race"),
            (r'if\s+.*\.count\s*\(.*\)\s*[<>=].*\n.*\.(insert|create|add)', "DB TOCTOU: count-then-insert race"),
            (r'balance\s*=.*get.*\n.*if\s+balance\s*[><=].*\n.*\.(update|subtract|deduct)', "Financial TOCTOU: read-then-write race"),
            (r'if\s+not\s+.*exists.*\n.*\.(save|write|create)', "Create-if-not-exists without lock"),
        ]
        for filepath, content in code_map.items():
            for pattern, desc in toctou_patterns:
                matches = list(re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE))
                for m in matches:
                    line = content[:m.start()].count("\n") + 1
                    exploits.append(Exploit(
                        exploit_id=self._next_id(),
                        category="race_condition",
                        title="TOCTOU Race Condition",
                        description=desc,
                        severity="high",
                        file_path=filepath,
                        line_number=line,
                        evidence=m.group()[:100],
                        remediation="Use atomic operations or file locks. Wrap check+action in a transaction.",
                        exploitability=0.7,
                    ))
        return exploits

    def scan_for_unprotected_endpoints(self, code_map: Dict[str, str]) -> List[Exploit]:
        """Find API routes that lack authentication or authorization checks."""
        exploits: List[Exploit] = []
        for filepath, content in code_map.items():
            if not filepath.endswith(".py"):
                continue
            route_matches = re.finditer(
                r'@(router|app)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
                content,
            )
            for m in route_matches:
                route_path = m.group(3)
                line = content[:m.start()].count("\n") + 1
                context_start = max(0, m.start() - 200)
                context = content[context_start:m.end() + 500]
                has_auth = any(kw in context.lower() for kw in [
                    "depends(", "current_user", "auth", "jwt", "token",
                    "permission", "role", "x_tenant", "tenant_id",
                ])
                is_public = any(kw in route_path for kw in [
                    "/health", "/docs", "/openapi", "/login", "/register", "/public",
                ])
                if not has_auth and not is_public and "/api" in route_path:
                    exploits.append(Exploit(
                        exploit_id=self._next_id(),
                        category="unprotected_endpoint",
                        title=f"Unprotected API: {m.group(2).upper()} {route_path}",
                        description=f"Route {route_path} appears to lack authentication checks",
                        severity="high",
                        file_path=filepath,
                        line_number=line,
                        evidence=f"{m.group(2).upper()} {route_path}",
                        remediation="Add authentication dependency (Depends(get_current_user)) or verify it is intentionally public",
                        exploitability=0.8,
                    ))
        return exploits

    def scan_for_privilege_escalation(self, code_map: Dict[str, str]) -> List[Exploit]:
        """Find potential privilege escalation paths."""
        exploits: List[Exploit] = []
        patterns = [
            (r'role\s*=\s*["\']admin["\']', "Hardcoded admin role assignment"),
            (r'is_admin\s*=\s*True', "Hardcoded admin flag"),
            (r'\.update\s*\(\s*\{[^}]*["\']role["\']', "Direct role update without validation"),
            (r'request\.(json|body|data).*\[?["\']role', "Role from user input without validation"),
        ]
        for filepath, content in code_map.items():
            for pattern, desc in patterns:
                for m in re.finditer(pattern, content, re.IGNORECASE):
                    line = content[:m.start()].count("\n") + 1
                    exploits.append(Exploit(
                        exploit_id=self._next_id(),
                        category="privilege_escalation",
                        title="Potential Privilege Escalation",
                        description=desc,
                        severity="critical",
                        file_path=filepath,
                        line_number=line,
                        evidence=m.group()[:100],
                        remediation="Enforce role changes through a dedicated admin-only service with audit logging",
                        exploitability=0.85,
                    ))
        return exploits

    def scan_for_business_logic_flaws(self, code_map: Dict[str, str]) -> List[Exploit]:
        """Find business logic vulnerabilities."""
        exploits: List[Exploit] = []
        patterns = [
            (r'if.*price\s*[<>=].*0', "Negative price check may be missing — allows free purchases"),
            (r'quantity\s*=.*int\(.*input', "User-controlled quantity without bounds"),
            (r'discount\s*=.*float\(.*request', "User-controlled discount from request"),
            (r'limit\s*=.*int\(.*request', "User-controlled limit — potential DoS via large values"),
        ]
        for filepath, content in code_map.items():
            for pattern, desc in patterns:
                for m in re.finditer(pattern, content, re.IGNORECASE):
                    line = content[:m.start()].count("\n") + 1
                    exploits.append(Exploit(
                        exploit_id=self._next_id(),
                        category="business_logic",
                        title="Business Logic Flaw",
                        description=desc,
                        severity="medium",
                        file_path=filepath,
                        line_number=line,
                        evidence=m.group()[:100],
                        remediation="Add server-side validation with explicit bounds. Never trust client-provided values for pricing or limits.",
                        exploitability=0.6,
                    ))
        return exploits

    def scan_for_state_manipulation(self, code_map: Dict[str, str]) -> List[Exploit]:
        """Find state manipulation vulnerabilities."""
        exploits: List[Exploit] = []
        patterns = [
            (r'session\[.*\]\s*=.*request', "Session state set from user input"),
            (r'global\s+\w+.*\n.*=.*request', "Global state modified by request"),
            (r'cache\.(set|put)\s*\(.*request', "Cache poisoning from user input"),
        ]
        for filepath, content in code_map.items():
            for pattern, desc in patterns:
                for m in re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE):
                    line = content[:m.start()].count("\n") + 1
                    exploits.append(Exploit(
                        exploit_id=self._next_id(),
                        category="state_manipulation",
                        title="State Manipulation Risk",
                        description=desc,
                        severity="high",
                        file_path=filepath,
                        line_number=line,
                        evidence=m.group()[:100],
                        remediation="Validate and sanitize all user input before storing in session/cache/globals",
                        exploitability=0.65,
                    ))
        return exploits

    def run_full_red_team(self, code_map: Dict[str, str]) -> Dict[str, Any]:
        """Execute the full red team scan."""
        self._exploits = []
        self._counter = 0

        self._exploits.extend(self.scan_for_race_conditions(code_map))
        self._exploits.extend(self.scan_for_unprotected_endpoints(code_map))
        self._exploits.extend(self.scan_for_privilege_escalation(code_map))
        self._exploits.extend(self.scan_for_business_logic_flaws(code_map))
        self._exploits.extend(self.scan_for_state_manipulation(code_map))

        severity_counts = {}
        for e in self._exploits:
            severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1

        category_counts = {}
        for e in self._exploits:
            category_counts[e.category] = category_counts.get(e.category, 0) + 1

        return {
            "exploits": [e.to_dict() for e in self._exploits],
            "totalExploits": len(self._exploits),
            "severityCounts": severity_counts,
            "categoryCounts": category_counts,
            "overallRisk": "critical" if severity_counts.get("critical", 0) > 0
                else "high" if severity_counts.get("high", 0) > 0
                else "medium" if severity_counts.get("medium", 0) > 0
                else "low",
        }

    def generate_report(self) -> str:
        """Generate Markdown red team report."""
        lines = [
            "# Red Team Report",
            "",
            f"**Total Exploits Found:** {len(self._exploits)}",
            "",
            "## Exploits by Severity",
            "",
        ]
        for sev in ["critical", "high", "medium", "low"]:
            items = [e for e in self._exploits if e.severity == sev]
            if items:
                lines.append(f"### {sev.upper()} ({len(items)})")
                lines.append("")
                for e in items:
                    lines.append(f"#### {e.exploit_id}: {e.title}")
                    lines.append(f"- **Category:** {e.category}")
                    lines.append(f"- **Description:** {e.description}")
                    if e.file_path:
                        lines.append(f"- **File:** {e.file_path}:{e.line_number}")
                    lines.append(f"- **Exploitability:** {e.exploitability*100:.0f}%")
                    lines.append(f"- **Remediation:** {e.remediation}")
                    lines.append("")
        return "\n".join(lines)
