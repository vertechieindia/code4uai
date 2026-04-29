"""Security Sentinel Agent — secret detection, SAST, and credential scanning.

Provides:
  - ``SecretScanner``            — high-entropy + regex-based credential detection.
  - ``SASTScanner``              — static analysis for common vulnerability patterns.
  - ``SecurityViolationError``   — raised when code changes contain secrets/vulns.
  - ``scan_content``             — unified scan for proposed code changes.

Usage::

    scanner = SecretScanner()
    findings = scanner.scan(source, file_path="config.py")
    if findings:
        raise SecurityViolationError(findings)
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple


class SecurityViolationError(Exception):
    """Raised when a proposed code change contains security violations."""

    def __init__(self, findings: List[Dict[str, Any]], message: str = ""):
        self.findings = findings
        summary = message or f"Security scan blocked {len(findings)} violation(s)"
        super().__init__(summary)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": "SecurityViolation",
            "message": str(self),
            "findings": self.findings,
            "count": len(self.findings),
        }


# =====================================================================
# Secret Scanner — regex + Shannon entropy
# =====================================================================

_SECRET_PATTERNS: List[Dict[str, Any]] = [
    {
        "id": "aws-access-key",
        "name": "AWS Access Key ID",
        "regex": re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
        "severity": "critical",
    },
    {
        "id": "aws-secret-key",
        "name": "AWS Secret Access Key",
        "regex": re.compile(r"""(?:aws_secret_access_key|secret_key|AWS_SECRET)\s*[=:]\s*['"]?([A-Za-z0-9/+=]{40})['"]?"""),
        "severity": "critical",
    },
    {
        "id": "github-token",
        "name": "GitHub Token",
        "regex": re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}"),
        "severity": "critical",
    },
    {
        "id": "github-pat-fine",
        "name": "GitHub Fine-grained PAT",
        "regex": re.compile(r"github_pat_[A-Za-z0-9_]{22,255}"),
        "severity": "critical",
    },
    {
        "id": "stripe-key",
        "name": "Stripe API Key",
        "regex": re.compile(r"(?:sk|pk|rk)_(?:test|live)_[A-Za-z0-9]{20,100}"),
        "severity": "critical",
    },
    {
        "id": "ssh-private-key",
        "name": "SSH Private Key",
        "regex": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
        "severity": "critical",
    },
    {
        "id": "generic-api-key",
        "name": "Generic API Key Assignment",
        "regex": re.compile(r"""(?:api[_-]?key|apikey|api[_-]?secret|secret[_-]?key)\s*[=:]\s*['"]([A-Za-z0-9_\-]{20,})['"]""", re.IGNORECASE),
        "severity": "warning",
    },
    {
        "id": "slack-token",
        "name": "Slack Token",
        "regex": re.compile(r"xox[boaprs]-[A-Za-z0-9\-]{10,250}"),
        "severity": "critical",
    },
    {
        "id": "jwt-token",
        "name": "JSON Web Token",
        "regex": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        "severity": "warning",
    },
    {
        "id": "private-key-pem",
        "name": "PEM Private Key",
        "regex": re.compile(r"-----BEGIN (?:ENCRYPTED )?PRIVATE KEY-----"),
        "severity": "critical",
    },
    {
        "id": "google-api-key",
        "name": "Google API Key",
        "regex": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
        "severity": "critical",
    },
    {
        "id": "heroku-api-key",
        "name": "Heroku API Key",
        "regex": re.compile(r"""(?:heroku[_-]?api[_-]?key|HEROKU_API_KEY)\s*[=:]\s*['"]?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})['"]?""", re.IGNORECASE),
        "severity": "critical",
    },
    {
        "id": "password-assign",
        "name": "Hardcoded Password",
        "regex": re.compile(r"""(?:password|passwd|pwd)\s*[=:]\s*['"]([^'"]{8,})['"]""", re.IGNORECASE),
        "severity": "warning",
    },
    {
        "id": "connection-string",
        "name": "Database Connection String",
        "regex": re.compile(r"""(?:postgres|mysql|mongodb|redis)://\w+:[^@\s]+@""", re.IGNORECASE),
        "severity": "critical",
    },
]

