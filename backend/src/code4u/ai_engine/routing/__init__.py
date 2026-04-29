from __future__ import annotations
"""Self-Hosted ↔ Cloud Routing Logic for code4u.ai.

Goal: Use self-hosted LLMs by default, fall back to premium APIs 
only when strictly necessary, and never degrade UX silently.

Every fallback is:
- Logged
- Attributed to cost center
- Visible to admins
"""
from code4u.ai_engine.routing.engine import RoutingEngine, RoutingDecision
from code4u.ai_engine.routing.complexity import ComplexityScorer, ComplexityScore
from code4u.ai_engine.routing.cost_controls import CostController, CostGuardrails

__all__ = [
    "RoutingEngine",
    "RoutingDecision",
    "ComplexityScorer",
    "ComplexityScore",
    "CostController",
    "CostGuardrails",
]

