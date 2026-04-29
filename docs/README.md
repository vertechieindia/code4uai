# code4u.ai Documentation

Single-source documentation for the platform. All content has been consolidated and updated.

**Last updated:** 2026-03-03 (Day 21 — Sovereign Launch complete)

---

## Documents

| Document | Purpose | Status |
|----------|---------|--------|
| **[STATUS.md](./STATUS.md)** | **Implementation status** — honest assessment of what works, what's partial, what's stub | Updated Day 21 |
| **[FILE_STRUCTURE.md](./FILE_STRUCTURE.md)** | **Current file structure** — verified against actual filesystem | Updated Day 21 |
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | System design, layers, security, deployment, roadmap | Updated Day 21 |
| **[BRD.md](./BRD.md)** | **Business Requirements Document** — objectives, scope, risks | Updated Day 21 |
| **[FSD.md](./FSD.md)** | **Functional Specification Document** — features, API contracts, criteria | Updated Day 21 |
| **[COMPLIANCE.md](./COMPLIANCE.md)** | SOC 2 and ISO 27001 control mapping | Updated Day 21 |
| **[TECHNICAL_MOAT.md](./TECHNICAL_MOAT.md)** | Investor-grade differentiation, competitive framing | Updated Day 21 |
| **[FRONTEND_STATUS.md](./FRONTEND_STATUS.md)** | **Frontend audit** — every page, what works, what's mock, what to build | Updated Day 21 |
| **[TESTING.md](./TESTING.md)** | **Test suite documentation** — 1,140+ backend tests, 147+ frontend tests | Updated Day 21 |
| **[REPOSITORY_RESTRUCTURE.md](./REPOSITORY_RESTRUCTURE.md)** | Repository restructure deliverable and rename log | Updated Day 21 |

---

## Quick Summary (as of Day 21)

| Metric | Value |
|--------|-------|
| Backend Python modules | ~279 |
| Frontend TS/TSX files | ~32 |
| Backend test files | 37 (original 23 + 7 comprehensive + 5 Day 15 + 2 Day 19-21) |
| Total backend tests | ~1,140+ (921 original + 215 comprehensive + 140 Day 19-21) |
| Frontend test files | 10 (8 original + 2 comprehensive) |
| Total frontend tests | ~147+ (61 original + 86 comprehensive) |
| API route files | 42 (34 original + 8 new: airgap, doctor, export, distillation, collaboration, staging, smoke, guardian, nvd_watch, hotspot, chaos, wisdom, governance, launch) |
| Specialist agents | 22 (12 original + 10 new: chaos, adversarial, red_team, predictor, wisdom, legal, accessibility, localization, compatibility, performance quality swarm) |
| CLI commands | 30+ |
| Integration stubs | 15+ (Jira/Slack partially implemented) |
| Pages (frontend) | 18 (16 original + GuardianPage + OrgDashboard) |
| New backend domains | 5 (knowledge/, validation/, analytics/, quality_swarm/, Day 19-21 modules) |

---

## What Was Built (Day 13-21)

| Day | Phase | Key Deliverables |
|-----|-------|-----------------|
| 13 | Model Agnostic & Local LLM | Ollama/vLLM integration, Smart Router, Air-Gapped Mode, Local Vector Store (FAISS) |
| 14 | Production Hardening | System Doctor, Emergency Kill Switch, Onboarding Tour (16 steps), Compliance Export |
| 15 | Post-Launch Roadmap | Model Distillation, CRDT Collaboration, Ephemeral Staging, Smoke Test Suite |
| 15+ | Titan Phase | Recursive Gauntlet Orchestrator, Quality Swarm (4 agents), Security Fortress (4 agents), Guardian Mission Control UI, No-Pass-No-Push Gateway |
| 16 | Ecosystem Connect | GitHub/GitLab PR Integration, CycloneDX SBOM Generator, NVD Vulnerability Watch, Organization Security Heatmap Dashboard |
| 17 | Predictive Intelligence | Git Churn Hotspot Analyzer, Predictive Bug Detection Agent, Parallel Gauntlet (asyncio), Worker Resource Monitor UI |
| 18 | Adversarial & Chaos | Chaos Agent (fault injection), Adversarial Agent (prompt injection testing), Red Team Agent (logic exploitation), Resilience Dashboard UI |
| 19 | Collective Intelligence | Cross-Project Pattern Extractor (Wisdom Nuggets), Wisdom Agent, Semantic Duplicate Finder, Wisdom Dashboard UI |
| 20 | Legal & Ethical | License Compliance Agent (18 licenses, 4x4 compatibility matrix), Provenance Tracker (attribution.json), Toxic Snippet Scanner (15 forbidden patterns), Governance & Ethics UI |
| 21 | Final Optimization | Redis Cache Manager (6 namespaces), Partitioned Vector Store (multi-tenant), Stress Test Suite, Launch Command Center with Impact Summary |

---

## What Still Needs Work (Honest)

1. **LLM Integration** — Adapters exist but require API keys; not tested against live providers
2. **Frontend Mock Data** — Many pages show mock/simulated data instead of real API responses
3. **Integration Stubs** — Only Jira/Slack partially implemented; 15+ others are `__init__.py` stubs
4. **Docker Compose** — Broken path references
5. **Production Deployment** — Not battle-tested; no real production traffic
6. **Meeting AI** — Stub implementations; returns mock data
7. **Admin Dashboard** — Only OverviewPage has content; other pages are empty stubs
8. **Web Agent Manager** — Chat UI with fake responses; no backend wiring
9. **Real-time WebSockets** — Presence, collaboration, and telemetry use simulated data in the UI
10. **Database Persistence** — Most state is in-memory; PostgreSQL/Redis not wired for production

---

## Quick Links

- **Run backend:** `cd backend && pip install -e . && code4u welcome .`
- **Run API server:** `cd backend && uvicorn code4u.interfaces.api.app:app --reload --port 8000`
- **Run frontend:** `cd frontends/workspace && pnpm install && pnpm dev` (loads on http://localhost:3000)
- **Run backend tests:** `cd backend && PYTHONPATH=src python -m pytest tests/ -v`
- **Run frontend tests:** `cd frontends/workspace && npx vitest run`
- **Default login:** `admin@code4u.ai` / `admin123` (register via `POST /api/v1/auth/register`)
- **Current file structure:** [FILE_STRUCTURE.md](./FILE_STRUCTURE.md)
- **Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Compliance:** [COMPLIANCE.md](./COMPLIANCE.md)
