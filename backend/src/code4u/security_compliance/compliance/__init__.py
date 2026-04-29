from __future__ import annotations
"""Compliance infrastructure for code4u.ai.

Compliance is architecture, not paperwork.
If you design correctly, audits become trivial.

This module provides:
- Compliance checking at runtime
- Audit evidence generation
- Control effectiveness monitoring
"""
from code4u.security_compliance.compliance.controls import ComplianceControls, ControlStatus
from code4u.security_compliance.compliance.evidence import EvidenceCollector
from code4u.security_compliance.compliance.monitor import ComplianceMonitor

__all__ = [
    "ComplianceControls",
    "ControlStatus",
    "EvidenceCollector",
    "ComplianceMonitor",
]

