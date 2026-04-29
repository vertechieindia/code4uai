# code4u.ai — Current File Structure

**Purpose:** Single source of truth for the repository layout. Update this document whenever you add, remove, or rename top-level folders or backend domains.

**Last updated:** 2026-03-03 (Day 21 — Sovereign Launch — includes all Day 13-21 additions)

---

## Top-level

```
code4u.ai/
├── backend/              # Python backend (code4u package) — FastAPI + CLI
├── frontends/            # Web apps, IDE extensions, shared frontend packages
├── cli/                  # Separate CLI package (code4u_cli) — HTTP client for backend
├── docs/                 # Architecture, compliance, status, file structure (9 docs)
├── infrastructure/       # Docker, Kubernetes
├── scripts/              # Installer, training, inference scripts
├── README.md
├── package.json          # pnpm workspace root
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
└── package-lock.json
```

**Note:** `turbo.json` and `tsconfig.base.json` listed in earlier docs may not exist on disk.

---

## Backend (`backend/`)

```
backend/
├── README.md
├── pyproject.toml                # Poetry, v1.0.0, entry: code4u.cli.main:app
├── .venv/                        # Local virtual environment
├── tests/                        # 37 test files, 1,360+ tests (see Tests section)
└── src/
    └── code4u/
        ├── __init__.py
        │
        ├── core/                          # Config, logging + Day 7-30 additions
        │   ├── __init__.py                # Exports: Settings, recipes, watcher, presence, staging, nexus
        │   ├── config.py                  # Settings via pydantic-settings
        │   ├── logging.py                 # structlog configuration
        │   ├── recipes.py                 # Recipe, RecipeRegistry, RecipeSelector (Day 14)
        │   ├── watcher.py                 # WorkspaceWatcher via watchdog (Day 17)
        │   ├── presence.py                # PresenceManager, WebSocket presence (Day 20)
        │   ├── staging.py                 # StagingArea, collaborative staging (Day 20)
        │   ├── guardrails.py              # StaticGuardrail, GuardrailViolation (Day 22)
        │   ├── consensus.py               # ReviewOrchestrator, Worker-Critic-Judge (Day 22)
        │   ├── nexus.py                   # NexusContext, GlobalRegistry (Day 27)
        │   ├── loader.py                  # PluginLoader, dynamic agent discovery (Day 26)
        │   ├── executor_ext.py            # TestRunner, shell command integration (Day 21)
        │   ├── version.py                 # VERSION = "1.0.0", VersionManager (Day 30)
        │   └── dist.py                    # PyInstaller build config (Day 30)
        │
        ├── cli/                           # Typer CLI — local-first commands
        │   ├── __init__.py                # Exports __version__ from core.version
        │   ├── main.py                    # 30+ commands: index, rename, refactor, health, etc.
        │   ├── history.py                 # History display helpers
        │   └── health.py                  # Health check helpers
        │
        ├── agents/                        # Day 10-29 specialist agents + Day 15-21 additions
        │   ├── __init__.py
        │   ├── base.py                    # AbstractAgent contract (Day 26)
        │   ├── github_reviewer.py         # GitHubReviewer, PR automation (Day 15)
        │   ├── chaos_agent.py             # ChaosAgent, fault injection (Day 18)
        │   ├── red_team_agent.py          # RedTeamAgent, logic exploitation (Day 18)
        │   ├── predictor_agent.py         # PredictorAgent, predictive risk (Day 17)
        │   ├── wisdom_agent.py            # WisdomAgent, collective intelligence (Day 19)
        │   ├── legal_agent.py             # LegalAgent, license compliance (Day 20)
        │   ├── session_manager.py         # SessionManager (Day 10) — ALSO in platform_core/agents/
        │   ├── chat/                      # Graph-augmented chat (Day 18)
        │   │   ├── retriever.py           # ContextRetriever
        │   │   └── assembler.py           # ContextAssembler
        │   ├── healing/                   # Self-healing (Day 21)
        │   │   ├── parser.py              # StackTraceParser
        │   │   └── diagnoser.py           # Diagnoser, RCA
        │   ├── migration/                 # Multi-file migration (Day 19)
        │   │   ├── planner.py             # MigrationPlanner
        │   │   ├── import_sync.py         # ImportSyncer
        │   │   └── executor.py            # MigrationExecutor
        │   ├── review/                    # Quality review (Day 22)
        │   │   └── critic.py              # CriticAgent
        │   ├── vision/                    # Visual intelligence (Day 23)
        │   │   ├── processor.py           # VisionAnalyzer
        │   │   └── mapper.py              # DesignSystemMapper
        │   ├── orchestrator/              # Autonomous swarm (Day 24)
        │   │   ├── models.py              # SubTask, TaskGraph, AgentType
        │   │   ├── chief.py               # ChiefArchitect
        │   │   └── controller.py          # SwarmController
        │   ├── meta/                      # Meta-agents (Day 26)
        │   │   └── forge.py               # ForgeAgent, recipe generation
        │   ├── nexus/                     # Cross-repo (Day 27-28)
        │   │   ├── impact_analyzer.py     # ImpactAnalyzer, BlastRadius
        │   │   ├── rules.py               # ArchitecturalRule, RuleRegistry
        │   │   └── sentinel.py            # Sentinel, drift detection
        │   ├── performance/               # Performance profiling (Day 29)
        │   │   ├── parser.py              # PerformanceIngestor
        │   │   └── optimizer.py           # Optimizer, hot-path analysis
        │   └── quality_swarm/             # Quality testing agents (Day 15 Titan)
        │       ├── __init__.py
        │       ├── accessibility_agent.py # WCAG violations
        │       ├── localization_agent.py  # Hardcoded strings, i18n coverage
        │       ├── compatibility_agent.py # Cross-environment validation
        │       └── performance_agent.py   # cProfile analysis, complexity
        │
        ├── models/                        # Shared data models
        │   ├── __init__.py
        │   └── analytics.py               # ReviewAudit, AuditStore (Day 16)
        │
        ├── interfaces/                    # API, integrations, TUI
        │   ├── __init__.py
        │   ├── api/
        │   │   ├── app.py                 # FastAPI app — 34 routers included
        │   │   └── routes/                # 34 route files (see API Routes section)
        │   ├── cli/
        │   │   └── dashboard.py           # War Room TUI (Day 25)
        │   ├── integrations/              # External service adapters
        │   │   ├── base.py                # Abstract integration contracts
        │   │   ├── registry.py            # Integration registry
        │   │   ├── approval_workflow.py
        │   │   ├── meeting_ai/            # Meeting intelligence (extractor, presenter, etc.)
        │   │   ├── jira/                  # Jira integration (client, webhook, integration)
        │   │   ├── slack/                 # Slack integration (client, handler, integration)
        │   │   ├── teams/, discord/, google/, zoom/, webex/
        │   │   ├── notion/, miro/, figma/, dropbox/
        │   │   ├── asana/, trello/, monday/, clickup/, wrike/, basecamp/
        │   │   ├── servicenow/, zendesk/, freshservice/
        │   │   └── (most have only __init__.py — stubs)
        │   └── mcp_marketplace/           # MCP server management
        │       ├── marketplace.py
        │       ├── registry.py            # Simulated startup, mock tool calls
        │       └── server.py
        │
        ├── platform_core/                 # Original enterprise platform layer
        │   ├── state_machine/             # ExecutionState, StateMachine, Coordinator
        │   ├── agents/                    # PlanExecutor, SessionManager, Sentinel, ProposedPlan
        │   ├── protocol/                  # WebSocket handler, messages
        │   ├── agent_manager/             # AgentManager, sessions, notifications
        │   ├── browser_agent/             # BrowserAgent, Playwright controller
        │   └── rules_engine/              # .mdc rules, workflows
        │
        ├── ai_engine/                     # LLM and AI layer
        │   ├── llm/                       # Client, executor, adapters, smart router, etc.
        │   │   └── adapters/              # OpenAI, Anthropic, Ollama adapters
        │   ├── routing/                   # RoutingEngine, CostController, ComplexityScorer
        │   ├── model_picker/              # ModelRegistry, ModelRouter, ModelPicker
        │   ├── compiler/                  # PromptCompiler, ScopeReducer, Constraints
        │   ├── training/                  # LoRATrainer, DatasetBuilder
        │   ├── evaluation/                # EvaluationRunner, Scorer, GoldenDataset
        │   ├── autocomplete/              # AutocompleteEngine, cache, context
        │   └── supercomplete/             # SupercompleteEngine, TabEngine, predictions
        │
        ├── code_intelligence/             # Code understanding
        │   ├── knowledge_graph/           # KnowledgeGraph, SymbolIndexer, DependencyMap
        │   ├── context/                   # ContextCompiler, ChangePlanner
        │   └── knowledge/                 # KnowledgeStore, MemoryStore
        │
        ├── change_execution/              # Diff and validation
        │   ├── diff_engine/               # DiffTransaction, TransactionManager
        │   └── validation/                # ASTValidator, DiffValidator
        │
        ├── security_compliance/           # Security, compliance, billing
        │   ├── sbom_generator.py          # CycloneDX SBOM from 6 manifest formats (Day 16)
        │   ├── toxic_scanner.py           # Forbidden pattern scanner (Day 20)
        │   ├── security/                  # RBAC, NoAIZones, Audit, Tenant, Isolation
        │   │   ├── adversarial_agent.py   # Prompt injection & jailbreak testing (Day 18)
        │   │   ├── fortress_swarm.py      # ThreatModel, Pentest, Fuzz, Audit agents (Day 15)
        │   │   └── vulnerability_scanner.py # SCA + NVD feed (Day 16)
        │   ├── compliance/                # Controls, Evidence, Monitor
        │   └── billing/                   # Metering, Pricing, Reports
        │
        ├── validation/                    # Quality validation (Day 15 Titan)
        │   ├── __init__.py
        │   └── gauntlet_orchestrator.py   # 5-stage recursive gauntlet
        │
        ├── analytics/                     # Code analytics (Day 17)
        │   ├── __init__.py
        │   └── hotspot_analyzer.py        # Git churn + complexity risk scoring
        │
        ├── knowledge/                     # Collective intelligence (Day 19-20)
        │   ├── __init__.py
        │   ├── pattern_extractor.py       # Wisdom Nugget storage + anonymization
        │   └── provenance_tracker.py       # Attribution tracking + export
        │
        └── requirements_intelligence/     # RIL pipeline
            └── ril/                       # Ingestion, intelligence, structuring, agent, etc.
```

