# code4u.ai — Comprehensive Test Suite Documentation

**Last updated:** 2026-03-03 (Day 21 — after full application testing)

## Test Summary

| Category | Backend Tests | Frontend Tests | Total |
|----------|:---:|:---:|:---:|
| Original Test Suite (Day 1-30) | 921 | — | 921 |
| Comprehensive Suite (Day 15) | 154 | 61 | 215 |
| Day 19-21 Unit Tests | 96 | — | 96 |
| Day 19-21 Integration Tests | 44 | — | 44 |
| Comprehensive Pages Tests | — | 58 | 58 |
| Security & Performance Tests | — | 28 | 28 |
| **Grand Total** | **~1,215** | **~147** | **~1,362** |

---

## Testing Types Covered

### Functional Testing
- **Unit Testing** — Individual functions, classes, and modules tested in isolation (PatternExtractor, WisdomAgent, LegalAgent, ProvenanceTracker, ToxicScanner, InMemoryLRUCache, RedisCacheManager, PartitionedVectorStore)
- **Integration Testing** — API routes tested with real middleware, auth, and cross-module flows (Wisdom→Legal gate, Wisdom→Provenance, Toxic→Cache, Vector→Wisdom)
- **System Testing** — Complete end-to-end user flows (register → login → use features → verify)
- **Acceptance Testing (Alpha)** — User journey simulations matching real-world workflows

### Non-Functional Testing
- **Performance Testing** — Response time benchmarks (cache 10K ops < 1s, toxic scan 100 files < 2s, vector search 10K docs in 0.5ms, page renders < 500ms)
- **Load/Stress Testing** — Concurrent task simulation via `/launch/stress-test` (up to 10K tasks)
- **Security Testing** — SQL injection, XSS, JWT tampering, CORS, token expiry, anonymization completeness, toxic pattern blocking, license gate enforcement
- **Accessibility Testing** — WCAG compliance, form labels, ARIA attributes, keyboard navigation, heading hierarchy
- **Compatibility Testing** — Browser rendering, responsive design, viewport meta, localStorage, fetch, ResizeObserver, IntersectionObserver, matchMedia
- **Localization Testing** — i18n readiness, extractable text, locale-aware formatting, no hardcoded dates

### Testing Methodologies
- **Black Box Testing** — E2E system tests treating the API as an opaque service
- **White Box Testing** — Unit tests with full knowledge of internal implementations
- **Grey Box Testing** — Integration tests using partial knowledge (API contracts + some internals)
- **Manual Testing** — CI pipeline provides test reports for human review

### Quality Assurance
- **Smoke Testing** — Critical path verification (all endpoints respond, all pages render, auth works)
- **Sanity Testing** — Targeted checks (singleton instantiation, pattern counts, license catalog counts)
- **Regression Testing** — Guards against regressions (ROI cards, gauntlet stages, dashboard tabs)

---

## Test Files Inventory

### Backend Tests (`backend/tests/`)

#### Original Suite (921 tests, Day 1-30)

| File | Tests | Covers |
|------|-------|--------|
| test_v1_launch.py | 30 | Day 30: Version, distribution |
| test_performance_profiler.py | 43 | Day 29: Profiler, optimizer |
| test_drift_sentinel.py | 55 | Day 28: Rules, sentinel, drift |
| test_nexus_multirepo.py | 34 | Day 27: Nexus, cross-repo |
| test_forge_plugins.py | 42 | Day 26: Plugins, forge |
| test_war_room.py | 49 | Day 25: TUI dashboard |
| test_autonomous_swarm.py | 58 | Day 24: TaskGraph, ChiefArchitect |
| test_vision_architect.py | 44 | Day 23: VisionAnalyzer |
| test_quality_jury.py | 56 | Day 22: CriticAgent, guardrails |
| test_self_healing.py | 48 | Day 21 (original): StackTraceParser |
| test_presence_collaboration.py | 31 | Day 20: Presence, staging |
| test_migration_agent.py | 33 | Day 19 (original): MigrationPlanner |
| test_graph_chat.py | 54 | Day 18: ContextRetriever |
| test_enterprise_scale.py | 44 | Day 17: Parallel indexing |
| test_analytics_dashboard.py | 47 | Day 16: ReviewAudit, ROI |
| test_github_pr_automation.py | 40 | Day 15: Webhooks, PR review |
| test_recipe_engine.py | 48 | Day 14: Recipes |
| test_multi_llm_switchboard.py | 38 | Day 13: LLM adapters |
| test_streaming_and_events.py | 16 | Day 12: SSE |
| test_concurrency_and_tenancy.py | 19 | Day 11: Workspace locking |
| test_session_and_impact.py | 26 | Day 10: Sessions |
| test_visual_grounder.py | 17 | Day 9: Visual grounding |
| test_rollback_integrity.py | 9 | Day 8: E2E rollback |

