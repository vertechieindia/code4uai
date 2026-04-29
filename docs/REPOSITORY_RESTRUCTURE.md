# code4u.ai — Repository Restructure Deliverable

**Date:** 2026-02-07  
**Scope:** Structure and naming only. Zero behavior change. All imports updated.

> **Update (2026-03-03, Day 21):** Since the January audit, Days 13-21 added significant new backend domains: `backend/src/code4u/knowledge/` (pattern_extractor.py, provenance_tracker.py), `backend/src/code4u/validation/` (gauntlet_orchestrator.py), `backend/src/code4u/analytics/` (hotspot_analyzer.py), `backend/src/code4u/agents/quality_swarm/` (4 agents), new agents (chaos_agent.py, adversarial_agent.py, red_team_agent.py, predictor_agent.py, wisdom_agent.py, legal_agent.py), new security modules (toxic_scanner.py, adversarial_agent.py, sbom_generator.py, fortress_swarm.py), new core modules (cache.py, collaboration.py), 14 new API route files, 2 new frontend pages (GuardianPage, OrgDashboard), and significant updates to DashboardPage, AgentPage, SettingsPage, and IntegrationsPage. Frontend now runs on port 3000. See [FILE_STRUCTURE.md](./FILE_STRUCTURE.md) for the current layout.
>
> **Audit Note (2026-01-31):** Since this restructure, the Day 1-30 development sprint added significant new code in `backend/src/code4u/agents/` (12 specialist agents), `backend/src/code4u/core/` (14 new modules beyond config/logging), `backend/src/code4u/models/` (analytics), `backend/src/code4u/interfaces/cli/` (TUI dashboard), and `scripts/install.sh`. The folder tree below does not reflect these additions. See [FILE_STRUCTURE.md](./FILE_STRUCTURE.md) for the current layout. Also: `jetbrains-plugin/` and `mobile-app/` listed below may not exist on disk.

---

## 1. High-Level Summary

The repository was reorganized so that:

- **Architecture layers are visible in folder structure** — platform_core, ai_engine, code_intelligence, change_execution, security_compliance, requirements_intelligence, interfaces.
- **Ownership boundaries are obvious** — Each domain has a single top-level folder under `backend/src/code4u/`; “Where does refactoring logic live?” → platform_core + change_execution; “Where is LLM routing?” → ai_engine; “Where are safety rules enforced?” → security_compliance.
- **Naming is consistent** — snake_case for Python; explicit folder and file names; no ambiguous `core`, `utils`, or bare `manager`/`handler`/`engine` at domain level.
- **Top-level is clear** — `backend`, `frontends`, `cli`, `docs`, `infrastructure`, `scripts` with READMEs explaining purpose and boundaries.

Refactoring logic lives in **platform_core** (state machine, agents, protocol) and **change_execution** (diff engine). LLM routing lives in **ai_engine**. Safety rules (RBAC, audit, no-AI zones) live in **security_compliance**.

---

## 2. What Was Wrong

| Issue | Detail |
|-------|--------|
| **Flat domain layout** | All backend domains (state_machine, llm, security, api, …) sat side-by-side under `code4u/`. No grouping by architectural layer. |
| **Ambiguous names** | `core` could mean “platform core” or “shared config”; `protocol` and `api` both “interfaces” but not grouped. |
| **No mental-model mapping** | New hires could not quickly map “deterministic execution” or “LLM orchestration” to folders. |
| **Top-level ambiguity** | `infra` abbreviated; `frontend` mixed apps (dashboard, workspace, admin) with no umbrella. |
| **Weak boundaries** | No READMEs stating what belongs in each area or how layers interact. |

---

## 3. What Was Improved

- **Domain hierarchy under `code4u/`**  
  Six domain groups + shared `core` + `interfaces`: platform_core, ai_engine, code_intelligence, change_execution, security_compliance, requirements_intelligence, interfaces. Each contains only modules that belong to that layer.

- **Predictable locations**  
  - Deterministic execution / state / rules → `code4u.platform_core.*`  
  - LLM / routing / prompts / training → `code4u.ai_engine.*`  
  - Knowledge graph / context / knowledge → `code4u.code_intelligence.*`  
  - Diffs / transactions / validation → `code4u.change_execution.*`  
  - RBAC / audit / isolation / billing / compliance → `code4u.security_compliance.*`  
  - RIL pipeline → `code4u.requirements_intelligence.ril`  
  - HTTP API / integrations / MCP → `code4u.interfaces.*`  
  - Config / logging → `code4u.core`

