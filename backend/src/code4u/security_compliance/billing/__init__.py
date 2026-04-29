from __future__ import annotations
"""Monetization & Usage-Based Cost Controls for code4u.ai.

This is where most AI startups collapse. code4u.ai won't.

Billing Philosophy:
- Bill for OUTCOMES, not tokens
- Internal cost metering for margin visibility
- Predictable pricing for customers
"""
from code4u.security_compliance.billing.metering import UsageMetering, UsageEvent
from code4u.security_compliance.billing.pricing import PricingEngine, PricingTier
from code4u.security_compliance.billing.reports import BillingReporter

__all__ = [
    "UsageMetering",
    "UsageEvent",
    "PricingEngine",
    "PricingTier",
    "BillingReporter",
]

