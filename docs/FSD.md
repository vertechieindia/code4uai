# code4u.ai — Functional Specification Document (FSD)

**Version:** 1.2  
**Last updated:** 2026-03-03 (Day 21 — Sovereign Launch)  
**Status:** Living document  
**Companion:** [BRD.md](./BRD.md) (Business Requirements)

> **Status (2026-03-03, Day 21):** The platform now has 22 specialist agents, 42 API routes, 1,360+ tests, 18 frontend pages with real JWT authentication. Login/Signup ARE real (JWT-based with `AuthManager`). The web workspace runs on port 3000. Day 13-21 added: Air-Gapped Mode, System Doctor, Onboarding Tour, Compliance Export, Recursive Quality Gauntlet (Titan Phase), SBOM Generator, NVD Watch, Hotspot Analyzer, Chaos/Adversarial/Red Team agents, Collective Intelligence (Wisdom Nuggets), License Compliance Agent, Toxic Snippet Scanner, Provenance Tracker, Redis Cache, Partitioned Vector Store, Launch Command Center. See [STATUS.md](./STATUS.md) for full details.

---

## 1. Introduction

This document specifies **functional requirements** for code4u.ai: features, user flows, APIs, data, and acceptance criteria. It aligns with the seven-layer architecture and current implementation status ([STATUS.md](./STATUS.md)).

### 1.1 Document purpose

- Define **what** the system must do (features and behaviors).
- Provide **acceptance criteria** for development and QA.
- Serve as reference for API contracts, UI behavior, and integration points.

### 1.2 Layers (reference)

```
Layer 7: UX / Trust          — Diffs, impact summaries, ownership alerts, rollback
Layer 6: Change Application — Transactional diffs, partial accept, audit trail
Layer 5: Multi-Agent        — Planner, Contract, Frontend, Backend, Verifier
Layer 4: LLM Orchestration  — Prompts, schema enforcement, routing
Layer 3: Context Selection  — Symbol, dependency, ownership, blast radius
Layer 2: Code Knowledge Graph — Nodes, relationships, index, query
Layer 1: IDE / Editor       — API, CLI, Web workspace, VS Code, JetBrains
```

---

## 2. Layer 1 — IDE / Editor & Access

### 2.1 Refactor API