_ALLOWLIST_PATTERNS = [
    re.compile(r"AKIA[A-Z0-9]{16}", re.IGNORECASE),  # example keys in docs
    re.compile(r"YOUR[_-]?API[_-]?KEY", re.IGNORECASE),
    re.compile(r"REPLACE[_-]?ME", re.IGNORECASE),
    re.compile(r"<[A-Z_]+>"),  # placeholder tokens
    re.compile(r"EXAMPLE", re.IGNORECASE),
    re.compile(r"xxx+", re.IGNORECASE),
]


def _shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not data:
        return 0.0
    freq: Dict[str, int] = {}
    for ch in data:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(data)
    return -sum((c / length) * math.log2(c / length) for c in freq.values())


def _is_allowlisted(match_text: str) -> bool:
    """Check if the matched text is a known placeholder / example."""
    for pat in _ALLOWLIST_PATTERNS:
        if pat.search(match_text):
            return True
    return False


class SecretScanner:
    """Detect secrets, credentials, and API keys in source code."""

    def __init__(self, entropy_threshold: float = 4.5, min_high_entropy_len: int = 20):
        self.entropy_threshold = entropy_threshold
        self.min_high_entropy_len = min_high_entropy_len

    def scan(self, source: str, file_path: str = "") -> List[Dict[str, Any]]:
        """Scan source code for secrets. Returns list of findings."""
        findings: List[Dict[str, Any]] = []
        lines = source.splitlines()

        for i, line in enumerate(lines):
            lineno = i + 1
            stripped = line.strip()

            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                if "example" in stripped.lower() or "placeholder" in stripped.lower():
                    continue

            for pat in _SECRET_PATTERNS:
                for m in pat["regex"].finditer(line):
                    matched = m.group(0)
                    if _is_allowlisted(matched):
                        continue
                    masked = matched[:6] + "..." + matched[-4:] if len(matched) > 12 else "***"
                    findings.append({
                        "type": "secret",
                        "patternId": pat["id"],
                        "name": pat["name"],
                        "severity": pat["severity"],
                        "filePath": file_path,
                        "line": lineno,
                        "match": masked,
                        "description": f"Potential {pat['name']} detected",
                    })

            self._check_high_entropy_strings(line, lineno, file_path, findings)

        return findings

    def _check_high_entropy_strings(
        self, line: str, lineno: int, file_path: str,
        findings: List[Dict[str, Any]],
    ) -> None:
        """Check for high-entropy strings that might be secrets."""
        for m in re.finditer(r"""['"]([A-Za-z0-9+/=_\-]{20,})['"]""", line):
            value = m.group(1)
            if len(value) < self.min_high_entropy_len:
                continue
            if _is_allowlisted(value):
                continue

            entropy = _shannon_entropy(value)
            if entropy >= self.entropy_threshold:
                masked = value[:4] + "..." + value[-4:]
                findings.append({
                    "type": "high-entropy",
                    "patternId": "high-entropy-string",
                    "name": "High-Entropy String",
                    "severity": "warning",
                    "filePath": file_path,
                    "line": lineno,
                    "match": masked,
                    "entropy": round(entropy, 2),
                    "description": f"High-entropy string (entropy={entropy:.1f}) may be a credential",
                })

    def scan_files(self, file_contents: Dict[str, str]) -> List[Dict[str, Any]]:
        """Scan multiple files for secrets."""
        all_findings: List[Dict[str, Any]] = []
        for path, content in file_contents.items():
            all_findings.extend(self.scan(content, path))
        return all_findings


# =====================================================================
# SAST Scanner — Static Application Security Testing
# =====================================================================

