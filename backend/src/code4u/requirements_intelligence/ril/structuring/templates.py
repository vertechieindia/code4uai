"""Requirement structuring templates."""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from ..models import RequirementType, RequirementPriority


@dataclass
class RequirementTemplate:
    """Template for requirement structuring."""
    
    # System mappings - keywords to system names
    SYSTEM_MAPPINGS: Dict[str, List[str]] = field(default_factory=lambda: {
        "auth": ["auth", "authentication", "login", "sso", "oauth", "saml", "okta", "auth0"],
        "frontend": ["frontend", "ui", "ux", "react", "vue", "web", "dashboard", "portal"],
        "backend": ["backend", "api", "server", "service", "microservice"],
        "database": ["database", "db", "postgresql", "mysql", "mongo", "redis", "storage"],
        "infrastructure": ["infrastructure", "kubernetes", "docker", "aws", "gcp", "azure", "terraform"],
        "security": ["security", "encryption", "audit", "compliance", "rbac", "acl"],
        "billing": ["billing", "payment", "stripe", "subscription", "pricing"],
        "notification": ["notification", "email", "sms", "push", "webhook", "alert"],
        "analytics": ["analytics", "metrics", "tracking", "dashboard", "reporting"],
        "search": ["search", "elasticsearch", "algolia", "indexing"],
        "file_storage": ["file", "upload", "s3", "storage", "cdn", "media"],
        "integration": ["integration", "api", "webhook", "connector", "sync"],
    })
    
    # Priority mappings
    PRIORITY_KEYWORDS: Dict[RequirementPriority, List[str]] = field(default_factory=lambda: {
        RequirementPriority.CRITICAL: [
            "critical", "urgent", "blocker", "asap", "immediately",
            "security issue", "production down", "outage",
        ],
        RequirementPriority.HIGH: [
            "high priority", "important", "soon", "next sprint",
            "before launch", "must have", "required",
        ],
        RequirementPriority.MEDIUM: [
            "medium", "normal", "standard", "should have",
            "this quarter", "next month",
        ],
        RequirementPriority.LOW: [
            "low priority", "nice to have", "someday", "backlog",
            "eventually", "if time permits",
        ],
    })
    
    # Type mappings
    TYPE_KEYWORDS: Dict[RequirementType, List[str]] = field(default_factory=lambda: {
        RequirementType.FUNCTIONAL: [
            "feature", "functionality", "add", "implement", "create",
            "user can", "ability to", "support", "enable",
        ],
        RequirementType.NON_FUNCTIONAL: [
            "performance", "scalability", "availability", "reliability",
            "maintainability", "usability", "accessibility",
        ],
        RequirementType.TECHNICAL: [
            "refactor", "migrate", "upgrade", "optimize", "technical debt",
            "architecture", "infrastructure",
        ],
        RequirementType.SECURITY: [
            "security", "authentication", "authorization", "encryption",
            "vulnerability", "audit", "penetration",
        ],
        RequirementType.COMPLIANCE: [
            "compliance", "soc2", "iso", "gdpr", "hipaa", "pci",
            "regulatory", "audit", "certification",
        ],
        RequirementType.PERFORMANCE: [
            "latency", "throughput", "response time", "load",
            "concurrent", "scaling", "capacity",
        ],
        RequirementType.INTEGRATION: [
            "integrate", "connect", "sync", "webhook", "api",
            "third-party", "external", "partner",
        ],
    })


STRUCTURING_PROMPT = """You are an engineering requirements analyst.

Convert the following conversation segment into a structured engineering requirement.

SEGMENT:
Speaker: {speaker} (Role: {role})
Text: "{text}"

CONTEXT (if available):
{context}

ENTITIES DETECTED:
- Systems: {systems}
- Technologies: {technologies}
- Constraints: {constraints}
- Deadlines: {deadlines}

Generate a structured requirement in JSON format:
{{
  "title": "Brief, actionable title (max 100 chars)",
  "description": "Clear description of what needs to be done",
  "type": "functional|non_functional|technical|security|compliance|performance|integration",
  "priority": "critical|high|medium|low",
  "systems": ["List of affected systems/services"],
  "services": ["Specific services to modify"],
  "constraints": ["Technical and compliance constraints"],
  "dependencies": ["Other requirements or systems this depends on"],
  "acceptance_criteria": [
    "Specific, testable acceptance criteria"
  ],
  "estimated_effort": "small|medium|large|xlarge",
  "deadline_indicator": "Extracted deadline text or null"
}}

Rules:
1. Title must be actionable and specific
2. Description should be 1-3 sentences
3. List ALL affected systems based on the requirement
4. Include specific constraints (SOC2, performance, etc.)
5. Acceptance criteria must be testable
6. Be conservative with priority (default to medium)

JSON only, no explanation:"""


BATCH_STRUCTURING_PROMPT = """You are an engineering requirements analyst.

Analyze these conversation segments and extract ALL distinct requirements.

SEGMENTS:
{segments}

For each distinct requirement mentioned, generate a structured requirement.
Merge related segments into single requirements.
Skip non-technical or context-only segments.

Respond with a JSON array:
[
  {{
    "title": "...",
    "description": "...",
    "type": "functional|...",
    "priority": "high|...",
    "systems": [...],
    "constraints": [...],
    "acceptance_criteria": [...],
    "source_segment_ids": ["segment IDs that contributed to this requirement"]
  }},
  ...
]

JSON array only, no explanation:"""