- **Top-level clarity**  
  - `infra` → `infrastructure` (full word).  
  - `frontend` → `frontends` (plural, multiple apps).  
  - README added to backend, frontends, cli, docs, infrastructure, scripts and to each domain folder under `code4u/`.

- **Naming**  
  - All new folders use snake_case (platform_core, ai_engine, etc.).  
  - No new generic names (no new “core”, “utils”, “misc”).  
  - Existing file names retained except where a README or convention doc explicitly called out renames; no silent semantic renames.

- **Documentation**  
  - Each major folder has a short README: purpose, responsibilities, what belongs / what does not, how it interacts with other layers.

---

## 4. Final Folder Tree

```
code4u.ai/
├── backend/
│   ├── README.md
│   ├── pyproject.toml
│   ├── poetry.lock
│   └── src/
│       └── code4u/
│           ├── __init__.py
│           ├── core/                          # Shared: config, logging
│           │   ├── README.md
│           │   ├── __init__.py
│           │   ├── config.py
│           │   └── logging.py
│           ├── platform_core/                 # State machine, rules, agents, protocol
│           │   ├── README.md
│           │   ├── __init__.py
│           │   ├── state_machine/
│           │   ├── rules_engine/
│           │   ├── agents/
│           │   ├── protocol/
│           │   ├── agent_manager/
│           │   └── browser_agent/
│           ├── ai_engine/                    # LLM, routing, compiler, training
│           │   ├── README.md
│           │   ├── __init__.py
│           │   ├── llm/
│           │   ├── routing/
│           │   ├── model_picker/
│           │   ├── compiler/
│           │   ├── training/
│           │   ├── evaluation/
│           │   ├── autocomplete/
│           │   └── supercomplete/
│           ├── code_intelligence/            # Knowledge graph, context, knowledge
│           │   ├── README.md
│           │   ├── __init__.py
│           │   ├── knowledge_graph/
│           │   ├── context/
│           │   └── knowledge/
│           ├── change_execution/             # Diff engine, validation
│           │   ├── README.md
│           │   ├── __init__.py
│           │   ├── diff_engine/
│           │   └── validation/
│           ├── security_compliance/           # Security, compliance, billing
│           │   ├── README.md
│           │   ├── __init__.py
│           │   ├── security/
│           │   ├── compliance/
│           │   └── billing/
│           ├── requirements_intelligence/    # RIL pipeline
│           │   ├── README.md
│           │   ├── __init__.py
│           │   └── ril/
│           └── interfaces/                    # API, integrations, MCP
│               ├── README.md
│               ├── __init__.py
│               ├── api/
│               ├── integrations/
│               └── mcp_marketplace/
├── frontends/
│   ├── README.md
│   ├── admin-dashboard/
│   ├── dashboard/
│   ├── workspace/
│   ├── web-agent-manager/
│   ├── vscode-extension/
│   ├── jetbrains-plugin/
│   ├── mobile-app/
│   └── packages/
│       └── knowledge-graph/
├── cli/
│   ├── README.md
│   └── src/code4u_cli/
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── COMPLIANCE.md
│   ├── STATUS.md
│   ├── TECHNICAL_MOAT.md
│   └── REPOSITORY_RESTRUCTURE.md
├── infrastructure/
│   ├── README.md
│   ├── docker/
│   └── kubernetes/
├── scripts/
│   ├── README.md
│   ├── start_inference.sh
│   └── train_lora.py
├── README.md
├── package.json
├── pnpm-workspace.yaml
├── turbo.json
└── tsconfig.base.json
```

---

## 5. Rename / Move Log

