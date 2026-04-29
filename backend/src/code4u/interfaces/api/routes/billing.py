from __future__ import annotations
"""Billing API routes for code4u.ai.

Exposes usage metering, pricing, and billing reports.
"""
from typing import Dict, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import structlog

from code4u.security_compliance.billing import UsageMetering, PricingEngine, PricingTier, BillingReporter

logger = structlog.get_logger("api.billing")
router = APIRouter()

# Service instances
metering = UsageMetering()
pricing = PricingEngine()
reporter = BillingReporter(metering, pricing)


class UsageReportRequest(BaseModel):
    tenant_id: str
    period_start: str
    period_end: str


class InvoiceRequest(BaseModel):
    tenant_id: str
    tier: Literal["developer", "team", "enterprise"]
    seats: int
    usage: Dict[str, int]


class LimitCheckRequest(BaseModel):
    tenant_id: str
    tier: Literal["developer", "team", "enterprise"]
    usage: Dict[str, int]


@router.get("/billing/usage/{tenant_id}")
async def get_usage(tenant_id: str):
    """Get current usage for a tenant."""
    metrics = metering.get_tenant_metrics(tenant_id)
    return {
        "tenant_id": tenant_id,
        "metrics": metrics.to_dict(),
    }


@router.post("/billing/usage/report")
async def get_usage_report(request: UsageReportRequest):
    """Get detailed usage report for a period."""
    report = reporter.generate_usage_report(
        tenant_id=request.tenant_id,
        period_start=request.period_start,
        period_end=request.period_end,
    )
    return report


@router.post("/billing/invoice")
async def calculate_invoice(request: InvoiceRequest):
    """Calculate invoice for a tenant."""
    tier = PricingTier(request.tier)
    
    invoice = pricing.calculate_invoice(
        tenant_id=request.tenant_id,
        tier=tier,
        seats=request.seats,
        usage=request.usage,
    )
    return invoice


@router.post("/billing/limits")
async def check_limits(request: LimitCheckRequest):
    """Check current usage against tier limits."""
    tier = PricingTier(request.tier)
    
    limits = pricing.check_limits(
        tenant_id=request.tenant_id,
        tier=tier,
        usage=request.usage,
    )
    return limits


@router.get("/billing/tiers")
async def get_tiers():
    """Get available pricing tiers and their features."""
    tiers = {}
    for tier in PricingTier:
        limits, pricing_info = pricing.get_tier_config(tier)
        tiers[tier.value] = {
            "limits": {
                "refactors_per_month": limits.refactors_per_month,
                "cross_repo_allowed": limits.cross_repo_allowed,
                "premium_fallback_allowed": limits.premium_fallback_allowed,
                "premium_tokens_per_month": limits.premium_tokens_per_month,
                "included_seats": limits.included_seats,
            },
            "features": {
                "contract_validation": limits.contract_validation,
                "audit_logs": limits.audit_logs,
                "custom_policies": limits.custom_policies,
                "dedicated_gpus": limits.dedicated_gpus,
                "tenant_isolation": limits.tenant_isolation,
            },
            "pricing": {
                "base_price_usd": pricing_info.base_price_usd,
                "per_seat_usd": pricing_info.per_seat_usd,
            },
        }
    return {"tiers": tiers}


@router.post("/billing/margin/{tenant_id}")
async def get_margin_report(
    tenant_id: str,
    tier: Literal["developer", "team", "enterprise"],
    period_start: str,
    period_end: str,
    seats: int = 1
):
    """Get margin analysis for a tenant (admin only)."""
    report = reporter.generate_margin_report(
        tenant_id=tenant_id,
        tier=PricingTier(tier),
        period_start=period_start,
        period_end=period_end,
        seats=seats,
    )
    return report


@router.get("/billing/cost-drivers/{tenant_id}")
async def get_cost_drivers(
    tenant_id: str,
    period_start: str,
    period_end: str
):
    """Get cost driver analysis for a tenant."""
    report = reporter.generate_cost_driver_report(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
    )
    return report