_SAST_RULES: List[Dict[str, Any]] = [
    {
        "id": "sqli-fstring",
        "name": "SQL Injection (f-string)",
        "regex": re.compile(r"""(?:execute|cursor\.execute|\.raw|\.query)\s*\(\s*f['"]""", re.IGNORECASE),
        "severity": "critical",
        "category": "SQL Injection",
        "description": "SQL query built with f-string — vulnerable to SQL injection.",
        "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
    },
    {
        "id": "sqli-format",
        "name": "SQL Injection (.format)",
        "regex": re.compile(r"""(?:execute|cursor\.execute)\s*\(\s*['"][^'"]*['"]\.format\s*\(""", re.IGNORECASE),
        "severity": "critical",
        "category": "SQL Injection",
        "description": "SQL query built with .format() — vulnerable to SQL injection.",
        "fix": "Use parameterized queries instead of string formatting.",
    },
    {
        "id": "sqli-concat",
        "name": "SQL Injection (concatenation)",
        "regex": re.compile(r"""(?:execute|cursor\.execute)\s*\(\s*['"](?:SELECT|INSERT|UPDATE|DELETE)\b[^'"]*['"]\s*\+""", re.IGNORECASE),
        "severity": "critical",
        "category": "SQL Injection",
        "description": "SQL query built with string concatenation — vulnerable to SQL injection.",
        "fix": "Use parameterized queries instead of string concatenation.",
    },
    {
        "id": "xss-innerhtml",
        "name": "XSS (innerHTML)",
        "regex": re.compile(r"""\.innerHTML\s*=\s*(?!['"]<)"""),
        "severity": "warning",
        "category": "Cross-Site Scripting",
        "description": "Setting innerHTML with dynamic content — potential XSS vulnerability.",
        "fix": "Use textContent instead, or sanitize HTML with DOMPurify.",
    },
    {
        "id": "xss-dangerously",
        "name": "XSS (dangerouslySetInnerHTML)",
        "regex": re.compile(r"dangerouslySetInnerHTML"),
        "severity": "warning",
        "category": "Cross-Site Scripting",
        "description": "Using dangerouslySetInnerHTML — ensure input is sanitized.",
        "fix": "Sanitize the HTML content with DOMPurify before rendering.",
    },
    {
        "id": "eval-usage",
        "name": "Unsafe eval()",
        "regex": re.compile(r"""\beval\s*\(\s*(?!['"])"""),
        "severity": "critical",
        "category": "Code Injection",
        "description": "Using eval() with dynamic input — allows arbitrary code execution.",
        "fix": "Use ast.literal_eval() for Python or JSON.parse() for JavaScript.",
    },
    {
        "id": "exec-usage",
        "name": "Unsafe exec()",
        "regex": re.compile(r"""\bexec\s*\(\s*(?!['"])"""),
        "severity": "critical",
        "category": "Code Injection",
        "description": "Using exec() with dynamic input — allows arbitrary code execution.",
        "fix": "Avoid exec() entirely; use safer alternatives.",
    },
    {
        "id": "pickle-load",
        "name": "Insecure Deserialization (pickle)",
        "regex": re.compile(r"""pickle\.(?:load|loads)\s*\("""),
        "severity": "critical",
        "category": "Insecure Deserialization",
        "description": "Using pickle.load with untrusted data allows arbitrary code execution.",
        "fix": "Use json.load() or a safe serialization format.",
    },
    {
        "id": "yaml-load",
        "name": "Insecure YAML Load",
        "regex": re.compile(r"""yaml\.load\s*\([^)]*(?!Loader)"""),
        "severity": "warning",
        "category": "Insecure Deserialization",
        "description": "Using yaml.load without SafeLoader allows code execution.",
        "fix": "Use yaml.safe_load() or yaml.load(data, Loader=yaml.SafeLoader).",
    },
    {
        "id": "hardcoded-ip",
        "name": "Hardcoded IP Address",
        "regex": re.compile(r"""\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"""),
        "severity": "info",
        "category": "Hardcoded Configuration",
        "description": "Hardcoded IP address found — should be externalized to configuration.",
        "fix": "Use environment variables or configuration files.",
    },
    {
        "id": "no-verify-ssl",
        "name": "SSL Verification Disabled",
        "regex": re.compile(r"""verify\s*=\s*False"""),
        "severity": "warning",
        "category": "Insecure Communication",
        "description": "SSL verification disabled — man-in-the-middle attacks possible.",
        "fix": "Enable SSL verification or use proper certificates.",
    },
    {
        "id": "command-injection",
        "name": "Command Injection",
        "regex": re.compile(r"""(?:os\.system|os\.popen|subprocess\.(?:call|run|Popen))\s*\(\s*(?:f['"]|.*\+\s*\w)"""),
        "severity": "critical",
        "category": "Command Injection",
        "description": "Shell command built with user input — command injection risk.",
        "fix": "Use subprocess with a list of arguments instead of shell=True.",
    },
    {
        "id": "path-traversal",
        "name": "Path Traversal",
        "regex": re.compile(r"""open\s*\(\s*(?:request\.|user_|input)"""),
        "severity": "warning",
        "category": "Path Traversal",
        "description": "File opened with user-controlled path — path traversal risk.",
        "fix": "Validate and sanitize file paths; use os.path.realpath() to resolve symlinks.",
    },
    {
        "id": "cors-wildcard",
        "name": "CORS Wildcard",
        "regex": re.compile(r"""(?:Access-Control-Allow-Origin|allow_origins)\s*[=:]\s*['"]\*['"]"""),
        "severity": "warning",
        "category": "CORS Misconfiguration",
        "description": "CORS allows all origins — sensitive endpoints may be exposed.",
        "fix": "Restrict allowed origins to trusted domains.",
    },
]

