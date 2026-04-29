from __future__ import annotations
"""Evidence collection for compliance audits.

Generates audit-ready evidence packages.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List
import json
import structlog

logger = structlog.get_logger("compliance.evidence")


@dataclass
class EvidencePackage:
    """A package of evidence for audit."""
    package_id: str
    created_at: str
    period_start: str
    period_end: str
    framework: str
    
    # Evidence items
    documents: list[Dict[str, str]] = field(default_factory=list)
    logs: list[Dict[str, Any]] = field(default_factory=list)
    configurations: list[Dict[str, Any]] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "created_at": self.created_at,
            "period": {
                "start": self.period_start,
                "end": self.period_end,
            },
            "framework": self.framework,
            "document_count": len(self.documents),
            "log_count": len(self.logs),
            "configuration_count": len(self.configurations),
        }


class EvidenceCollector:
    """
    Collect evidence for compliance audits.
    
    Evidence types:
    - Documents (policies, procedures)
    - Logs (audit logs, access logs)
    - Configurations (security settings)
    - Screenshots (UI evidence)
    """
    
    def __init__(self):
        pass
    
    async def collect_soc2_evidence(
        self,
        period_start: str,
        period_end: str
    ) -> EvidencePackage:
        """Collect evidence for SOC 2 audit."""
        import uuid
        
        package = EvidencePackage(
            package_id=str(uuid.uuid4())[:12],
            created_at=datetime.utcnow().isoformat(),
            period_start=period_start,
            period_end=period_end,
            framework="SOC2",
        )
        
        # Collect documents
        package.documents = await self._collect_documents()
        
        # Collect logs
        package.logs = await self._collect_audit_logs(period_start, period_end)
        
        # Collect configurations
        package.configurations = await self._collect_configurations()
        
        logger.info(
            "evidence_collected",
            package_id=package.package_id,
            framework="SOC2",
            documents=len(package.documents),
            logs=len(package.logs),
        )
        
        return package
    
    async def collect_iso27001_evidence(
        self,
        period_start: str,
        period_end: str
    ) -> EvidencePackage:
        """Collect evidence for ISO 27001 audit."""
        import uuid
        
        package = EvidencePackage(
            package_id=str(uuid.uuid4())[:12],
            created_at=datetime.utcnow().isoformat(),
            period_start=period_start,
            period_end=period_end,
            framework="ISO27001",
        )
        
        # Collect documents
        package.documents = await self._collect_documents()
        
        # Collect logs
        package.logs = await self._collect_audit_logs(period_start, period_end)
        
        # Collect configurations
        package.configurations = await self._collect_configurations()
        
        # Add ISMS-specific evidence
        package.documents.extend(await self._collect_isms_documents())
        
        logger.info(
            "evidence_collected",
            package_id=package.package_id,
            framework="ISO27001",
            documents=len(package.documents),
            logs=len(package.logs),
        )
        
        return package
    
    async def _collect_documents(self) -> list[Dict[str, str]]:
        """Collect policy and procedure documents."""
        return [
            {
                "name": "AI Usage Policy",
                "path": "docs/compliance/AI_USAGE_POLICY.md",
                "type": "policy",
            },
            {
                "name": "SOC 2 Mapping",
                "path": "docs/compliance/SOC2_MAPPING.md",
                "type": "control_mapping",
            },
            {
                "name": "ISO 27001 Mapping",
                "path": "docs/compliance/ISO27001_MAPPING.md",
                "type": "control_mapping",
            },
            {
                "name": "Architecture Overview",
                "path": "docs/architecture/SELF_HOSTED_LLM.md",
                "type": "architecture",
            },
            {
                "name": "Enterprise Security Design",
                "path": "docs/architecture/ENTERPRISE_SECURITY.md",
                "type": "architecture",
            },
        ]
    
    async def _collect_isms_documents(self) -> list[Dict[str, str]]:
        """Collect ISMS-specific documents for ISO 27001."""
        return [
            {
                "name": "Information Security Policy",
                "path": "docs/compliance/ISMS/info_security_policy.md",
                "type": "isms",
            },
            {
                "name": "Risk Assessment",
                "path": "docs/compliance/ISMS/risk_assessment.md",
                "type": "isms",
            },
            {
                "name": "Statement of Applicability",
                "path": "docs/compliance/ISMS/soa.md",
                "type": "isms",
            },
        ]
    
    async def _collect_audit_logs(
        self,
        period_start: str,
        period_end: str
    ) -> list[Dict[str, Any]]:
        """Collect audit logs for the period."""
        # In production, this would query the audit log store
        return [
            {
                "type": "llm_interaction_summary",
                "period": {"start": period_start, "end": period_end},
                "total_interactions": 0,  # Would be populated
                "rejections": 0,
                "security_events": 0,
            },
            {
                "type": "change_application_summary",
                "period": {"start": period_start, "end": period_end},
                "total_changes": 0,
                "approved": 0,
                "rejected": 0,
                "rolled_back": 0,
            },
            {
                "type": "access_log_summary",
                "period": {"start": period_start, "end": period_end},
                "total_requests": 0,
                "denied_requests": 0,
            },
        ]
    
    async def _collect_configurations(self) -> list[Dict[str, Any]]:
        """Collect security configurations."""
        return [
            {
                "name": "RBAC Configuration",
                "source": "backend/src/code4u/security/rbac.py",
                "type": "access_control",
                "roles": ["admin", "developer", "auditor", "guest"],
            },
            {
                "name": "No-AI Zones",
                "source": "backend/src/code4u/security/no_ai_zones.py",
                "type": "data_protection",
                "zones": ["auth/", "payments/", "crypto/", "compliance/"],
            },
            {
                "name": "State Machine",
                "source": "backend/src/code4u/state_machine/states.py",
                "type": "processing_integrity",
                "states": [
                    "INIT", "IMPACT_ANALYZED", "PLAN_GENERATED",
                    "CONTRACT_VALIDATED", "CODE_GENERATED", "VERIFIED",
                    "READY_FOR_REVIEW", "APPLIED", "REJECTED",
                ],
            },
            {
                "name": "Cost Controls",
                "source": "backend/src/code4u/routing/cost_controls.py",
                "type": "operational",
                "guardrails": ["daily_token_cap", "premium_ceiling", "kill_switch"],
            },
        ]
    
    def export_package(self, package: EvidencePackage, format: str = "json") -> str:
        """Export evidence package to a file format."""
        if format == "json":
            return json.dumps({
                "package": package.to_dict(),
                "documents": package.documents,
                "logs": package.logs,
                "configurations": package.configurations,
            }, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

