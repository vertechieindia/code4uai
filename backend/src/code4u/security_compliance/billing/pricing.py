from __future__ import annotations
"""Pricing engine for code4u.ai.

What You Bill For (NOT Tokens):
- Refactors executed (high value)
- APIs added/changed (business impact)
- Cross-repo changes (premium)
- Premium model fallback (cost recovery)
- Seats (predictability)

Pricing Model:
- Developer Plan: Self-hosted only, limited refactors
- Team Plan: Self-hosted + limited premium, contract validation
- Enterprise: Dedicated GPUs, tenant-isolated models, custom policies
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict
import structlog

logger = structlog.get_logger("billing.pricing")


class PricingTier(str, Enum):
    """Pricing tiers for code4u.ai."""
    DEVELOPER = "developer"
    TEAM = "team"
    ENTERPRISE = "enterprise"


@dataclass
class TierLimits:
    """Limits for a pricing tier."""
    # Refactors
    refactors_per_month: int = 100
    cross_repo_allowed: bool = False
    
    # Premium
    premium_fallback_allowed: bool = False
    premium_tokens_per_month: int = 0
    
    # Features
    contract_validation: bool = False
    audit_logs: bool = False
    custom_policies: bool = False
    dedicated_gpus: bool = False
    tenant_isolation: bool = False
    
    # Seats
    included_seats: int = 1
    max_seats: int = 1


@dataclass
class TierPricing:
    """Pricing for a tier."""
    base_price_usd: float = 0.0
    per_seat_usd: float = 0.0
    overage_refactor_usd: float = 0.0
    overage_api_usd: float = 0.0
    premium_token_per_1k_usd: float = 0.0


# Tier configurations
TIER_CONFIGS: dict[PricingTier, tuple[TierLimits, TierPricing]] = {
    PricingTier.DEVELOPER: (
        TierLimits(
            refactors_per_month=50,
            cross_repo_allowed=False,
            premium_fallback_allowed=False,
            contract_validation=False,
            audit_logs=False,
            included_seats=1,
            max_seats=1,
        ),
        TierPricing(
            base_price_usd=0.0,  # Free
            per_seat_usd=0.0,
        )
    ),
    PricingTier.TEAM: (
        TierLimits(
            refactors_per_month=500,
            cross_repo_allowed=True,
            premium_fallback_allowed=True,
            premium_tokens_per_month=50000,
            contract_validation=True,
            audit_logs=True,
            included_seats=5,
            max_seats=50,
        ),
        TierPricing(
            base_price_usd=499.0,
            per_seat_usd=49.0,
            overage_refactor_usd=0.50,
            overage_api_usd=1.0,
            premium_token_per_1k_usd=0.02,
        )
    ),
    PricingTier.ENTERPRISE: (
        TierLimits(
            refactors_per_month=10000,  # Effectively unlimited
            cross_repo_allowed=True,
            premium_fallback_allowed=True,
            premium_tokens_per_month=500000,
            contract_validation=True,
            audit_logs=True,
            custom_policies=True,
            dedicated_gpus=True,
            tenant_isolation=True,
            included_seats=20,
            max_seats=10000,
        ),
        TierPricing(
            base_price_usd=4999.0,
            per_seat_usd=99.0,
            overage_refactor_usd=0.25,  # Volume discount
            overage_api_usd=0.50,
            premium_token_per_1k_usd=0.015,
        )
    ),
}


class PricingEngine:
    """
    Calculate billing based on usage and tier.
    
    COGS stay predictable because:
    - Self-hosted for most requests
    - Premium caps per tier
    - Volume discounts for enterprise
    """
    
    def __init__(self):
        pass
    
    def get_tier_config(self, tier: PricingTier) -> tuple[TierLimits, TierPricing]:
        """Get configuration for a tier."""
        return TIER_CONFIGS[tier]
    
    def calculate_invoice(
        self,
        tenant_id: str,
        tier: PricingTier,
        seats: int,
        usage: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Calculate invoice for a billing period.
        
        Usage dict should contain:
        - refactors_executed
        - apis_added
        - apis_changed
        - cross_repo_changes
        - premium_tokens
        """
        limits, pricing = self.get_tier_config(tier)
        
        # Base charges
        base_charge = pricing.base_price_usd
        
        # Seat charges
        extra_seats = max(0, seats - limits.included_seats)
        seat_charge = extra_seats * pricing.per_seat_usd
        
        # Overage charges
        total_refactors = usage.get("refactors_executed", 0) + usage.get("cross_repo_changes", 0)
        overage_refactors = max(0, total_refactors - limits.refactors_per_month)
        refactor_overage = overage_refactors * pricing.overage_refactor_usd
        
        total_apis = usage.get("apis_added", 0) + usage.get("apis_changed", 0)
        api_overage = total_apis * pricing.overage_api_usd
        
        # Premium token charges
        premium_tokens = usage.get("premium_tokens", 0)
        overage_premium = max(0, premium_tokens - limits.premium_tokens_per_month)
        premium_overage = (overage_premium / 1000) * pricing.premium_token_per_1k_usd
        
        # Total
        total = base_charge + seat_charge + refactor_overage + api_overage + premium_overage
        
        invoice = {
            "tenant_id": tenant_id,
            "tier": tier.value,
            "line_items": [
                {
                    "description": f"Base subscription ({tier.value})",
                    "amount_usd": base_charge,
                },
            ],
            "subtotal_usd": total,
            "total_usd": total,
        }
        
        if seat_charge > 0:
            invoice["line_items"].append({
                "description": f"Additional seats ({extra_seats} × ${pricing.per_seat_usd})",
                "amount_usd": seat_charge,
            })
        
        if refactor_overage > 0:
            invoice["line_items"].append({
                "description": f"Refactor overage ({overage_refactors} × ${pricing.overage_refactor_usd})",
                "amount_usd": refactor_overage,
            })
        
        if api_overage > 0:
            invoice["line_items"].append({
                "description": f"API changes ({total_apis} × ${pricing.overage_api_usd})",
                "amount_usd": api_overage,
            })
        
        if premium_overage > 0:
            invoice["line_items"].append({
                "description": f"Premium token overage ({overage_premium:,} tokens)",
                "amount_usd": premium_overage,
            })
        
        logger.info(
            "invoice_calculated",
            tenant_id=tenant_id,
            tier=tier.value,
            total_usd=total
        )
        
        return invoice
    
    def check_limits(
        self,
        tenant_id: str,
        tier: PricingTier,
        usage: Dict[str, int]
    ) -> Dict[str, Any]:
        """Check current usage against tier limits."""
        limits, _ = self.get_tier_config(tier)
        
        total_refactors = usage.get("refactors_executed", 0) + usage.get("cross_repo_changes", 0)
        premium_tokens = usage.get("premium_tokens", 0)
        
        return {
            "tenant_id": tenant_id,
            "tier": tier.value,
            "refactors": {
                "used": total_refactors,
                "limit": limits.refactors_per_month,
                "remaining": max(0, limits.refactors_per_month - total_refactors),
                "at_limit": total_refactors >= limits.refactors_per_month,
            },
            "premium_tokens": {
                "used": premium_tokens,
                "limit": limits.premium_tokens_per_month,
                "remaining": max(0, limits.premium_tokens_per_month - premium_tokens),
                "at_limit": premium_tokens >= limits.premium_tokens_per_month,
            },
            "features": {
                "cross_repo": limits.cross_repo_allowed,
                "premium_fallback": limits.premium_fallback_allowed,
                "contract_validation": limits.contract_validation,
                "audit_logs": limits.audit_logs,
            },
        }