---

## API Routes (`backend/src/code4u/interfaces/api/routes/`)

42 route files, all imported and mounted in `app.py` (34 original + 8 new):

| File | Status | Key Endpoints |
|------|--------|---------------|
| refactor.py | Real | POST /refactor, /rename, /dry-run, /visual, /multi-root, /index, /recipes |
| chat.py | Real | POST /chat/query, /context, /sessions |
| migration.py | Real | POST /migration/plan, /execute, /move |
| healing.py | Real | POST /heal, /heal/run, /heal/parse |
| quality.py | Real | POST /quality/review, /guardrails, /consensus |
| vision.py | Real | POST /vision/analyze, /map, /refactor |
| swarm.py | Real | POST /swarm/plan, /execute |
| nexus.py | Real | POST /nexus/scan, /index, /link |
| sentinel.py | Real | POST /sentinel/scan, /scan-delta |
| profiler.py | Real | POST /profiler/ingest, /analyze, /scan |
| presence.py | Real | WebSocket /ws/presence, POST /staging |
| events.py | Real | GET /events/{job_id} (SSE) |
| webhooks.py | Real | POST /webhooks/github |
| analytics.py | Real | GET /analytics/summary, /heatmap |
| admin.py | Real | PATCH /admin/recipes/{id}/toggle |
| watcher.py | Real | POST /watcher/start, /stop |
| llm.py | Real | POST /internal/generate-diff, /validate-schema |
| graph.py | Real | POST /graph/index, /query, /impact |
| autocomplete.py | Real | POST /autocomplete/complete, /inline |
| browser.py | Real | POST /browser/sessions, /task |
| models.py | Real | GET /models/, POST /models/route |
| rules.py | Real | GET/POST /rules/, /workflows |
| integrations.py | Real | GET /integrations/available, POST /tasks/create |
| meeting.py | Real | POST /meeting/join, /process |
| supercomplete.py | Real | POST /supercomplete/complete, /tab |
| mcp.py | Real | GET /mcp/servers, POST /mcp/install |
| agent.py | Real | POST/GET /agent/tasks, /sessions |
| knowledge.py | Real | POST/GET /knowledge/items, /memories |
| ril.py | Real | POST /ril/capture/start, /webhooks/slack |
| ide.py | Real | POST /generate, /fix-bug, /explain, /chat |
| billing.py | Real | GET /billing/usage/{id}, /tiers |
| compliance.py | Real | GET /compliance/check, /dashboard |
| analysis.py | **Stub** | POST /impact, /ownership — hardcoded responses |
| transactions.py | **Stub** | POST /accept, /reject, /rollback — hardcoded responses |
| airgap.py | Real | GET/POST /airgap/status, /toggle, /providers |
| doctor.py | Real | GET /health/doctor — 7 system probes |
| export.py | Real | GET /projects/{id}/export-report — Markdown audit |
| distillation.py | Real | GET/POST /distill/stats, /collect, /export |
| collaboration.py | Real | POST /collab/join, /op, /leave; GET /collab/doc |
| staging.py | Real | POST /staging/create; GET/DELETE /staging/{id} |
| smoke.py | Real | POST /smoke-test — 10 checks with SHA-256 chain |
| guardian.py | Real | POST /guardian/gauntlet/run, /fortress/scan; GET /guardian/audit/sbom |
| nvd_watch.py | Real | POST /nvd/watch/configure, /poll; GET /nvd/watch/alerts |
| hotspot.py | Real | POST /analytics/hotspots, /predict; GET /analytics/predict/report |
| chaos.py | Real | POST /chaos/toggle, /inject, /round; POST /adversarial/run; POST /red-team/scan |
| wisdom.py | Real | POST /wisdom/nuggets/store, /search, /analyze, /find-duplicates |
| governance.py | Real | POST /governance/license/detect, /check, /gate; POST /governance/toxic/scan; POST /governance/provenance/record |
| launch.py | Real | POST /launch/stress-test, /vector/benchmark; GET /launch/impact-summary, /readiness |

