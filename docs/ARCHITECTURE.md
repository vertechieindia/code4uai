# code4u.ai — Architecture & Operations

Single reference for system design, repository layout, security, self-hosted LLM, and production roadmap. For the current file tree, see [FILE_STRUCTURE.md](./FILE_STRUCTURE.md).

---

## 1. Executive Summary

code4u.ai is an AI-native engineering platform for enterprise-scale development: 500+ micro-frontends, 500+ microservices, billions of lines of code. It is a **Code Intelligence Platform**, **Deterministic Refactoring Engine**, and **Enterprise Execution System** — not a chat assistant.

---

## 2. Repository Layout (Mental Model)

The repository is organized so that each architectural layer maps to a clear location. **Update [FILE_STRUCTURE.md](./FILE_STRUCTURE.md) whenever the layout changes.**

| Layer / Concern | Location | Contents |
|-----------------|----------|----------|
| **Platform core** | `backend/src/code4u/platform_core/` | State machine, rules engine, agents, IDE protocol, agent manager, browser agent |
| **AI engine** | `backend/src/code4u/ai_engine/` | LLM client/router/executor, model picker, prompt compiler, routing, training, evaluation, autocomplete, supercomplete |
| **Code intelligence** | `backend/src/code4u/code_intelligence/` | Knowledge graph, context compiler/planner, knowledge store |
| **Change execution** | `backend/src/code4u/change_execution/` | Diff engine (transactions), validation (AST, diff) |
| **Security & compliance** | `backend/src/code4u/security_compliance/` | Security (tenant, RBAC, no-AI zones, audit), compliance, billing |
| **Requirements intelligence** | `backend/src/code4u/requirements_intelligence/ril/` | RIL pipeline (ingestion, intelligence, structuring, agent) |
| **Interfaces** | `backend/src/code4u/interfaces/` | FastAPI app + routes, integrations (Jira, Slack, etc.), MCP marketplace |
| **Day 1-30 agents** | `backend/src/code4u/agents/` | Specialist agents: chat, healing, migration, review, vision, orchestrator, forge, nexus, sentinel, performance, chaos, adversarial, red_team, predictor, wisdom, legal + quality_swarm/ (accessibility, localization, compatibility, performance) |
| **Validation** | `backend/src/code4u/validation/` | Gauntlet orchestrator, recursive quality pipeline |
| **Analytics** | `backend/src/code4u/analytics/` | Hotspot analyzer, churn risk mapping |
| **Knowledge (Wisdom)** | `backend/src/code4u/knowledge/` | Pattern extractor, provenance tracker |
| **Day 1-30 core** | `backend/src/code4u/core/` | Config, logging, recipes, watcher, presence, staging, guardrails, consensus, nexus, loader, version, dist, cache (Redis + LRU), collaboration (CRDT) |
| **Day 1-30 models** | `backend/src/code4u/models/` | ReviewAudit, AuditStore (analytics) |
| **Day 1-30 TUI** | `backend/src/code4u/interfaces/cli/` | War Room TUI dashboard |
| **Frontends** | `frontends/` | Web workspace, dashboards, VS Code/JetBrains extensions, mobile, shared packages |
| **Infrastructure** | `infrastructure/` | Docker, Kubernetes |
| **Docs** | `docs/` | Architecture, compliance, status, file structure |

**Backend entrypoint:** `code4u.interfaces.api.app:app`

---

## 3. Core Principles

### 3.1 Non-Negotiable Rules

1. **No Direct Writes** — All file modifications require diff preview and explicit approval  
2. **AST-Based Transforms** — Never use regex for code transformations  
3. **Structured Outputs** — All LLM responses follow strict JSON schemas  
4. **No Hallucinations** — If context is insufficient, halt and request clarification  
5. **Correctness Over Cleverness** — Prioritize reliability over novel solutions  
6. **Full Auditability** — Every change has a complete audit trail  
7. **Transactional Rollback** — Any failed operation can be fully reverted  