**Description:** REST API to trigger refactor or rename by intent and file path.

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/refactor` | Generic refactor by intent + filePath + workspacePath |
| POST | `/api/v1/refactor/rename` | Rename symbol: oldName, newName, filePath, workspacePath |

**Request (refactor):**

- `intent` (string, required): e.g. "Rename create_user to create_user_v2"
- `filePath` (string, required): primary file (absolute or relative to workspace)
- `workspacePath` (string, optional): repo root; default "."
- `selection` (optional): reserved
- `context` (optional): reserved

**Request (rename):**

- `oldName` (string, required)
- `newName` (string, required)
- `filePath` (string, required)
- `workspacePath` (string, optional)

**Response (success):**

- `success`: true
- `affectedFiles`: list of file paths (from plan)
- `breakingChange`: boolean (from plan metadata has_cross_owner or equivalent)
- `analysis`, `transactionId`: optional / future

**Behavior:**

1. Validate required fields; return 400 on failure.
2. Call `ContextCompiler.compile_refactor_blast_context(intent, primary_file_path, workspace_path)`.
3. Build `ExecutionPlan` via `plan_from_blast_context(blast_context)`.
4. Run `PlanExecutor.run(plan, blast_context)` (GENERATE_CODE → VALIDATE_CODE → PREVIEW_DIFF → APPLY_DIFF).
5. On success: return 200 with affectedFiles and metadata.
6. On exception: return 500; PipelineIncompleteError returns body with code `PIPELINE_INCOMPLETE`.

**Acceptance criteria:**

- [ ] Missing intent or filePath returns 400.
- [ ] Invalid or unreadable primary file leads to compile failure and 500.
- [ ] Symbol not found or ambiguous leads to clear error (e.g. SymbolNotFoundError).
- [ ] Full pipeline runs when LLM is available; response includes affectedFiles.
- [ ] Apply phase writes files; on write failure, rollback runs and error is re-raised.

**Implementation reference:** `backend/src/code4u/interfaces/api/routes/refactor.py`

---

### 2.2 CLI

**Description:** Terminal client to invoke refactor (and other operations) against backend API.

**Commands (refactor):**

- `refactor run <intent> --file <path>` — calls POST /api/v1/refactor
- `refactor rename <old_name> <new_name> --file <path>` — calls POST /api/v1/refactor/rename

**Configuration:**

- Server URL: env `CODE4U_SERVER_URL` or default (e.g. http://localhost:8002).
- API key / tenant: env `CODE4U_API_KEY`, `CODE4U_TENANT_ID` (optional).

**Acceptance criteria:**

- [ ] Refactor run sends intent and file path to backend; displays result or error.
- [ ] Refactor rename sends oldName, newName, filePath; displays result or error.
- [ ] Configurable base URL; documented for typical backend port (e.g. 8000).

**Implementation reference:** `cli/src/code4u_cli/commands/refactor.py`, `client.py`

---

### 2.3 Web workspace

**Description:** React app with pages for Dashboard, Refactor, Agent, Connect Repo, etc.

**Refactor page (current):**

- **Current state:** Mock only (setTimeout, fake refactored code); does not call backend.
- **Required state:** User enters or pastes file path (or selects from connected repo), intent or old/new name; submits to POST /api/v1/refactor or /refactor/rename; displays loading; on success shows affected files and optional diff summary; on error shows message.

**Acceptance criteria:**

- [ ] Refactor page calls backend refactor or rename API with workspace path context.
- [ ] Loading and error states are shown.
- [ ] Success shows affected files; future: diff preview panel.

**Implementation reference:** `frontends/workspace/src/pages/RefactorPage.tsx`

---

### 2.4 VS Code extension

**Description:** Extension that activates client, status bar, chat view, inline completion; connects to configurable server URL.

**Acceptance criteria:**

- [ ] Activates and connects to backend (e.g. /health); status reflects connection.
- [ ] Refactor/rename can be triggered from editor (command or context); calls API with current file and workspace.
- [ ] No mock refactor responses; all refactor flows use backend.

**Implementation reference:** `frontends/vscode-extension/src/extension.ts`

---

### 2.5 JetBrains plugin

**Description:** Kotlin-based plugin with structure for actions, client, completion, settings.

**Acceptance criteria:**

- [ ] Structure supports refactor trigger and API client; feature parity with VS Code refactor flow (when implemented).

**Implementation reference:** `frontends/jetbrains-plugin/`

---

## 3. Layer 2 — Code Knowledge Graph

### 3.1 Graph model

**Entities:** Repository, Package, Module, Symbol; Team, Service, Endpoint, Schema.  
**Relationships:** owns, contains, declares, imports, exposes, uses, consumes, federates.

**API (tenant-scoped):**

- Index directory (or repo path).
- Query graph (nodes, relationships, filters).
- Impact analysis (given node or file).

**Acceptance criteria:**

- [ ] Graph API accepts index and query requests; returns structured nodes/relationships.
- [ ] Tenant ID is required and enforced; no cross-tenant data.

**Implementation reference:** `backend/src/code4u/code_intelligence/knowledge_graph/`, `interfaces/api/routes/graph.py`

---

### 3.2 Indexing pipeline (future)

- Wire CodeIndexer to real filesystem/git; parse CODEOWNERS.
- Run on repo connect or webhook; support depth limits.

---

## 4. Layer 3 — Context Selection

### 4.1 Context compiler

**Description:** Builds RefactorBlastContext from intent, primary file path, and workspace path.

**Flow:**

1. Resolve primary file path (absolute) relative to workspace.
2. Read file content; detect language.
3. Resolve symbol name from intent (e.g. “Rename X to Y” → X).
4. `resolve_symbol(file_path, symbol_name, language)` → ResolvedSymbol (or SymbolNotFoundError / AmbiguousSymbolError).
5. `get_direct_dependencies(resolved_symbol, workspace_path)` → list of dependent file paths (sorted).
6. Build affected_rel (defining first, then dependents); `resolve_ownership(affected_rel, workspace_path)`.
7. Map to absolute paths; `assemble_refactor_context(resolved_symbol, dependents_abs, ownership_abs)` → RefactorBlastContext.

**Acceptance criteria:**

- [ ] Invalid or missing primary file raises.
- [ ] Unresolvable or ambiguous symbol raises with clear type.
- [ ] RefactorBlastContext.affected_files are absolute; ownership present for each file; is_complete True.

**Implementation reference:** `backend/src/code4u/code_intelligence/context/compiler.py` — `compile_refactor_blast_context`

---

### 4.2 Planner

**Description:** Produces deterministic ExecutionPlan from RefactorBlastContext.

**Output:**

- Steps: GENERATE_CODE, VALIDATE_CODE, PREVIEW_DIFF, APPLY_DIFF (fixed order).
- Each step: step_id, kind, files (same affected_files for all).
- Metadata: file_count, has_cross_owner.

**Acceptance criteria:**

- [ ] plan_from_blast_context(context) returns plan with exactly four steps in order.
- [ ] plan.affected_files matches context.affected_files; metadata consistent.

**Implementation reference:** `backend/src/code4u/code_intelligence/context/planner.py`

---

## 5. Layer 4 — LLM Orchestration

### 5.1 Executor

**Description:** Calls LLM with file content and instruction; returns raw generated content.

**Interface:** `execute_refactor_simple(file_content: str, instruction: str) -> str`

**Behavior:**

- Build messages (system + user with instruction and file content).
- Call LLM client (e.g. vLLM); return response content.
- Raise on failure (no silent fallback unless designed).

**Acceptance criteria:**

- [ ] Valid request returns non-empty string.
- [ ] Timeout or API failure raises; no fake success.

**Implementation reference:** `backend/src/code4u/ai_engine/llm/executor.py`

---

### 5.2 Client and routing

- **Client:** Configured base URL (vLLM); generate(request) returns content, usage, latency.
- **Routing:** Complexity-based and fallback logic (e.g. self-hosted first; premium fallback after retries); tenant air-gapped → self-hosted only.

**Acceptance criteria (future):**

- [ ] vLLM endpoint configurable; routing respects tenant and retry policy.

---

## 6. Layer 5 — Multi-Agent & Plan Execution

### 6.1 Plan execution state machine

**States:** INIT → PLAN_READY → CODE_GENERATED → CODE_VALIDATED → DIFF_PREVIEWED → APPLIED | FAILED.

**Rules:**

- Only transitions in ALLOWED_PLAN_TRANSITIONS are valid.
- PlanExecutor.run(plan, context) transitions in order; on any exception → FAILED and re-raise.

**Acceptance criteria:**

- [ ] Invalid transition raises PlanStateViolation.
- [ ] No step is skipped; APPLIED only after all four steps succeed.

**Implementation reference:** `backend/src/code4u/platform_core/state_machine/plan_states.py`

---

### 6.2 PlanExecutor handlers

**GENERATE_CODE:**

- For each file in step.files: read from disk; call LLM with context; store in _generated_code.
- Missing file or LLM failure → raise.

**VALIDATE_CODE:**

- For each file: ensure in _generated_code; Python → ast.parse; JS/TS → balanced braces (or equivalent).
- First validation failure → raise.

**PREVIEW_DIFF:**

- For each file: read original from disk; get generated from _generated_code; produce unified diff (difflib); store in _diffs.
- Missing generated or read error → raise. Unchanged file still gets diff (headers only).

**APPLY_DIFF:**

- Assert _generated_code and _diffs non-empty; each step.files in both.
- Backup: read all originals into _original_code.
- Apply: write _generated_code to each file (UTF-8).
- On any write failure: rollback (write _original_code back); re-raise.
- On success: clear _original_code.

**Acceptance criteria:**

- [ ] Generate stores one entry per file; validate rejects invalid syntax.
- [ ] Preview produces one diff per file; apply writes only in APPLY_DIFF.
- [ ] Rollback restores all backed-up files; rollback failure raises and does not swallow apply error.

**Implementation reference:** `backend/src/code4u/platform_core/agents/orchestrator.py` — PlanExecutor

---

## 7. Layer 6 — Change Application

### 7.1 Apply and rollback (PlanExecutor)

- **Backup:** All affected files read and stored before any write.
- **Apply:** Sequential write of generated content; UTF-8.
- **Rollback:** On first write failure, restore every file from backup; then re-raise original error.

**Acceptance criteria:**

- [ ] No partial apply: either all files updated or all restored.
- [ ] Rollback restores exact original content (byte-for-byte where applicable).

---

### 7.2 Diff engine (transaction manager)

**Description:** In-memory DiffTransaction with FileDiff list; create, add_diff, apply, rollback.

**Acceptance criteria:**

- [ ] add_diff appends FileDiff (path, original, new, unified_diff, status).
- [ ] apply writes new_content to each file; rollback writes original_content; errors reported.

**Implementation reference:** `backend/src/code4u/change_execution/diff_engine/transaction.py`

**Future:** Persistence; partial accept/reject per hunk; signed diffs; IDE protocol using same API.

---

## 8. Layer 7 — UX / Trust

### 8.1 Diff preview (required for trust)

**Description:** User must see a diff before apply. Backend already produces _diffs in PlanExecutor; apply happens in same request today.

**Future UI:**

- Side-by-side or inline diff per file.
- Accept / Reject per file or per hunk.
- Call to apply only after user accepts (or keep current “apply in same request” and add optional preview-only mode).

**Acceptance criteria:**

- [ ] Workspace or IDE can show per-file diffs (from API or from executor._diffs if exposed).
- [ ] No silent apply without user-facing preview capability.

---

### 8.2 Change summary and ownership

- **Change summary:** Intent, affected files, breaking-change/cross-owner warning.
- **Ownership:** Show “Owned by @team-x” when file is in plan; optional approval flow for cross-owner.

**Acceptance criteria (future):**

- [ ] Refactor response or dedicated endpoint exposes affected files and has_cross_owner (or equivalent).
- [ ] UI can display ownership from plan or context.

---

### 8.3 Rollback control

- **Backend:** Rollback is automatic on apply failure. Optional: explicit “rollback last transaction” API using stored backup or transaction id.
- **UI:** One-click “Revert last change” when supported by API.

---

## 9. Security & Compliance (Functional)

### 9.1 No-AI zones

**Description:** Before refactor (or any LLM edit), check file paths and optionally content against No-AI zone patterns (auth, payment, crypto, compliance, secrets). If match → reject and log.

**Acceptance criteria:**

- [ ] Refactor route (or PlanExecutor entry) calls No-AI check; on violation returns 403 or 400 and logs event.
- [ ] No LLM call for files in No-AI zone.

**Implementation reference:** `backend/src/code4u/security_compliance/security/no_ai_zones.py`

---

### 9.2 Tenant and RBAC

- **Tenant:** Every request must have tenant context; graph and data scoped by tenant.
- **RBAC:** Permissions (e.g. refactor, modify_public_api, approve_breaking_change) checked per intent; role hierarchy (viewer → developer → … → admin).

**Acceptance criteria (future):**

- [ ] Missing or invalid tenant → 401/403.
- [ ] Intent not allowed for user role → 403.

---

### 9.3 Audit

- **Events:** Refactor request, plan created, code generated, validated, diff previewed, applied, failed, rollback.
- **Content:** No raw prompts/responses in logs; hashes or ids only where required.
- **Persistence (future):** Durable store; immutable; signature.

**Acceptance criteria (future):**

- [ ] Every refactor run produces audit events; persistence and retrieval documented.

---

## 10. Integrations

### 10.1 Jira / Slack / RIL

- **Current:** Stubs and structure; Jira/Slack have some client and handler code. RIL: ingestion (Slack, Teams, Zoom), intelligence, orchestrator, STT.
- **Future:** OAuth per integration; webhooks; RIL end-to-end (capture → transcript → requirements → plan).

**Acceptance criteria (future):**

- [ ] OAuth flow for at least one integration; webhook receives and processes events.
- [ ] RIL pipeline runnable with real Slack/Teams/Zoom input.

---

## 11. Non-Functional Requirements

### 11.1 Performance (targets)

| Metric | Target |
|--------|--------|
| Context retrieval | &lt; 200 ms P99 |
| LLM response (simple refactor) | &lt; 5 s P99 |
| Diff generation | &lt; 500 ms P99 |
| Knowledge graph query | &lt; 50 ms P99 |

### 11.2 Availability and scalability

- API availability ≥ 99.95%.
- Support 10,000+ concurrent users per cluster; 100k+ refactors/month (roadmap).

### 11.3 Security

- TLS 1.3 in transit; encryption at rest (AES-256) for stored data.
- mTLS between services (roadmap); OAuth 2.0 / OIDC for user auth (roadmap).
- No raw prompts/responses in logs; redacted audit.

### 11.4 Determinism and correctness

- Same intent + same context → same plan and validation outcome.
- LLM output may vary; validation and diff apply are deterministic.
- No silent writes; no partial apply without explicit design.

---

## 12. Data and API Contracts (Summary)

### 12.1 Refactor request/response

- **Request:** intent, filePath, workspacePath (and for rename: oldName, newName).
- **Response:** success, affectedFiles[], breakingChange, analysis, transactionId (optional).

### 12.2 RefactorBlastContext (internal)

- symbol: ResolvedSymbol
- defining_file: str
- affected_files: tuple of str (absolute paths)
- ownership: dict path → list of owners
- blast_radius: file_count, has_cross_owner
- is_complete: True

### 12.3 ExecutionPlan (internal)

- steps: (GENERATE_CODE, VALIDATE_CODE, PREVIEW_DIFF, APPLY_DIFF)
- affected_files: tuple of str
- metadata: file_count, has_cross_owner

---

## 13. Acceptance Criteria Checklist (High Level)

- [ ] **E2E refactor:** API refactor/rename → compile → plan → execute → apply; files updated; response has affectedFiles.
- [ ] **Rollback:** Forced write failure → all files restored; error returned.
- [ ] **Validation:** Invalid Python/JS in generated code → VALIDATE_CODE fails; no apply.
- [ ] **No silent apply:** Apply only in APPLY_DIFF step; backup before write.
- [ ] **Workspace refactor:** Refactor page calls backend; no mock.
- [ ] **CLI:** Refactor commands call API; configurable URL.
- [ ] **No-AI (when enforced):** Request touching No-AI path rejected and logged.
- [ ] **Audit (when persisted):** Refactor runs produce persistent audit events.

---

## 14. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-31 | — | Initial FSD; aligned with BRD, ARCHITECTURE, STATUS. |

---

*Related: [BRD.md](./BRD.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [STATUS.md](./STATUS.md), [COMPLIANCE.md](./COMPLIANCE.md).*
