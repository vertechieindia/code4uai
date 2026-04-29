# code4u.ai — Business Requirements Document (BRD)

**Version:** 1.2  
**Last updated:** 2026-03-03 (Day 21 — Sovereign Launch)  
**Status:** Living document

> **Status Update (2026-03-03, Day 21 — Sovereign Launch):** The platform now includes 22 specialist agents, 42 API routes, 1,360+ tests, 18 frontend pages with real JWT authentication, a 16-step onboarding tour, recursive quality gauntlet (Titan Phase), collective intelligence system (Wisdom Nuggets), license compliance enforcement (18 licenses, 4-category compatibility matrix), toxic snippet scanning (15 forbidden patterns), provenance tracking with attribution.json, Redis caching layer, partitioned multi-tenant vector store, chaos/adversarial/red-team testing, Organization Security Heatmap, Guardian Mission Control dashboard, and a Launch Command Center with impact summary. Frontend workspace runs on port 3000 with real auth (admin@code4u.ai / admin123). LLM integration requires API keys. Some pages show simulated data. Integrations beyond Jira/Slack remain stubs. Docker Compose has broken paths. No production deployment yet.

---

## 1. Executive Summary

code4u.ai is an **AI-native engineering platform** for enterprise-scale software development. It is **not** a chat-based coding assistant. It is a **Code Intelligence Platform**, a **Deterministic Refactoring Engine**, and an **Enterprise Execution System** that:

- Understands codebases via a **Knowledge Graph** (symbols, dependencies, ownership).
- Executes refactors and renames **deterministically** through a locked state machine (plan → generate → validate → preview → apply).
- Applies changes **transactionally** with backup and rollback; no silent or partial writes.
- Supports **enterprise trust**: tenant isolation, RBAC, No-AI zones, audit, and compliance (SOC 2 / ISO 27001 mapping).

The platform targets engineering organizations with large, multi-repo or multi-service codebases (e.g. 500+ micro-frontends, 500+ microservices) who need AI-assisted refactoring that is **safe, auditable, and ownership-aware**.

---

## 2. Business Objectives

| Objective | Description | Success Measure |
|-----------|-------------|-----------------|
| **Safe refactoring at scale** | Enable rename/refactor across many files and repos with full context and no silent failures | Refactors complete correctly; rollback works on failure; zero unrecoverable partial applies |
| **Enterprise adoption** | Meet security, compliance, and governance requirements of regulated and large enterprises | SOC 2 / ISO 27001 alignment; tenant isolation; audit trail; No-AI zones enforced |
| **Predictable economics** | Align pricing with outcomes (refactors, API changes, seats) and support self-hosted inference | Outcome-based billing; self-hosted option; cost controls and kill switches |
| **Developer trust** | No silent changes; every edit is previewed, validated, and reversible | Diff preview mandatory; AST/contract validation; one-click rollback |
| **Platform differentiation** | Establish structural moats vs. chat-first tools (e.g. Cursor): graph-first context, deterministic execution, ownership-aware edits | Clear technical moat narrative; multi-year competitor catch-up timeline |

---

## 3. Problem Statement

### 3.1 Market Problem

- **Enterprise engineering teams** need AI assistance for refactoring and code evolution across large, complex codebases.
- **Existing AI coding tools** (e.g. Cursor) are:
  - **Context-poor:** File/embedding-centric; no first-class model of symbols, dependencies, and ownership.
  - **Execution-weak:** Prompt-driven; no deterministic plan, no strict validation, no transactional apply/rollback.
  - **Enterprise-light:** Limited tenant isolation, RBAC, No-AI zones, and audit; unpredictable cloud costs.

### 3.2 User Pain Points

- **Developers:** Fear of AI making wrong or unrecoverable changes; lack of visibility into blast radius and ownership.
- **Tech leads:** No enforcement of API contracts or code ownership; no audit trail for compliance.
- **Security / compliance:** No way to block AI from touching auth, payment, or compliance logic; no immutable audit logs.
- **Finance / ops:** Unpredictable token-based costs; need for self-hosted or air-gapped deployment.

---

## 4. Scope

### 4.1 In scope (MVP and roadmap)

