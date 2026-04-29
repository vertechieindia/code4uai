# code4u.ai — Compliance (SOC 2 & ISO 27001)

**Principle:** Compliance is architecture, not paperwork. Design controls into the system so audits are straightforward.

This document maps **SOC 2 Trust Service Criteria** and **ISO 27001:2022 Annex A** to code4u.ai implementation and evidence.

> **Updated Status (as of 2026-03-03, Day 21):**
> Since the January audit, significant security and compliance capabilities have been added:
> - **License Compliance Agent** — Detects project licenses, enforces compatibility matrix (18 licenses, 4 categories), blocks GPL→Proprietary code transfers
> - **Provenance & Attribution Tracker** — Records origin of every AI-generated change with source nugget, project hash, author hash, license verification
> - **Toxic Snippet Scanner** — 15 forbidden patterns across ethical (scraping, dark patterns), bias (gender/race logic), leaked code (Oracle/Windows), and malware (crypto mining, keyloggers, backdoors) categories
> - **Adversarial Agent** — 15 prompt injection/jailbreak test cases for AI hygiene verification
> - **Red Team Agent** — Scans for race conditions, unprotected endpoints, privilege escalation, business logic flaws
> - **Chaos Agent** — Fault injection (process kill, latency, memory pressure) for resilience testing
> - **SBOM Generator** — CycloneDX 1.5 compliant Software Bill of Materials from 6 manifest formats
> - **NVD Vulnerability Watch** — Real-time CVE monitoring via NVD API 2.0
> - **Recursive Gauntlet Orchestrator** — 5-stage validation pipeline with self-healing and quarantine
> - **Redis Cache Manager** — Caching layer for expensive operations with TTL-based namespaces
> - **Partitioned Vector Store** — Multi-tenant isolation for vector search indexes
>
> These are implemented and passing tests (140 new Day 19-21 tests + 215 comprehensive tests). However, they have NOT been audited by an external compliance body. Redis requires a running Redis server for the Redis backend; memory fallback is used by default.
>
> **Original Status (as of 2026-01-31 audit):**
> The compliance *architecture* exists (RBAC, audit, no-AI zones, tenant isolation, etc.) but has **not been integration-tested or audited**. Several security modules have import bugs (`List`, `Dict` used without importing from `typing`) that would cause runtime crashes on Python 3.9. mTLS is documented but not implemented. Signed diffs are documented but `transaction.py` does not include cryptographic signing. This document describes the *design intent*, not verified production behavior. All evidence paths reference real files, but the code at those paths may have issues.

---

## Part 1 — SOC 2 Trust Service Criteria

### 1. Security

**Objective:** Information and systems protected against unauthorized access.

| Control | Implementation | Evidence |
|---------|----------------|----------|
| mTLS between services | All internal service communication uses mutual TLS | `infrastructure/kubernetes/*.yaml` |
| RBAC on intents | Role-based access for all operations | `backend/src/code4u/security_compliance/security/rbac.py` |
| No shared tenant state | Hard tenant isolation | `backend/src/code4u/security_compliance/security/tenant.py`, `isolation.py` |
| Signed diffs | All generated diffs cryptographically signed | `backend/src/code4u/change_execution/diff_engine/transaction.py` |
| Immutable audit logs | All actions logged immutably | `backend/src/code4u/security_compliance/security/audit.py` |
| License compliance gate | Blocks copyleft→proprietary code transfers | `backend/src/code4u/agents/legal_agent.py` |
| Toxic snippet scanner | 15 forbidden patterns (bias, malware, leaked code) | `backend/src/code4u/security_compliance/toxic_scanner.py` |
| Provenance tracking | Attribution chain for all AI-generated changes | `backend/src/code4u/knowledge/provenance_tracker.py` |
| Adversarial hygiene | Prompt injection and jailbreak resistance testing | `backend/src/code4u/security_compliance/security/adversarial_agent.py` |
| Red team scanning | Logic exploitation, race condition, privilege escalation detection | `backend/src/code4u/agents/red_team_agent.py` |
| Chaos engineering | Fault injection resilience testing for AI workers | `backend/src/code4u/agents/chaos_agent.py` |
| SBOM generation | CycloneDX 1.5 Software Bill of Materials | `backend/src/code4u/security_compliance/sbom_generator.py` |
| NVD vulnerability watch | Real-time CVE monitoring via NVD API 2.0 | `backend/src/code4u/security_compliance/security/vulnerability_scanner.py` |

### 2. Availability

| Control | Implementation | Evidence |
|---------|----------------|----------|
| Stateless services | All API services stateless | `backend/src/code4u/interfaces/api/` |
| Graceful degradation | Premium fallback routing | `backend/src/code4u/ai_engine/routing/engine.py` |
| Kill-switches | Emergency disable for cloud models | `backend/src/code4u/ai_engine/routing/cost_controls.py` |
| Health checks | K8s readiness/liveness probes | `infrastructure/kubernetes/*-deployment.yaml` |

### 3. Processing Integrity

**Objective:** Processing complete, valid, accurate, timely, authorized.