### 3.2 Design Philosophy

| Principle | Meaning |
|-----------|---------|
| **Deterministic** | Same input → same output |
| **Observable** | Every step produces structured telemetry |
| **Reversible** | Every change can be rolled back |
| **Contract-First** | API schemas drive all integrations |
| **Ownership-Aware** | CODEOWNERS enforced at edit time |
| **Blast-Radius** | Every edit shows impact scope |

---

## 4. System Layers (Logical)

```
Layer 7: UX / Trust          — Diffs • Impact summaries • Ownership alerts • Rollback
Layer 6: Change Application  — Transactional diffs • Partial accept • Audit trail
Layer 5: Multi-Agent         — Planner • Contract • Frontend • Backend • Verifier
Layer 4: LLM Orchestration   — Constrained prompts • Schema enforcement
Layer 3: Context Selection   — Symbol • Dependency • Ownership • Impact aware
Layer 2: Code Knowledge Graph — AST nodes • Dependencies • Schemas • Ownership
Layer 1: IDE / Editor        — VS Code • Monaco Web IDE • CLI • API Gateway
```

### 4.1 Code Knowledge Graph (Layer 2)

- **Nodes:** Repository → Package → Module → Symbol; Team → Service → Endpoint → Schema  
- **Relationships:** owns, contains, declares, imports, exposes, uses, consumes, federates  
- **Backend:** `backend/src/code4u/code_intelligence/knowledge_graph/`  
- **Frontend package:** `frontends/packages/knowledge-graph/`

### 4.2 Context Selection (Layer 3)

1. Symbol lookup → 2. Dependency traversal → 3. Ownership lookup → 4. Impact analysis → Context package (files, owners, blast_radius).

**Rules:** Never load entire repos; depth-limited traversal; flag cross-team boundaries; schema-first; include related tests.

- **Backend:** `backend/src/code4u/code_intelligence/context/` (compiler, planner)

### 4.3 Multi-Agent Execution (Layer 5)

**Planner** → Contract / Frontend / Backend agents → **Verifier** → Execution result (diffs, verification, approvals). No skipping states.

**State machine:** INIT → IMPACT_ANALYZED → PLAN_GENERATED → CONTRACT_VALIDATED → CODE_GENERATED → VERIFIED → READY_FOR_REVIEW → APPLIED | REJECTED  

- **Backend:** `backend/src/code4u/platform_core/state_machine/`, `platform_core/agents/`, `platform_core/protocol/`

### 4.4 Change Application (Layer 6)

**Phases:** Preview → User decision (accept/reject) → Application (backup, apply, verify) → Verification → COMMITTED or ROLLED_BACK. All diffs unified format with metadata (transaction_id, file_hash, hunks, owner).

- **Backend:** `backend/src/code4u/change_execution/diff_engine/`, `change_execution/validation/`

### 4.5 Trust / UX (Layer 7)

Zero silent changes; full transparency; granular accept/reject; instant rollback; audit trail; ownership warnings.

---

## 5. Security & Isolation

### 5.1 Tenant Isolation

Each tenant: separate Knowledge Graph, embeddings, LoRA adapters (optional), storage, audit logs. **No shared state.** Every operation receives a validated `TenantContext`. Cross-tenant access is **always denied**.

- **Backend:** `backend/src/code4u/security_compliance/security/tenant.py`, `security/isolation.py`

### 5.2 Model Isolation

- **Shared + LoRA:** One base model, tenant-specific LoRA (cost-effective).  
- **Dedicated:** One model per tenant (regulated industries).  
- **Hybrid:** Shared for simple tasks, dedicated for sensitive ops.

### 5.3 RBAC on Intents

**Permissions:** view_code, refactor, modify_public_api, approve_breaking_change, etc.  
**Roles:** viewer → developer → senior_developer → tech_lead → admin.

- **Backend:** `backend/src/code4u/security_compliance/security/rbac.py`

### 5.4 No-AI Zones