- **Refactor pipeline:** Intent (e.g. “Rename X to Y”) → context compilation (symbol, dependencies, ownership) → execution plan → LLM-generated code → validation → diff preview → apply (with backup/rollback).
- **Code Intelligence:** Symbol resolution (Python, TypeScript/JavaScript); file-level dependency traversal; CODEOWNERS-based ownership; blast-radius context.
- **Plan execution:** Locked state machine (GENERATE_CODE → VALIDATE_CODE → PREVIEW_DIFF → APPLY_DIFF); no step skipping.
- **Change application:** Backup before write; full rollback on any write failure; no partial state on disk.
- **Access channels:** REST API (refactor, rename); CLI; Web workspace (UI); VS Code extension; JetBrains plugin (structure).
- **Knowledge Graph:** Models, indexer, query, traversal; tenant-scoped graph API.
- **Security & compliance:** Tenant isolation; RBAC model; No-AI zones (definition and enforcement); audit logging (structure); SOC 2 / ISO 27001 control mapping.
- **LLM orchestration:** vLLM client; executor; routing (complexity, fallback); self-hosted + optional premium fallback.
- **Integrations:** Stubs and structure for Jira, Slack, etc.; RIL (Requirements Intelligence Layer) pipeline structure.
- **Billing:** Outcome-based model design (refactors, API changes, seats); metering and pricing modules.

### 4.2 Out of scope (explicit)

- General-purpose chat or open-ended code generation without a defined refactor/change intent.
- Training on customer code without explicit opt-in and contract.
- Replacement of human review for apply: preview and explicit accept remain required.
- Full implementation of all integrations (OAuth, webhooks) in MVP; structure and key integrations only.
- Legal/compliance certification (SOC 2 audit, ISO certification) — platform is designed to support them; actual certification is separate.

---

## 5. Stakeholders

| Stakeholder | Role | Interests |
|-------------|------|-----------|
| **Developers** | End users | Safe refactors; clear diff preview; rollback; fast feedback |
| **Tech leads / architects** | Decision makers | Blast radius; ownership; contract safety; consistency |
| **Security / compliance** | Governance | No-AI zones; audit; tenant isolation; RBAC; evidence |
| **Platform / DevOps** | Operators | Self-hosted option; observability; scaling; cost controls |
| **Product / founder** | Owner | Differentiation; enterprise adoption; predictable economics |
| **Investors** | Capital | Moat; scalability; enterprise readiness |

---

## 6. Success Criteria

### 6.1 MVP (Phase 1)

- Refactor API runs full pipeline (compile → plan → generate → validate → preview → apply) with real LLM.
- Rollback restores all files on apply failure (verified via Day 14 Golden Path).
- No silent writes; no partial applies; diffs are unified and deterministic.
- Documentation: ARCHITECTURE, COMPLIANCE, STATUS, BRD, FSD current and honest.

### 6.2 Phase 2 (Trusted MVP)

- No-AI zones enforced before refactor; RBAC and tenant on every request.
- Diff preview UI in workspace or IDE; ownership warnings.
- Audit events persisted; evidence locations documented.

### 6.3 Production / scale

- API availability ≥ 99.95%; latency targets (e.g. context &lt; 200 ms P99, refactor &lt; 5 s P99).
- 10,000+ concurrent users per cluster; 100k+ refactors/month.
- SOC 2 / ISO 27001 evidence collectable; runbooks and AI usage policy in place.

---

## 7. Assumptions

- Enterprise customers will accept “preview then apply” and will not demand fully autonomous writes without review.
- CODEOWNERS (or equivalent) exists or can be added for ownership-aware behavior.
- At least one LLM endpoint (e.g. vLLM) is available for code generation; fallback to premium API is acceptable for some tenants.
- Target codebases are primarily Python and/or TypeScript/JavaScript for MVP; other languages are later scope.
- Compliance requirements are known and stable enough to map controls to implementation (SOC 2, ISO 27001).

---

## 8. Constraints

- **No direct writes without preview:** All file modifications require diff preview and explicit approval.
- **AST-based transforms:** Code transformations must be AST-aware where applicable; no regex-only code edits.
- **Deterministic execution:** Same inputs (intent, context) must yield same plan and validation outcome; LLM output is constrained by context and schema.
- **No shared tenant state:** Tenants are isolated (graph, storage, audit); cross-tenant access is forbidden.
- **Audit and reversibility:** Every change must be auditable and reversible (rollback).

---

