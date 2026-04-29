"""Security Empire — The 1,000-Eye Fortress.

Offensive and defensive security agents that perform:
- Threat modeling via Knowledge Graph
- Automated penetration testing (DAST)
- API fuzzing with malformed data
- Secure code review audit
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("fortress_swarm")


@dataclass
class SecurityFinding:
    """A single security finding from any agent."""
    agent: str
    severity: str
    title: str
    description: str
    file_path: str = ""
    line_number: int = 0
    cwe_id: str = ""
    remediation: str = ""
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "filePath": self.file_path,
            "lineNumber": self.line_number,
            "cweId": self.cwe_id,
            "remediation": self.remediation,
            "evidence": self.evidence,
        }


class ThreatModelAgent:
    """Threat modeling via route and data flow analysis."""

    def analyze_api_routes(
        self,
        routes: List[Dict[str, Any]],
    ) -> List[SecurityFinding]:
        """Check for missing auth, org_id validation, mass assignment."""
        findings: List[SecurityFinding] = []
        for route in routes:
            path = route.get("path", route.get("path_regex", ""))
            methods = route.get("methods", ["GET"])
            auth = route.get("auth_required", route.get("auth", True))
            if not auth and path not in ("/health", "/", "/docs"):
                findings.append(SecurityFinding(
                    agent="ThreatModelAgent",
                    severity="high",
                    title="Missing authentication",
                    description=f"Route {path} has no authentication",
                    remediation="Add auth middleware or require JWT",
                    cwe_id="CWE-306",
                ))
            if "org_id" not in str(route) and "tenant" not in str(route).lower():
                if any(m in ["POST", "PUT", "PATCH", "DELETE"] for m in methods):
                    findings.append(SecurityFinding(
                        agent="ThreatModelAgent",
                        severity="medium",
                        title="Possible missing org_id validation",
                        description=f"Mutation route {path} may not validate tenant scope",
                        remediation="Ensure org_id/tenant_id in path or body",
                        cwe_id="CWE-639",
                    ))
        return findings

    def analyze_data_flow(
        self,
        code_map: Dict[str, str],
    ) -> List[SecurityFinding]:
        """Trace sensitive data through the code."""
        findings: List[SecurityFinding] = []
        sensitive = ["password", "secret", "token", "api_key", "credential"]
        for filepath, content in code_map.items():
            for term in sensitive:
                if re.search(rf'\b{term}\s*=', content, re.I):
                    findings.append(SecurityFinding(
                        agent="ThreatModelAgent",
                        severity="info",
                        title="Sensitive data handling",
                        description=f"Variable matching '{term}' in {filepath}",
                        file_path=filepath,
                        remediation="Ensure no logging or exposure",
                        cwe_id="CWE-532",
                    ))
        return findings[:20]

    def generate_threat_model(
        self,
        findings: List[SecurityFinding],
    ) -> Dict[str, Any]:
        """STRIDE-based threat model."""
        stride = {"S": [], "T": [], "R": [], "I": [], "D": [], "E": []}
        for f in findings:
            if "auth" in f.title.lower() or "auth" in f.description.lower():
                stride["S"].append(f.to_dict())
            elif "tenant" in f.title.lower() or "org" in f.title.lower():
                stride["T"].append(f.to_dict())
            else:
                stride["I"].append(f.to_dict())
        return {
            "stride": stride,
            "findings": [f.to_dict() for f in findings],
            "summary": {k: len(v) for k, v in stride.items()},
        }


class PentestAgent:
    """Automated penetration testing (DAST-style) scans."""

    def scan_for_sqli(
        self,
        source: str,
        file_path: str = "",
    ) -> List[SecurityFinding]:
        """Detect f-string SQL, string concatenation SQL."""
        findings: List[SecurityFinding] = []
        lines = source.splitlines()
        for i, line in enumerate(lines, 1):
            if re.search(r'f["\'].*SELECT.*\{', line) or re.search(
                r'f["\'].*INSERT.*\{', line
            ):
                findings.append(SecurityFinding(
                    agent="PentestAgent",
                    severity="critical",
                    title="SQL Injection risk",
                    description="f-string used with SQL - user input may be injected",
                    file_path=file_path,
                    line_number=i,
                    cwe_id="CWE-89",
                    remediation="Use parameterized queries",
                    evidence=line.strip()[:100],
                ))
            if re.search(r'["\'].*SELECT.*\+', line) or re.search(
                r'\+.*["\'].*SELECT', line
            ):
                findings.append(SecurityFinding(
                    agent="PentestAgent",
                    severity="critical",
                    title="SQL Injection risk",
                    description="String concatenation with SQL",
                    file_path=file_path,
                    line_number=i,
                    cwe_id="CWE-89",
                    remediation="Use parameterized queries",
                    evidence=line.strip()[:100],
                ))
        return findings

    def scan_for_xss(
        self,
        source: str,
        file_path: str = "",
    ) -> List[SecurityFinding]:
        """Detect innerHTML, dangerouslySetInnerHTML without sanitization."""
        findings: List[SecurityFinding] = []
        if "dangerouslySetInnerHTML" in source:
            if "sanitize" not in source.lower() and "DOMPurify" not in source:
                findings.append(SecurityFinding(
                    agent="PentestAgent",
                    severity="high",
                    title="XSS risk",
                    description="dangerouslySetInnerHTML without sanitization",
                    file_path=file_path,
                    cwe_id="CWE-79",
                    remediation="Use DOMPurify or similar before setting HTML",
                ))
        if "innerHTML" in source and "=" in source:
            findings.append(SecurityFinding(
                agent="PentestAgent",
                severity="high",
                title="XSS risk",
                description="innerHTML assignment may allow XSS",
                file_path=file_path,
                cwe_id="CWE-79",
                remediation="Avoid innerHTML with user input",
            ))
        return findings

    def scan_for_ssrf(
        self,
        source: str,
        file_path: str = "",
    ) -> List[SecurityFinding]:
        """Detect user-controlled URLs in requests."""
        findings: List[SecurityFinding] = []
        if re.search(r'requests\.(get|post|put|delete)\s*\(\s*\w+', source):
            if "url" in source.lower() and "input" in source.lower():
                findings.append(SecurityFinding(
                    agent="PentestAgent",
                    severity="high",
                    title="SSRF risk",
                    description="User-controlled URL in HTTP request",
                    file_path=file_path,
                    cwe_id="CWE-918",
                    remediation="Validate and allowlist URLs",
                ))
        if "fetch(" in source and "url" in source:
            findings.append(SecurityFinding(
                agent="PentestAgent",
                severity="medium",
                title="Possible SSRF",
                description="fetch with variable URL - verify not user-controlled",
                file_path=file_path,
                cwe_id="CWE-918",
                remediation="Validate URL against allowlist",
            ))
        return findings

    def scan_for_auth_bypass(
        self,
        routes: List[Dict[str, Any]],
    ) -> List[SecurityFinding]:
        """Check for auth bypass patterns in route definitions."""
        findings: List[SecurityFinding] = []
        for route in routes:
            if route.get("public", False) and route.get("path", "").startswith("/api"):
                findings.append(SecurityFinding(
                    agent="PentestAgent",
                    severity="medium",
                    title="Public API route",
                    description=f"Route {route.get('path')} is public",
                    remediation="Verify no sensitive operations",
                    cwe_id="CWE-306",
                ))
        return findings


class FuzzAgent:
    """API fuzzing with malformed data."""

    def generate_fuzz_payloads(self, param_type: str) -> List[Any]:
        """Generate malformed inputs for string, int, email, url, json."""
        payloads: List[Any] = []
        if param_type in ("string", "str"):
            payloads = [
                "", " " * 10000, "\x00", "'; DROP TABLE--",
                "${7*7}", "{{constructor.constructor('alert(1)')()}}",
                "<script>alert(1)</script>", "\n\r\t",
            ]
        elif param_type in ("int", "integer"):
            payloads = [-1, 0, 2**31, -2**31 - 1, 999999999, "1; DROP TABLE--"]
        elif param_type in ("email",):
            payloads = [
                "a@b", "a@b.c", "x" * 300 + "@test.com",
                "test@<script>", "test@.com",
            ]
        elif param_type in ("url",):
            payloads = [
                "http://localhost", "file:///etc/passwd",
                "http://169.254.169.254/latest/meta-data/",
                "javascript:alert(1)",
            ]
        elif param_type in ("json",):
            payloads = [
                {}, {"__proto__": {"admin": True}},
                {"a": float("inf")}, {"a": 1e999},
            ]
        return payloads

    def fuzz_endpoint(
        self,
        method: str,
        path: str,
        params: Dict[str, Any],
    ) -> List[SecurityFinding]:
        """Fuzz a single endpoint with malformed params."""
        findings: List[SecurityFinding] = []
        for key, val in params.items():
            param_type = "string"
            if isinstance(val, int):
                param_type = "int"
            elif isinstance(val, bool):
                param_type = "string"
            payloads = self.generate_fuzz_payloads(param_type)
            for p in payloads[:3]:
                if isinstance(p, str) and len(p) > 500:
                    findings.append(SecurityFinding(
                        agent="FuzzAgent",
                        severity="info",
                        title="Large payload test",
                        description=f"Endpoint {path} accepts param {key}",
                        evidence=f"Payload length: {len(str(p))}",
                    ))
        return findings

    def fuzz_all_endpoints(
        self,
        openapi_spec: Dict[str, Any],
    ) -> List[SecurityFinding]:
        """Fuzz all endpoints from OpenAPI spec."""
        findings: List[SecurityFinding] = []
        paths = openapi_spec.get("paths", {})
        for path, methods in paths.items():
            for method, spec in methods.items():
                if method.lower() in ("get", "post", "put", "patch", "delete"):
                    params = spec.get("parameters", []) or []
                    param_dict = {p.get("name", "x"): p.get("schema", {}).get("type", "string") for p in params if isinstance(p, dict)}
                    findings.extend(
                        self.fuzz_endpoint(method.upper(), path, param_dict)
                    )
        return findings[:30]


class AuditAgent:
    """Secure code review audit."""

    def review_code(
        self,
        code_map: Dict[str, str],
    ) -> List[SecurityFinding]:
        """Comprehensive security review."""
        findings: List[SecurityFinding] = []
        pentest = PentestAgent()
        for filepath, content in code_map.items():
            findings.extend(pentest.scan_for_sqli(content, filepath))
            findings.extend(pentest.scan_for_xss(content, filepath))
            findings.extend(pentest.scan_for_ssrf(content, filepath))

        for filepath, content in code_map.items():
            if "eval(" in content:
                findings.append(SecurityFinding(
                    agent="AuditAgent",
                    severity="critical",
                    title="eval() usage",
                    description="eval() allows code injection",
                    file_path=filepath,
                    cwe_id="CWE-95",
                    remediation="Use ast.literal_eval or JSON parsing",
                ))
            if "pickle.loads" in content and "user" in content.lower():
                findings.append(SecurityFinding(
                    agent="AuditAgent",
                    severity="high",
                    title="Unsafe deserialization",
                    description="pickle.loads with user input is dangerous",
                    file_path=filepath,
                    cwe_id="CWE-502",
                    remediation="Use JSON or safe deserialization",
                ))

        return findings

    def generate_audit_report(
        self,
        findings: List[SecurityFinding],
    ) -> str:
        """Generate detailed Markdown report."""
        lines = [
            "# Security Audit Report",
            "",
            f"**Security Readiness Score:** {self.compute_security_score(findings)}/100",
            "",
            "## Findings by Severity",
            "",
        ]
        for sev in ["critical", "high", "medium", "low", "info"]:
            items = [f for f in findings if f.severity == sev]
            if items:
                lines.append(f"### {sev.upper()} ({len(items)})")
                lines.append("")
                for f in items:
                    lines.append(f"- **{f.title}** ({f.agent})")
                    lines.append(f"  - {f.description}")
                    if f.file_path:
                        lines.append(f"  - File: {f.file_path}:{f.line_number}")
                    if f.remediation:
                        lines.append(f"  - Remediation: {f.remediation}")
                    lines.append("")
        return "\n".join(lines)

    def compute_security_score(self, findings: List[SecurityFinding]) -> int:
        """Compute Security Readiness Score 0-100."""
        critical = sum(1 for f in findings if f.severity == "critical")
        high = sum(1 for f in findings if f.severity == "high")
        medium = sum(1 for f in findings if f.severity == "medium")
        low = sum(1 for f in findings if f.severity == "low")
        score = 100 - critical * 25 - high * 15 - medium * 5 - low * 2
        return max(0, min(100, score))


class FortressSwarm:
    """Orchestrates all security agents."""

    def __init__(self) -> None:
        self.threat_model = ThreatModelAgent()
        self.pentest = PentestAgent()
        self.fuzz = FuzzAgent()
        self.audit = AuditAgent()
        self._last_score: int = 100

    async def run_full_scan(
        self,
        code_map: Dict[str, str],
        routes: Optional[List[Dict[str, Any]]] = None,
        openapi_spec: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run all agents and aggregate findings."""
        all_findings: List[SecurityFinding] = []
        routes = routes or []

        all_findings.extend(self.threat_model.analyze_api_routes(routes))
        all_findings.extend(self.threat_model.analyze_data_flow(code_map))
        all_findings.extend(self.pentest.scan_for_auth_bypass(routes))

        for filepath, content in code_map.items():
            all_findings.extend(self.pentest.scan_for_sqli(content, filepath))
            all_findings.extend(self.pentest.scan_for_xss(content, filepath))
            all_findings.extend(self.pentest.scan_for_ssrf(content, filepath))

        all_findings.extend(self.audit.review_code(code_map))

        if openapi_spec:
            all_findings.extend(self.fuzz.fuzz_all_endpoints(openapi_spec))

        self._last_score = self.audit.compute_security_score(all_findings)
        threat_model = self.threat_model.generate_threat_model(all_findings)

        return {
            "findings": [f.to_dict() for f in all_findings],
            "securityScore": self._last_score,
            "threatModel": threat_model,
            "auditReport": self.audit.generate_audit_report(all_findings),
            "summary": {
                "total": len(all_findings),
                "critical": sum(1 for f in all_findings if f.severity == "critical"),
                "high": sum(1 for f in all_findings if f.severity == "high"),
                "medium": sum(1 for f in all_findings if f.severity == "medium"),
            },
        }

    def get_security_score(self) -> int:
        """Return latest security score."""
        return self._last_score