---

## Tests (`backend/tests/`)

37 test files, **~1,360 tests total**, all passing:

| File | Tests | Covers |
|------|-------|--------|
| test_v1_launch.py | 30 | Day 30: Version, distribution, install |
| test_performance_profiler.py | 43 | Day 29: Profiler, optimizer, TUI heatmap |
| test_drift_sentinel.py | 55 | Day 28: Rules, sentinel, drift detection |
| test_nexus_multirepo.py | 34 | Day 27: Nexus, cross-repo impact |
| test_forge_plugins.py | 42 | Day 26: Plugins, forge, marketplace |
| test_war_room.py | 49 | Day 25: TUI dashboard, widgets |
| test_autonomous_swarm.py | 58 | Day 24: TaskGraph, ChiefArchitect, SwarmController |
| test_vision_architect.py | 44 | Day 23: VisionAnalyzer, DesignSystemMapper |
| test_quality_jury.py | 56 | Day 22: CriticAgent, guardrails, consensus |
| test_self_healing.py | 48 | Day 21: StackTraceParser, Diagnoser |
| test_presence_collaboration.py | 31 | Day 20: Presence, staging, locking |
| test_migration_agent.py | 33 | Day 19: MigrationPlanner, ImportSyncer |
| test_graph_chat.py | 54 | Day 18: ContextRetriever, ContextAssembler |
| test_enterprise_scale.py | 44 | Day 17: Parallel indexing, watcher |
| test_analytics_dashboard.py | 47 | Day 16: ReviewAudit, AuditStore, ROI |
| test_github_pr_automation.py | 40 | Day 15: Webhooks, PR review |
| test_recipe_engine.py | 48 | Day 14: Recipes, RecipeRegistry |
| test_multi_llm_switchboard.py | 38 | Day 13: LLM adapters, SmartRouter |
| test_streaming_and_events.py | 16 | Day 12: SSE, status callbacks |
| test_concurrency_and_tenancy.py | 19 | Day 11: Workspace locking, tenancy |
| test_session_and_impact.py | 26 | Day 10: Sessions, predictive impact |
| test_visual_grounder.py | 17 | Day 9: Visual grounding |
| test_rollback_integrity.py | 9 | Day 8: E2E rollback safety |
| test_comprehensive_unit.py | 43 | Comprehensive unit tests |
| test_comprehensive_integration.py | 28 | API integration tests |
| test_e2e_system.py | 20 | End-to-end system tests |
| test_smoke_sanity.py | 18 | Smoke & sanity checks |
| test_regression_suite.py | 15 | Regression guards |
| test_security_audit.py | 15 | Security audit tests |
| test_performance_nonfunctional.py | 15 | Performance benchmarks |
| test_day19_21_unit.py | 96 | Day 19-21 unit tests (PatternExtractor, LegalAgent, ToxicScanner, Cache, etc.) |
| test_day19_21_integration.py | 44 | Day 19-21 integration tests (Wisdom, Governance, Launch APIs) |

