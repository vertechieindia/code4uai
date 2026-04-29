# security_compliance

Security, compliance, and billing.

## Purpose

- Tenant isolation, RBAC, no-AI zones, audit logging.
- Compliance controls and evidence.
- Billing and metering.

## Belongs here

- security (tenant, isolation, rbac, no_ai_zones, audit).
- compliance (controls, evidence, monitor).
- billing (metering, pricing, reports).

## Does not belong

- State machine (→ `platform_core`).
- API route handlers (→ `interfaces.api`; routes may call this layer).

## Depends on

- Referenced by compliance controls (state_machine, security).