AI is **blocked** from modifying: auth, payment, crypto, compliance logic, secrets (e.g. `.env`, `.pem`). Implemented via path/content patterns; hard block = immediate reject + log + notify.

- **Backend:** `backend/src/code4u/security_compliance/security/no_ai_zones.py`

### 5.5 Audit Logging (SOC2-Ready)

Every operation: event ID, timestamp, tenant/user/session, operation details, **content hashes only** (no raw prompts/responses), cryptographic signature.

- **Backend:** `backend/src/code4u/security_compliance/security/audit.py`

### 5.6 Security Controls Summary

| Control | Implementation |
|---------|----------------|
| mTLS | Between all services |
| RBAC | On all intents |
| Signed diffs | Integrity |
| Redacted logging | No raw prompts/responses |
| No-AI zones | Hard blocks on sensitive code |
| Tenant isolation | Separate graphs, embeddings, storage |

**Evidence:** `backend/src/code4u/security_compliance/security/` (tenant, isolation, rbac, no_ai_zones, audit)

---

## 6. Self-Hosted LLM Stack

### 6.1 Principles

- LLM is **not** the brain — Knowledge Graph + rules decide; LLM fills code.  
- **Determinism > raw intelligence.** Cost scales sub-linearly. Everything observable, debuggable, rollbackable.

### 6.2 Flow

IDE → Orchestration API (intent router, policy, cost-aware selection) → Context Compiler / Planner → **LLM inference (vLLM + open model)** → Validation & Diff Engine → Workspace.

### 6.3 Hardware (Lean)

| Component | Choice |
|-----------|--------|
| GPU | 2× L40S (48GB) or 1× A100 80GB |
| CPU | 32–64 cores |
| RAM | 128–256 GB |
| Storage | NVMe 2–4 TB |

**Models:** Inference — `Qwen/Qwen2.5-Coder-32B` (primary), Mixtral-8x7B (fallback). Embeddings — `BAAI/bge-large-en-v1.5` or e5-large.

### 6.4 Routing Logic

```text
IF complexity < threshold → Self-hosted
IF retry_count >= 2 → Premium fallback
IF tenant = "air-gapped" → Self-hosted ONLY
```

- **Backend:** `backend/src/code4u/ai_engine/routing/` (engine, complexity, cost_controls)

### 6.5 Training (QLoRA)

4-bit quantization, LoRA adapters. Dataset: refactor diffs, schema evolution, frontend↔backend sync, reject cases. Quality > quantity (MVP 20k–50k examples).

- **Backend:** `backend/src/code4u/ai_engine/training/`, `ai_engine/evaluation/`

### 6.6 Deployment

- **Dev:** `cd infrastructure/docker && docker-compose -f docker-compose.gpu.yml up -d`  
- **Prod:** `kubectl apply -f infrastructure/kubernetes/`

**Evidence:** `backend/src/code4u/ai_engine/llm/`, `code_intelligence/context/`, `ai_engine/training/`, `change_execution/validation/`

---

## 7. Deployment & Performance

### 7.1 Production Topology

Edge (CloudFlare/AWS) → Kubernetes (API Gateway, Graph, LLM, Embed, Verify, Audit, Web IDE, Workers) → Data (PostgreSQL, Qdrant, Redis, S3/MinIO). Multi-AZ; optional second region.

### 7.2 Performance Targets

| Metric | Target |
|--------|--------|
| Context retrieval | < 200 ms (P99) |
| LLM response | < 5 s (P99 simple refactors) |
| Diff generation | < 500 ms (P99) |
| Knowledge graph query | < 50 ms (P99) |
| Concurrent users | 10,000+ per cluster |

### 7.3 Security (Network / Auth / Data)

TLS 1.3, mTLS between services, VPC isolation; OAuth 2.0/OIDC, SSO; RBAC, CODEOWNERS; encryption at rest (AES-256), field-level for secrets; immutable audit logs; no code exfiltration, sandboxed execution.

---