---

## Frontends (`frontends/`)

```
frontends/
├── workspace/             # Main web workspace (Vite + React + Tailwind)
│   ├── src/
│   │   ├── App.tsx         # Full layout, routing, dark mode
│   │   ├── IDE.tsx         # IDE with file tree, editor (textarea), terminal
│   │   ├── pages/          # 18 pages (Dashboard, Guardian, OrgDashboard, IDE, Agent, etc.)
│   │   └── index.css
│   ├── dist/               # Built assets (if built)
│   └── package.json
├── dashboard/             # Marketing/compliance dashboard (Vite + React)
│   └── src/App.tsx         # ~2,500 lines, fetches from localhost:8000
├── admin-dashboard/       # Admin UI (Vite + React + Tailwind)
│   └── src/                # OverviewPage real; 11 other pages are stubs
├── web-agent-manager/     # Agent manager UI (Vite + React)
│   └── src/App.tsx         # Chat UI, mock responses (no backend)
├── vscode-extension/      # VS Code extension (TypeScript)
│   └── src/extension.ts    # Real: commands, chat, inline completion, HTTP client
└── packages/
    └── knowledge-graph/   # Shared TypeScript KG library
        └── src/            # Real: graph, schema, query, traversal
```

**Note:** `jetbrains-plugin/` and `mobile-app/` listed in earlier docs — may not exist on disk.

