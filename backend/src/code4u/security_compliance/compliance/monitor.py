from __future__ import annotations
"""Continuous compliance monitoring for code4u.ai.

Automated compliance checking and alerting.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List
import structlog

from code4u.security_compliance.compliance.controls import ComplianceControls, ControlResult, ControlStatus

logger = structlog.get_logger("compliance.monitor")


@dataclass
class ComplianceAlert:
    """A compliance alert."""
    alert_id: str
    severity: str  # critical, high, medium, low
    control_id: str
    control_name: str
    message: str
    created_at: str
    resolved: bool = False


class ComplianceMonitor:
    """
    Continuous compliance monitoring.
    
    Runs periodic checks and generates alerts.
    """
    
    def __init__(self):
        self.controls = ComplianceControls()
        self._alerts: list[ComplianceAlert] = []
    
    async def run_check(self) -> Dict[str, Any]:
        """
        Run a compliance check.
        
        Returns summary and any new alerts.
        """
        results = await self.controls.check_all()
        summary = self.controls.get_summary()
        
        # Generate alerts for failing controls
        new_alerts = []
        for result in results:
            if result.status == ControlStatus.FAILING:
                alert = self._create_alert(result, "critical")
                new_alerts.append(alert)
                self._alerts.append(alert)
            elif result.status == ControlStatus.WARNING:
                alert = self._create_alert(result, "medium")
                new_alerts.append(alert)
                self._alerts.append(alert)
        
        logger.info(
            "compliance_check_complete",
            passing=summary["passing"],
            failing=summary["failing"],
            new_alerts=len(new_alerts),
        )
        
        return {
            "summary": summary,
            "results": [r.__dict__ for r in results],
            "new_alerts": [a.__dict__ for a in new_alerts],
            "checked_at": datetime.utcnow().isoformat(),
        }
    
    async def get_dashboard(self) -> Dict[str, Any]:
        """
        Get compliance dashboard data.
        
        For display in admin UI.
        """
        results = await self.controls.check_all()
        summary = self.controls.get_summary()
        
        # Group by framework
        by_framework: dict[str, list[ControlResult]] = {}
        for result in results:
            if result.framework not in by_framework:
                by_framework[result.framework] = []
            by_framework[result.framework].append(result)
        
        framework_summaries = {}
        for framework, framework_results in by_framework.items():
            passing = sum(1 for r in framework_results if r.status == ControlStatus.PASSING)
            framework_summaries[framework] = {
                "total": len(framework_results),
                "passing": passing,
                "failing": len(framework_results) - passing,
                "compliance_rate": passing / len(framework_results) * 100,
            }
        
        return {
            "overall": summary,
            "by_framework": framework_summaries,
            "active_alerts": len([a for a in self._alerts if not a.resolved]),
            "recent_alerts": [a.__dict__ for a in self._alerts[-10:]],
            "last_check": datetime.utcnow().isoformat(),
        }
    
    async def get_audit_status(self) -> Dict[str, Any]:
        """
        Get audit readiness status.
        
        Indicates readiness for SOC 2 / ISO 27001 audits.
        """
        results = await self.controls.check_all()
        summary = self.controls.get_summary()
        
        # Check critical controls
        critical_controls = ["SOC2-SEC-001", "SOC2-SEC-002", "SOC2-PI-001"]
        critical_passing = all(
            any(r.control_id == c and r.status == ControlStatus.PASSING 
                for r in results)
            for c in critical_controls
        )
        
        readiness = "ready" if summary["failing"] == 0 else (
            "partial" if summary["compliance_rate"] >= 80 else "not_ready"
        )
        
        return {
            "readiness": readiness,
            "compliance_rate": summary["compliance_rate"],
            "critical_controls_passing": critical_passing,
            "blocking_issues": [
                r.control_name for r in results if r.status == ControlStatus.FAILING
            ],
            "recommendations": self._get_recommendations(results),
            "estimated_remediation_days": self._estimate_remediation(results),
        }
    
    def resolve_alert(self, alert_id: str) -> None:
        """Mark an alert as resolved."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                break
    
    def _create_alert(self, result: ControlResult, severity: str) -> ComplianceAlert:
        """Create an alert from a control result."""
        import uuid
        return ComplianceAlert(
            alert_id=str(uuid.uuid4())[:8],
            severity=severity,
            control_id=result.control_id,
            control_name=result.control_name,
            message=result.details,
            created_at=datetime.utcnow().isoformat(),
        )
    
    def _get_recommendations(self, results: list[ControlResult]) -> List[str]:
        """Generate recommendations based on results."""
        recommendations = []
        
        failing = [r for r in results if r.status == ControlStatus.FAILING]
        
        for result in failing:
            if "isolation" in result.control_name.lower():
                recommendations.append(
                    "Review tenant isolation configuration and ensure "
                    "IsolationEnforcer is properly initialized."
                )
            elif "audit" in result.control_name.lower():
                recommendations.append(
                    "Configure audit logging and verify log destinations."
                )
            elif "state" in result.control_name.lower():
                recommendations.append(
                    "Verify state machine transitions are properly defined."
                )
        
        if not recommendations:
            recommendations.append("All controls passing. Maintain current configuration.")
        
        return recommendations
    
    def _estimate_remediation(self, results: list[ControlResult]) -> int:
        """Estimate days to remediate failing controls."""
        failing_count = sum(1 for r in results if r.status == ControlStatus.FAILING)
        
        # Rough estimate: 1-2 days per failing control
        return failing_count * 2

