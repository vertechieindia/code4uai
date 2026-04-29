from __future__ import annotations
"""Enterprise Security & Tenant Isolation for code4u.ai.

This is MANDATORY for real enterprise customers.

Security Features:
- Tenant Isolation (hard boundary)
- Model Isolation (shared or dedicated)
- Data Flow Rules
- RBAC on Intents
- No-AI Zones
- Audit Logging
"""
from code4u.security_compliance.security.tenant import TenantContext, TenantManager
from code4u.security_compliance.security.isolation import IsolationPolicy, IsolationLevel
from code4u.security_compliance.security.rbac import RBACPolicy, Permission, Role
from code4u.security_compliance.security.no_ai_zones import NoAIZonePolicy, NoAIZone
from code4u.security_compliance.security.audit import AuditLogger, AuditEvent

__all__ = [
    "TenantContext",
    "TenantManager",
    "IsolationPolicy",
    "IsolationLevel",
    "RBACPolicy",
    "Permission",
    "Role",
    "NoAIZonePolicy",
    "NoAIZone",
    "AuditLogger",
    "AuditEvent",
]