## 8. Production Roadmap (Summary)

| Phase | Focus | Duration |
|-------|--------|----------|
| 1 | Core stabilization: error handling, observability, testing | Weeks 1–4 |
| 2 | Security: auth (OIDC/SSO), RBAC, data/code security | Weeks 5–8 |
| 3 | Scalability: K8s, HPA, DB/Redis/Qdrant, multi-tenancy | Weeks 9–12 |
| 4 | Enterprise: SOC 2 prep, GDPR, integrations, admin | Weeks 13–16 |
| 5 | Advanced: multi-model, KG enhancements, DX (CLI, IDE, CI) | Weeks 17–24 |

**Success metrics:** API availability 99.95%; latency targets as above; error rate < 0.1%; MAU 10k+; refactors 100k+/month.

**Risks:** LLM outage → multi-provider + fallback; vector DB → sharding + cache; KG staleness → webhooks + sync; prompt injection → sanitization + validation; exfiltration → no raw code storage + sandbox.

---

## 9. Day 13-21 Extensions (March 2026)

The platform was extended with 9 additional development phases:

### 9.1 Model Agnosticism & Air-Gapped Mode (Day 13)
- **Local LLM Support:** Ollama/vLLM integration via OpenAI-compatible API
- **Dynamic Model Routing:** `MODEL_ROUTING_TABLE` maps 14 agent types to cloud/local models
- **Air-Gapped Mode:** Runtime toggle blocks all external API calls
- **Local Vector Store:** FAISS/numpy fallback with hashed TF-IDF embeddings (256d)
- **Evidence:** `ai_engine/llm/smart_router.py`, `ai_engine/vector_store.py`, `interfaces/api/routes/airgap.py`

### 9.2 Production Hardening (Day 14-15)
- **System Doctor:** `GET /health/doctor` probes DB, Redis, LLM, Git, Vector Store, Disk
- **Emergency Kill Switch:** `POST /swarm/kill-all` terminates all active agent PIDs
- **Onboarding Tour:** 16-step guided overlay with SVG spotlight system
- **Compliance Export:** `GET /projects/{id}/export-report` generates Markdown audit report
- **Model Distillation:** Collects successful agent executions as JSONL training data
- **CRDT Collaboration:** Lamport-clocked insert/delete/replace operations
- **Ephemeral Staging:** Generates Vercel, K8s, or Docker Compose preview configs
- **Smoke Test Suite:** 10 automated checks with SHA-256 signature chain

### 9.3 Titan Phase — Recursive Quality Gauntlet (Day 15+)
- **5-Stage Pipeline:** CORE → FUNCTIONAL → SYSTEM → NON_FUNCTIONAL → SECURITY
- **Recursive Healing:** On failure, HealAgent fixes code and restarts from Stage 1 (max 10 cycles)
- **Quality Swarm:** AccessibilityAgent, LocalizationAgent, CompatibilityAgent, PerformanceAgent
- **Security Fortress:** ThreatModelAgent, PentestAgent, FuzzAgent, AuditAgent
- **No-Pass-No-Push Gateway:** Gauntlet must pass before Git commit/push is allowed
- **Evidence:** `validation/gauntlet_orchestrator.py`, `agents/quality_swarm/`, `security_compliance/security/fortress_swarm.py`

### 9.4 Ecosystem Connect (Day 16)
- **PR Integration:** Posts Titan Audit Report to GitHub/GitLab PRs
- **SBOM Generator:** CycloneDX 1.5 from 6 manifest formats (package.json, requirements.txt, pyproject.toml, go.mod, Cargo.toml, pom.xml)
- **NVD Watch:** Real-time CVE monitoring via NVD API 2.0
- **Organization Dashboard:** Treemap security heatmap across all projects

### 9.5 Predictive Intelligence (Day 17)
- **Hotspot Analyzer:** Git churn × cyclomatic complexity = risk score per file
- **Predictor Agent:** Flags changes matching 7 regression patterns (auth, validation, concurrency, etc.)
- **Parallel Gauntlet:** `asyncio.gather()` for concurrent stage execution