_SAST_IP_ALLOWLIST = frozenset({"0.0.0.0", "127.0.0.1", "255.255.255.255", "192.168.1.1"})


class SASTScanner:
    """Static Application Security Testing scanner."""

    def scan(self, source: str, file_path: str = "") -> List[Dict[str, Any]]:
        """Scan source for common vulnerability patterns."""
        findings: List[Dict[str, Any]] = []
        lines = source.splitlines()

        for i, line in enumerate(lines):
            lineno = i + 1

            for rule in _SAST_RULES:
                for m in rule["regex"].finditer(line):
                    if rule["id"] == "hardcoded-ip":
                        ip = m.group(0)
                        if ip in _SAST_IP_ALLOWLIST:
                            continue

                    findings.append({
                        "type": "vulnerability",
                        "ruleId": rule["id"],
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "category": rule["category"],
                        "filePath": file_path,
                        "line": lineno,
                        "description": rule["description"],
                        "fix": rule["fix"],
                        "match": line.strip()[:120],
                    })

        return findings

    def scan_files(self, file_contents: Dict[str, str]) -> List[Dict[str, Any]]:
        """Scan multiple files."""
        all_findings: List[Dict[str, Any]] = []
        for path, content in file_contents.items():
            all_findings.extend(self.scan(content, path))
        return all_findings


# =====================================================================
# Unified scan — combines secrets + SAST
# =====================================================================

def scan_content(
    source: str,
    file_path: str = "",
    check_secrets: bool = True,
    check_sast: bool = True,
) -> List[Dict[str, Any]]:
    """Run all security scanners on source code."""
    findings: List[Dict[str, Any]] = []

    if check_secrets:
        findings.extend(SecretScanner().scan(source, file_path))

    if check_sast:
        findings.extend(SASTScanner().scan(source, file_path))

    findings.sort(
        key=lambda f: {"critical": 0, "warning": 1, "info": 2}.get(f.get("severity", ""), 3)
    )
    return findings


def scan_proposed_changes(
    file_contents: Dict[str, str],
    block_on_secrets: bool = True,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Scan proposed code changes for security issues.

    Returns (findings, blocked) where blocked=True if critical secrets found.
    """
    all_findings: List[Dict[str, Any]] = []
    has_critical_secret = False

    for path, content in file_contents.items():
        findings = scan_content(content, path)
        all_findings.extend(findings)

        if block_on_secrets:
            for f in findings:
                if f.get("type") == "secret" and f.get("severity") == "critical":
                    has_critical_secret = True

    return all_findings, has_critical_secret