---

## CLI (`cli/`)

```
cli/
├── pyproject.toml
└── src/
    └── code4u_cli/
        ├── main.py            # Typer app, command registration
        ├── client.py          # Async HTTP client (default port 8002)
        └── commands/          # agent, analyze, chat, config, generate, refactor
```

**Note:** This is a SEPARATE CLI package from `backend/src/code4u/cli/`. The backend CLI (`code4u`) runs locally without a server. This CLI (`code4u_cli`) requires a running backend server.

---

## Infrastructure (`infrastructure/`)

```
infrastructure/
├── docker/
│   ├── Dockerfile             # Python 3.11, backend API
│   ├── docker-compose.yml     # BROKEN: references infra/docker/ instead of infrastructure/
│   └── docker-compose.gpu.yml # BROKEN: same path issue
└── kubernetes/
    └── *.yaml                 # K8s deployment manifests
```

---

## Scripts (`scripts/`)

```
scripts/
├── install.sh          # One-line installer (Day 30) — works
├── train_lora.py       # BROKEN: imports code4u.ai_engine.training.trainer (wrong path)
└── start_inference.sh  # vLLM server startup — works
```

---

## Quick Reference

| What | Where |
|------|-------|
| CLI (local, no server) | `backend/src/code4u/cli/main.py` |
| CLI (HTTP client) | `cli/src/code4u_cli/` |
| FastAPI app | `backend/src/code4u/interfaces/api/app.py` |
| Day 1-30 agents | `backend/src/code4u/agents/` |
| Day 1-30 core modules | `backend/src/code4u/core/` |
| Original platform core | `backend/src/code4u/platform_core/` |
| LLM adapters & routing | `backend/src/code4u/ai_engine/llm/` |
| Symbol indexer & DependencyMap | `backend/src/code4u/code_intelligence/knowledge_graph/symbol_indexer.py` |
| Knowledge graph | `backend/src/code4u/code_intelligence/knowledge_graph/graph.py` |
| Tests (~1,360 total) | `backend/tests/` |
| Docker/K8s | `infrastructure/` |
| Frontend workspace | `frontends/workspace/` |

---

**When to update this doc:** Add, remove, or rename any top-level folder; add or remove a backend domain folder; change layout of frontends, cli, infrastructure, or scripts.