#### Comprehensive Suite (Day 15 Testing Sprint — 154 tests)

| File | Tests | Covers |
|------|-------|--------|
| test_comprehensive_unit.py | 43 | All core modules unit tests |
| test_comprehensive_integration.py | 28 | API route integration tests |
| test_e2e_system.py | 20 | Full system E2E tests |
| test_smoke_sanity.py | 18 | Smoke & sanity checks |
| test_regression_suite.py | 15 | Regression guards |
| test_security_audit.py | 15 | Security audit tests |
| test_performance_nonfunctional.py | 15 | Performance benchmarks |

#### Day 19-21 Suite (140 tests)

| File | Tests | Covers |
|------|-------|--------|
| test_day19_21_unit.py | 96 | PatternExtractor (22), WisdomAgent (14), LegalAgent (21), ProvenanceTracker (7), ToxicScanner (13), InMemoryLRUCache (10), RedisCacheManager (7), PartitionedVectorStore (10) |
| test_day19_21_integration.py | 44 | Wisdom API (7), Governance API (11), Launch API (7), Cross-Module (4), Security Audit (4), Performance (3), Smoke & Sanity (5) |

### Frontend Tests (`frontends/workspace/src/test/`)

#### Original Suite (61 tests)

| File | Tests | Covers |
|------|-------|--------|
| unit/AuthContext.test.tsx | 8 | Auth context, token handling |
| unit/components.test.tsx | 12 | Component rendering |
| integration/routing.test.tsx | 10 | Route navigation |
| integration/pages.test.tsx | 9 | Page integration |
| accessibility/a11y.test.tsx | 6 | WCAG compliance |
| smoke/smoke.test.tsx | 5 | Critical path checks |
| regression/regression.test.tsx | 4 | Regression guards |
| compatibility/compatibility.test.tsx | 7 | Browser compatibility |

#### Comprehensive Suite (Day 21 — 86 tests)

| File | Tests | Covers |
|------|-------|--------|
| comprehensive/pages.test.tsx | 58 | Smoke (18 pages), Unit (17), Integration (3), Accessibility (5), Regression (3), Compatibility (5), Localization (2) |
| comprehensive/security-perf.test.tsx | 28 | Security Auth (5), XSS (2), CSRF (1), Performance Render (5), Performance DOM (2), Black Box (4), White Box (3), Grey Box (2), Acceptance (4) |

---

## Running Tests

### Backend
```bash
# All tests
cd backend && PYTHONPATH=src python -m pytest tests/ -v

# Day 19-21 only
cd backend && PYTHONPATH=src python -m pytest tests/test_day19_21_unit.py tests/test_day19_21_integration.py -v

# With coverage
cd backend && PYTHONPATH=src python -m pytest tests/ --cov=src/code4u --cov-report=html
```

### Frontend
```bash
# All tests
cd frontends/workspace && npx vitest run

# Comprehensive only
cd frontends/workspace && npx vitest run src/test/comprehensive/

# With coverage
cd frontends/workspace && npx vitest run --coverage
```

---

## CI/CD

GitHub Actions workflow at `.github/workflows/test.yml`:
- Backend: Python 3.9, 3.11, 3.12
- Frontend: Node.js 18, 20, 22
- Artifact uploads for coverage reports