## 9. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LLM outage or poor quality | Refactor pipeline fails or produces bad code | Medium | Multi-provider/fallback; validation gates; rollback |
| Knowledge graph stale or wrong | Wrong blast radius; missed dependencies | Medium | Indexing pipeline; webhooks/sync; depth limits |
| Enterprise adoption slow | Revenue and traction delayed | Medium | Clear compliance mapping; self-hosted option; outcome-based pricing |
| Prompt injection / exfiltration | Security breach; compliance failure | Low | Sanitization; validation; no raw code in logs; sandbox |
| Competitor copies approach | Moat eroded | Medium | Execute fast; lock in graph + state machine + enterprise controls |

---

## 10. High-Level Capabilities (Product)

1. **Refactor by intent** — User submits intent (e.g. “Rename create_user to create_user_v2”) and primary file; system resolves symbol, dependencies, ownership; generates and validates code; shows diff; applies or rolls back.
2. **Blast-radius visibility** — Affected files, ownership, and cross-owner flags are computed and exposed in plan and API response.
3. **Transactional apply** — Backup before write; apply all or rollback all; no partial state.
4. **No-AI zones** — Configurable exclusion of paths/content (auth, payment, crypto, compliance, secrets); hard block and audit.
5. **Multi-channel access** — API, CLI, Web workspace, VS Code, JetBrains (structure).
6. **Knowledge Graph** — Model and query code entities and relationships; tenant-scoped.
7. **Audit and compliance** — Structured audit events; SOC 2 / ISO 27001 control mapping; redacted logging.
8. **Self-hosted / air-gapped** — Option to run inference and platform on-prem; no data sent to third-party LLM by default.
9. **Recursive quality validation** — 5-stage Gauntlet (Core → Functional → System → Non-Functional → Security) with self-healing and restart-from-zero on failure. "No-Pass, No-Push" gateway.
10. **Collective intelligence** — Cross-project pattern sharing via anonymized Wisdom Nuggets. Semantic duplicate detection prevents reinventing the wheel.
11. **License & ethical compliance** — Automated license compatibility enforcement, provenance tracking with attribution chains, toxic snippet scanning for bias/malware/leaked code.
12. **Chaos & adversarial testing** — Fault injection, prompt injection resistance, red team logic exploitation scanning.
13. **Organization-wide security posture** — Treemap heatmap across all projects, SBOM generation, NVD vulnerability watch, churn risk hotspot analysis.

---

## 11. Dependencies

- **External:** LLM inference (vLLM or compatible API); optional vector DB (Qdrant); optional Redis/DB for persistence.
- **Internal:** Backend (Python/FastAPI); frontends (React, VS Code extension, CLI); infrastructure (Docker, K8s).
- **Organizational:** Product/engineering alignment on scope; compliance/security sign-off on control design.

---

## 12. Glossary

| Term | Definition |
|------|------------|
| **Blast radius** | Set of files (and optionally owners) affected by a refactor. |
| **RefactorBlastContext** | Immutable context object: resolved symbol, affected files, ownership, blast-radius metrics. |
| **PlanExecutor** | Component that runs an ExecutionPlan (GENERATE_CODE → VALIDATE_CODE → PREVIEW_DIFF → APPLY_DIFF) with no step skip. |
| **ExecutionPlan** | Ordered list of steps (with kind and files) plus metadata (file_count, has_cross_owner). |
| **No-AI zone** | Path or content pattern where AI-driven code modification is forbidden. |
| **CODEOWNERS** | File (e.g. in repo root) that maps paths to owning teams. |
| **Golden Path** | End-to-end happy path: refactor request → compile → plan → execute → apply (and optionally rollback test). |
| **RIL** | Requirements Intelligence Layer — pipeline for ingestion (e.g. Slack/Teams/Zoom), structuring, and execution. |

---

## 13. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-31 | — | Initial BRD; aligned with ARCHITECTURE, TECHNICAL_MOAT, STATUS. |
| 1.2 | 2026-03-03 | — | Updated with Day 13-21 capabilities: Titan Phase, Collective Intelligence, Legal Governance, Launch Command Center. Updated audit note with honest current status. |

---

*Related: [FSD.md](./FSD.md) (Functional Specification), [ARCHITECTURE.md](./ARCHITECTURE.md), [TECHNICAL_MOAT.md](./TECHNICAL_MOAT.md), [STATUS.md](./STATUS.md), [COMPLIANCE.md](./COMPLIANCE.md).*