| Control | Implementation | Evidence |
|---------|----------------|----------|
| Deterministic state machine | Strict state transitions, no skipping | `backend/src/code4u/platform_core/state_machine/` |
| Validation gates | Each phase validates before proceeding | `backend/src/code4u/platform_core/agents/verifier.py` |
| No silent writes | All changes require human approval | `backend/src/code4u/platform_core/protocol/handler.py` |
| Human approval checkpoints | Diff preview mandatory | IDE protocol `preview_only=True` |
| Contract validation | Schema and API contract enforcement | `backend/src/code4u/ai_engine/compiler/prompt_compiler.py` |

**Enforced state flow:** INIT → IMPACT_ANALYZED → PLAN_GENERATED → CONTRACT_VALIDATED → CODE_GENERATED → VERIFIED → READY_FOR_REVIEW → APPLIED | REJECTED. No skipping.

### 4. Confidentiality

| Control | Implementation | Evidence |
|---------|----------------|----------|
| Tenant-isolated storage | Separate KG, embeddings per tenant | `backend/src/code4u/security_compliance/security/tenant.py` |
| No training on customer data | Explicit opt-in only | Tenant configuration |
| Encryption at rest | AES-256 for stored data | Cloud provider config |
| Encryption in transit | TLS 1.3 | Infrastructure config |
| Redacted logs | Sensitive data scrubbed | `backend/src/code4u/security_compliance/security/audit.py` |

### 5. Privacy (Optional)

Data minimization, explicit opt-in for training, configurable retention, right to deletion via Admin API.

### code4u.ai-Specific: No-AI Zones

Explicit exclusions where AI modifications are forbidden:

| Zone / Pattern | Reason |
|----------------|--------|
| `^auth/`, `^login/` | Authentication — security critical |
| `^payments/` | Payment processing — PCI |
| `^crypto/` | Cryptography — security critical |
| `^compliance/` | Regulatory calculations — audit |
| `.env`, `.pem` | Secrets and keys |

**Implementation:** `backend/src/code4u/security_compliance/security/no_ai_zones.py`

---

## Part 2 — ISO 27001:2022 Annex A Mapping

### Summary

| ISO Control | code4u.ai Implementation |
|-------------|---------------------------|
| A.5 Organizational policies | AI usage policies + No-AI zones |
| A.6 Organization of IS | Ownership graph + team boundaries |
| A.7 Human resource security | User onboarding/offboarding |
| A.8 Asset management | Repository & service inventory (Knowledge Graph) |
| A.9 Access control | RBAC + SSO |
| A.10 Cryptography | TLS + encrypted storage + signed diffs |
| A.11 Physical security | Cloud provider (SaaS) |
| A.12 Operations security | State machine + logging |
| A.13 Communications security | mTLS + API contracts |
| A.14 System acquisition/development | Deterministic pipelines |
| A.15 Supplier relationships | Premium model governance, fallback logging |
| A.16 Incident management | Audit trails + alerts |
| A.17 Business continuity | Fallback routing + kill switches |
| A.18 Compliance | This document + continuous monitoring |

### Selected Detailed Mappings

**A.5.1 / A.8.2** — AI Usage Policy, No-AI Zones, information classification: `backend/src/code4u/security_compliance/security/no_ai_zones.py`, `tenant.py`.

**A.6.1** — Internal organization: Ownership graph, team boundaries, cross-team approval: `frontends/packages/knowledge-graph/`, `backend/src/code4u/security_compliance/security/rbac.py`.

**A.8.1** — Asset responsibility: Knowledge Graph inventories repositories, services, schemas, endpoints, packages, modules: `frontends/packages/knowledge-graph/`.

**A.9** — Access control: RBAC (e.g. admin, developer, auditor, guest), least privilege, SSO, intent-based and resource-level permissions: `backend/src/code4u/security_compliance/security/rbac.py`.

**A.10.1** — Cryptographic controls: TLS 1.3, mTLS, AES-256 at rest, signed diffs.

**A.12** — Operations: State machine for consistent operations; audit logging and monitoring: `backend/src/code4u/platform_core/state_machine/`, `backend/src/code4u/security_compliance/security/audit.py`.

**A.14.2** — Security in development: Deterministic pipelines, validation gates, no silent changes; evaluation harness, golden dataset: `backend/src/code4u/ai_engine/evaluation/`.

**A.15.1** — Supplier (e.g. premium LLM) governance: Fallback routing, logging, cost controls: `backend/src/code4u/ai_engine/routing/engine.py`, `cost_controls.py`.

**A.16.1** — Incident management: Audit trails, state violation detection, alerts, procedures.

**A.17.1** — Business continuity: Self-hosted primary, premium fallback, kill switches, stateless recovery: `backend/src/code4u/ai_engine/routing/`.

### Statement of Applicability

- **Implemented:** Via architecture, code, operations, and documentation as above.  
- **Not applicable:** A.11 Physical security (SaaS; cloud provider responsibility).

---

## Audit Readiness

### Pre-Audit

- [ ] Collect evidence artifacts (configs, logs, access tests)  
- [ ] Review and update this documentation  
- [ ] Verify audit logs and incident response  

### During Audit

- [ ] Architecture walkthrough and demo environment  
- [ ] Key personnel and evidence access  

### Post-Audit

- [ ] Address findings and track remediation  
- [ ] Confirm continuous monitoring  

### Continuous Compliance

- Automated compliance checks in CI/CD  
- Regular audit log and security metric reviews  
- Quarterly ISMS and annual internal audit cycle  

---

## Contact

For SOC 2 and ISO 27001 inquiries: **compliance@code4u.ai**