### 9.6 Adversarial & Chaos Engineering (Day 18)
- **Chaos Agent:** Fault injection (SIGTERM, latency, memory pressure, stage corruption, network partition)
- **Adversarial Agent:** 15 prompt injection/jailbreak hygiene tests
- **Red Team Agent:** Scans for race conditions, unprotected endpoints, privilege escalation, business logic flaws

### 9.7 Collective Intelligence (Day 19)
- **Pattern Extractor:** Anonymizes fixes (9 PII patterns), stores as "Wisdom Nuggets" in central vector store
- **Wisdom Agent:** Queries nugget store during Gauntlet: "Has anyone fixed this before?"
- **Semantic Duplicate Finder:** Identifies functions with similar semantics across different projects

### 9.8 Legal & Ethical Governance (Day 20)
- **License Compliance Agent:** 18 licenses, 4 categories (permissive/weak copyleft/strong copyleft/proprietary), compatibility matrix
- **Provenance Tracker:** Records origin of every AI-generated change, exports `attribution.json`
- **Toxic Snippet Scanner:** 15 forbidden patterns (bias, malware, leaked code, ethical violations)

### 9.9 Final Optimization & Launch (Day 21)
- **Redis Cache Manager:** 6 namespaces with configurable TTLs, in-memory LRU fallback
- **Partitioned Vector Store:** Per-tenant indexes + global wisdom index for sub-millisecond search
- **Stress Test Suite:** Configurable load simulation up to 10K concurrent tasks
- **Launch Command Center:** Impact summary, readiness check, vector benchmark

---

## 10. Current Status (Honest Assessment — March 2026)

1. ✅ Architecture (this document) — updated through Day 21
2. ✅ Repository structure ([FILE_STRUCTURE.md](./FILE_STRUCTURE.md))
3. ✅ Knowledge Graph — SymbolIndexer + DependencyMap fully implemented and tested
4. ✅ Refactor pipeline — PlanExecutor with atomic rollback, verified with E2E tests
5. ✅ CLI — 30+ local-first commands with `typer` + `rich`
6. ✅ 22 specialist agents — all implemented with 1,360+ tests passing
7. ✅ VS Code extension — real implementation, requires running backend
8. ✅ Authentication — JWT-based with login/register/GitHub OAuth
9. ✅ Frontend workspace — 18 pages, real auth, onboarding tour, Guardian, OrgDashboard
10. ✅ 42 API route files — all mounted and responding
11. ✅ Recursive Gauntlet — 5-stage validation with self-healing
12. ✅ License compliance — 18 licenses, compatibility matrix, transfer gating
13. ✅ Toxic snippet scanner — 15 forbidden patterns with blocking
14. ✅ Collective intelligence — Wisdom nuggets, provenance tracking, attribution
15. ✅ Caching & vector partitioning — Redis/memory cache, multi-tenant vector store
16. ⚠️ LLM integration — adapters exist but require API keys; local fallback for testing
17. ⚠️ Frontend mock data — Several pages show simulated data instead of real API responses
18. ⚠️ Integrations — Jira/Slack partially implemented; 15+ others are stubs
19. ⚠️ Real-time features — WebSocket presence, collaboration use simulated data in UI
20. ⚠️ Database persistence — Most state is in-memory; PostgreSQL/Redis not wired for production
21. ❌ Docker Compose — broken path references
22. ❌ Production deployment — not battle-tested

---

*For the current file tree, see [FILE_STRUCTURE.md](./FILE_STRUCTURE.md). For compliance (SOC 2, ISO 27001), see [COMPLIANCE.md](./COMPLIANCE.md). For investor differentiation, see [TECHNICAL_MOAT.md](./TECHNICAL_MOAT.md). For implementation status, see [STATUS.md](./STATUS.md). For testing, see [TESTING.md](./TESTING.md).*