| Old path | New path | Justification |
|----------|----------|---------------|
| `backend/src/code4u/state_machine/` | `backend/src/code4u/platform_core/state_machine/` | Deterministic execution; belongs in platform_core. |
| `backend/src/code4u/rules_engine/` | `backend/src/code4u/platform_core/rules_engine/` | Rules and constraints for execution; platform_core. |
| `backend/src/code4u/agents/` | `backend/src/code4u/platform_core/agents/` | Execution agents (planner, verifier, orchestrator); platform_core. |
| `backend/src/code4u/protocol/` | `backend/src/code4u/platform_core/protocol/` | IDE protocol and execution flow; platform_core. |
| `backend/src/code4u/agent_manager/` | `backend/src/code4u/platform_core/agent_manager/` | Agent session/task management; platform_core. |
| `backend/src/code4u/browser_agent/` | `backend/src/code4u/platform_core/browser_agent/` | Browser automation agent; platform_core. |
| `backend/src/code4u/llm/` | `backend/src/code4u/ai_engine/llm/` | LLM client, router, prompts; ai_engine. |
| `backend/src/code4u/routing/` | `backend/src/code4u/ai_engine/routing/` | Model routing and cost; ai_engine. |
| `backend/src/code4u/model_picker/` | `backend/src/code4u/ai_engine/model_picker/` | Model selection; ai_engine. |
| `backend/src/code4u/compiler/` | `backend/src/code4u/ai_engine/compiler/` | Prompt/constraint compilation; ai_engine. |
| `backend/src/code4u/training/` | `backend/src/code4u/ai_engine/training/` | LoRA/training; ai_engine. |
| `backend/src/code4u/evaluation/` | `backend/src/code4u/ai_engine/evaluation/` | LLM evaluation; ai_engine. |
| `backend/src/code4u/autocomplete/` | `backend/src/code4u/ai_engine/autocomplete/` | Autocomplete engine; ai_engine. |
| `backend/src/code4u/supercomplete/` | `backend/src/code4u/ai_engine/supercomplete/` | Supercomplete engine; ai_engine. |
| `backend/src/code4u/knowledge_graph/` | `backend/src/code4u/code_intelligence/knowledge_graph/` | Code KG; code_intelligence. |
| `backend/src/code4u/context/` | `backend/src/code4u/code_intelligence/context/` | Context compiler/planner; code_intelligence. |
| `backend/src/code4u/knowledge/` | `backend/src/code4u/code_intelligence/knowledge/` | Knowledge store/memories; code_intelligence. |
| `backend/src/code4u/diff_engine/` | `backend/src/code4u/change_execution/diff_engine/` | Diffs and transactions; change_execution. |
| `backend/src/code4u/validation/` | `backend/src/code4u/change_execution/validation/` | Diff/AST validation; change_execution. |
| `backend/src/code4u/security/` | `backend/src/code4u/security_compliance/security/` | RBAC, audit, isolation, no-AI; security_compliance. |
| `backend/src/code4u/compliance/` | `backend/src/code4u/security_compliance/compliance/` | Compliance controls; security_compliance. |
| `backend/src/code4u/billing/` | `backend/src/code4u/security_compliance/billing/` | Metering and billing; security_compliance. |
| `backend/src/code4u/ril/` | `backend/src/code4u/requirements_intelligence/ril/` | RIL pipeline; requirements_intelligence. |
| `backend/src/code4u/api/` | `backend/src/code4u/interfaces/api/` | HTTP API; interfaces. |
| `backend/src/code4u/integrations/` | `backend/src/code4u/interfaces/integrations/` | External adapters; interfaces. |
| `backend/src/code4u/mcp_marketplace/` | `backend/src/code4u/interfaces/mcp_marketplace/` | MCP; interfaces. |
| `infra/` | `infrastructure/` | Full word; no abbreviation. |
| `frontend/` | `frontends/` | Plural; multiple frontend apps. |

---

## 6. Open Questions / Risks

1. **pnpm lockfile** — After renaming `frontend` → `frontends`, run `pnpm install` at repo root to refresh lockfile and workspace links. `package.json` and `pnpm-workspace.yaml` have been updated to `frontends/*` and `frontends/packages/*`.
2. **CI / Docker / K8s** — Paths in docs and Dockerfile updated to `infrastructure/` and entrypoint `code4u.interfaces.api.app:app`. Any external CI or deploy scripts that reference `frontend/` or `infra/` must be updated manually.
3. **Backend entrypoint** — All run commands and Docker CMD use `code4u.interfaces.api.app:app`. README and docs updated.
4. **Poetry scripts** — `[tool.poetry.scripts] code4u = "code4u.cli:main"` — backend has no `code4u.cli`; left as-is. Remove or point to separate `cli` package if desired.
5. **File renames** — No `manager.py` → `agent_session_manager.py` (or similar) renames were applied in this pass to avoid scope creep. Recommend a follow-up pass to qualify ambiguous filenames per the naming rules.

---

## 7. Success Criteria (Checklist)

- [ ] New hire can answer “Where does refactoring logic live?” without searching → **platform_core + change_execution**
- [ ] New hire can answer “Where is LLM routing?” without searching → **ai_engine**
- [ ] New hire can answer “Where are safety rules enforced?” without searching → **security_compliance**
- [ ] Repository feels predictable and professional; boundaries and READMEs in place.
- [ ] All tests pass (when present); app starts; no dead or circular imports.
