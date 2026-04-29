from __future__ import annotations
"""Billing reports for code4u.ai.

Provides visibility into:
- Customer usage and billing
- Internal COGS and margin
- Fallback rates and cost drivers
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List
import structlog

from code4u.security_compliance.billing.metering import UsageMetering, TenantMetrics
from code4u.security_compliance.billing.pricing import PricingEngine, PricingTier

logger = structlog.get_logger("billing.reports")


class BillingReporter:
    """
    Generate billing and cost reports.
    
    Reports include:
    - Customer invoices
    - Usage summaries
    - Margin analysis
    - Cost driver analysis
    """
    
    def __init__(
        self,
        metering: UsageMetering | None = None,
        pricing: PricingEngine | None = None
    ):
        self.metering = metering or UsageMetering()
        self.pricing = pricing or PricingEngine()
    
    def generate_usage_report(
        self,
        tenant_id: str,
        period_start: str,
        period_end: str
    ) -> Dict[str, Any]:
        """
        Generate a usage report for a tenant.
        
        Shows what they used and what it would cost.
        """
        metrics = self.metering.get_tenant_metrics(
            tenant_id, period_start, period_end
        )
        
        return {
            "report_type": "usage",
            "tenant_id": tenant_id,
            "period": {
                "start": period_start,
                "end": period_end,
            },
            "outcomes": {
                "refactors_executed": metrics.refactors_executed,
                "apis_added": metrics.apis_added,
                "apis_changed": metrics.apis_changed,
                "cross_repo_changes": metrics.cross_repo_changes,
                "explanations": metrics.explanations,
            },
            "resource_usage": {
                "total_tokens": metrics.total_tokens,
                "self_hosted_tokens": metrics.self_hosted_tokens,
                "premium_tokens": metrics.premium_tokens,
                "total_gpu_ms": metrics.total_gpu_ms,
            },
            "premium_fallbacks": metrics.premium_fallbacks,
            "generated_at": datetime.utcnow().isoformat(),
        }
    
    def generate_margin_report(
        self,
        tenant_id: str,
        tier: PricingTier,
        period_start: str,
        period_end: str,
        seats: int = 1
    ) -> Dict[str, Any]:
        """
        Generate margin analysis for a tenant.
        
        Shows:
        - Revenue (what we charge)
        - COGS (what it costs us)
        - Margin (profit)
        """
        metrics = self.metering.get_tenant_metrics(
            tenant_id, period_start, period_end
        )
        
        # Calculate revenue
        usage = {
            "refactors_executed": metrics.refactors_executed,
            "apis_added": metrics.apis_added,
            "apis_changed": metrics.apis_changed,
            "cross_repo_changes": metrics.cross_repo_changes,
            "premium_tokens": metrics.premium_tokens,
        }
        
        invoice = self.pricing.calculate_invoice(
            tenant_id, tier, seats, usage
        )
        
        revenue = invoice["total_usd"]
        cogs = metrics.estimated_cogs_usd
        margin = revenue - cogs
        margin_percent = (margin / revenue * 100) if revenue > 0 else 0
        
        return {
            "report_type": "margin",
            "tenant_id": tenant_id,
            "tier": tier.value,
            "period": {
                "start": period_start,
                "end": period_end,
            },
            "financials": {
                "revenue_usd": revenue,
                "cogs_usd": cogs,
                "margin_usd": margin,
                "margin_percent": round(margin_percent, 2),
            },
            "cost_breakdown": {
                "gpu_cost_usd": cogs * 0.9,  # Estimate
                "premium_model_cost_usd": cogs * 0.1,
            },
            "insights": self._generate_margin_insights(
                metrics, revenue, cogs, margin_percent
            ),
            "generated_at": datetime.utcnow().isoformat(),
        }
    
    def generate_cost_driver_report(
        self,
        tenant_id: str,
        period_start: str,
        period_end: str
    ) -> Dict[str, Any]:
        """
        Analyze what's driving costs for a tenant.
        
        Helps identify:
        - High fallback rates (why?)
        - Heavy GPU users
        - Optimization opportunities
        """
        metrics = self.metering.get_tenant_metrics(
            tenant_id, period_start, period_end
        )
        
        total_requests = (
            metrics.refactors_executed +
            metrics.apis_added +
            metrics.apis_changed +
            metrics.cross_repo_changes +
            metrics.explanations
        )
        
        fallback_rate = (
            metrics.premium_fallbacks / total_requests * 100
            if total_requests > 0 else 0
        )
        
        return {
            "report_type": "cost_drivers",
            "tenant_id": tenant_id,
            "period": {
                "start": period_start,
                "end": period_end,
            },
            "drivers": {
                "fallback_rate_percent": round(fallback_rate, 2),
                "cross_repo_ratio": (
                    metrics.cross_repo_changes / metrics.refactors_executed
                    if metrics.refactors_executed > 0 else 0
                ),
                "avg_tokens_per_request": (
                    metrics.total_tokens / total_requests
                    if total_requests > 0 else 0
                ),
                "avg_gpu_ms_per_request": (
                    metrics.total_gpu_ms / total_requests
                    if total_requests > 0 else 0
                ),
            },
            "recommendations": self._generate_cost_recommendations(
                metrics, fallback_rate
            ),
            "generated_at": datetime.utcnow().isoformat(),
        }
    
    def generate_admin_dashboard(self) -> Dict[str, Any]:
        """
        Generate admin dashboard data.
        
        Shows cross-tenant metrics for operators.
        """
        # This would aggregate across all tenants
        return {
            "report_type": "admin_dashboard",
            "summary": {
                "total_tenants": 0,
                "total_requests_today": 0,
                "total_revenue_mtd": 0,
                "total_cogs_mtd": 0,
                "avg_margin_percent": 0,
            },
            "alerts": [
                # High fallback rates
                # Cost spikes
                # Limit approaching
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }
    
    def _generate_margin_insights(
        self,
        metrics: TenantMetrics,
        revenue: float,
        cogs: float,
        margin_percent: float
    ) -> List[str]:
        """Generate insights about margin."""
        insights = []
        
        if margin_percent < 30:
            insights.append("Margin below 30% target. Review cost drivers.")
        
        if metrics.premium_fallbacks > metrics.refactors_executed * 0.2:
            insights.append("High premium fallback rate. Consider model improvements.")
        
        if margin_percent > 70:
            insights.append("Strong margins. Consider upsell opportunities.")
        
        if not insights:
            insights.append("Metrics within normal ranges.")
        
        return insights
    
    def _generate_cost_recommendations(
        self,
        metrics: TenantMetrics,
        fallback_rate: float
    ) -> List[str]:
        """Generate cost reduction recommendations."""
        recommendations = []
        
        if fallback_rate > 20:
            recommendations.append(
                "High fallback rate indicates self-hosted model struggles. "
                "Review common failure patterns and consider fine-tuning."
            )
        
        if metrics.premium_tokens > 100000:
            recommendations.append(
                "High premium token usage. Consider upgrading to Enterprise "
                "for better volume pricing."
            )
        
        if metrics.cross_repo_changes > metrics.refactors_executed * 0.5:
            recommendations.append(
                "Many cross-repo changes. Ensure proper monorepo structure "
                "to reduce complexity."
            )
        
        if not recommendations:
            recommendations.append("Cost profile is healthy. No action needed.")
        
        return recommendations

