# code4u.ai — Frontend Status

**Last updated:** 2026-03-03 (Day 21 — Sovereign Launch complete — includes all Day 13-21 UI updates)

---

## Quick Overview

| Metric | Value |
|--------|-------|
| Total pages/views | 21 (across 2 apps) — includes GuardianPage + OrgDashboard |
| Fully working (real backend API) | **8** — Dashboard, Projects, ConnectRepo, AgentPage, RefactorPage, IDE, Login, Signup |
| Fully working (local state, no backend needed) | **1** — Settings |
| Working UI with mock data | **6** |
| Static / stub pages | **3** (GitLab/Bitbucket providers) |
| Authentication system | **Real** — JWT via `POST /api/v1/auth/login` + `AuthContext` + route guards |
| Code editor | **Monaco Editor** with syntax highlighting, save, multi-tab, glyph margin |
| Knowledge Graph | **Live** — Hot Spots panel in IDE, symbol indexing per project |
| Self-Healing | **Active** — PlanExecutor auto-heals validation failures (max 2 attempts) |
| AI Code Review | **Live** — Synthetic PR review with AI Review Notes on RefactorPage |
| Test Runner | **Live** — Run Tests button in IDE with structured output |
| Issues Tab | **Live** — Architectural debt panel in IDE from profiler scans |
| GitHub OAuth | **Live** — OAuth flow with token exchange, repo listing, and clone |
| Remote Cloning | **Live** — Git URL clone + GitHub clone via `GitManager` |
| External Issues | **Live** — Tracker panel in IDE (GitHub Issues, Jira, Linear support) |
| Git Webhooks | **Live** — Push events trigger automatic re-index via `POST /webhooks/git-event` |
| Command Palette | **Live** — `Cmd+K` omnibar for files, symbols, navigation, and actions |
| Theme System | **Live** — Dark / Light / System modes with persistence and glassmorphism |
| Enhanced Chat | **Live** — Markdown + syntax highlighting + collapsible AI thought bubbles |
| Agent Presence | **Live** — WebSocket-based real-time agent location in file tree + editor gutter |
| Page Transitions | **Live** — Framer Motion smooth transitions between all pages |
| Performance Profiler | **Live** — cProfile runner + workspace scanner + hot function list in IDE |
| Complexity Heatmap | **Live** — Treemap view on Projects page with burden scores + hot spots |
| /optimize Intent | **Live** — Chat command + orchestrator routing for performance anti-patterns |
| Semantic Search | **Live** — TF-IDF concept search in IDE Performance panel |
| Workspace Scanner | **Live** — Bulk performance smell detection across all project files |
| Go Symbol Indexer | **Live** — structs, interfaces, methods, constants, imports for .go files |
| Java Symbol Indexer | **Live** — classes, interfaces, enums, methods, imports for .java files |
| Enhanced TS Parser | **Live** — React components, hooks, namespaces, and improved pattern coverage |
| Go-to-Definition | **Live** — F12 cross-language symbol lookup in IDE via Knowledge Graph |
| Language Distribution | **Live** — Per-project language bar chart on Projects page |
| Polyglot Linting | **Live** — eslint, go vet, staticcheck, ruff integration via /test/lint |
| Polyglot Test Runner | **Live** — go test, cargo test, gradle, maven alongside pytest/vitest |
| Library Migration | **Live** — /migrate/analyze + /migrate/plan for npm, pip, go, cargo, maven |
| /upgrade-library Intent | **Live** — Chat command + orchestrator routing for dependency upgrades |
| Secret Scanner | **Live** — Regex + Shannon entropy detection for 14 credential patterns |
| SAST Scanner | **Live** — SQLi, XSS, eval, pickle, command injection, CORS patterns |
| SecurityViolationError | **Live** — PlanExecutor blocks code changes containing secrets |
| SCA Vulnerability Scanner | **Live** — OSV.dev + built-in DB for 15 known-vulnerable packages |
| Security Dashboard | **Live** — Dedicated /security page with secrets, CVEs, SAST findings |
| Fleet Security Posture | **Live** — Cross-project security aggregation endpoint |
| Inline Diff Comments | **Live** — Gutter comment UI on RefactorPage unified diff + plan revision via feedback |
| Swarm Feedback Endpoint | **Live** — `POST /swarm/feedback` sends inline comments to Chief Architect for plan revision |
| Agent Debate (Jury) | **Live** — Profiler vs Heal Agent debate UI on AgentPage with per-round voting |
| Approval Gates | **Live** — `RequiresApproval` decorator + `ApprovalGateManager` in RBAC for high-risk refactors |
| Approval Gate API | **Live** — `POST /swarm/approval`, approve/reject endpoints, pending list |
| Notification Bridge | **Live** — Slack/Teams webhook integration with formatted swarm summaries |
| Notification API | **Live** — `POST /notifications/send`, `/swarm-summary`, webhook config endpoints |
| K8s Worker Pool | **Live** — Worker Deployment, HPA, ServiceAccount with security hardening |
| K8s Redis | **Live** — Redis 7 with auth, resource limits, non-root, read-only rootfs |
| K8s Network Policies | **Live** — deny-all default, API/Worker/Redis isolation with DNS + HTTPS egress |
| K8s Namespace | **Live** — Pod Security Standards (restricted) enforced at namespace level |
| /deploy Intent | **Live** — `AgentType.DEPLOY` in Chief Architect + SwarmController routing |
| CI/CD Generator | **Live** — GitHub Actions + GitLab CI pipelines for Python, Go, TS, Rust, Java |
| Dockerfile Generator | **Live** — Multi-stage builds with non-root users for all languages |
| Deploy API | **Live** — `POST /deploy/generate`, `/deploy/dockerfile`, `/deploy/pipelines`, `/deploy/status` |
| Secret Provider | **Live** — `EnvSecretProvider`, `VaultSecretProvider` (mock), `AWSSecretProvider` (mock), chained |
| Telemetry | **Live** — `@track_execution` decorator, token/cost tracking per agent |
| Cost Analytics | **Live** — Dashboard "Cloud Costs" widget with by-agent and by-model breakdowns |
| Ollama/vLLM Models | **Live** — Llama 3.1, CodeLlama 34B, DeepSeek Coder V2, Qwen 2.5 Coder 32B, vLLM in registry |
| MODEL_ROUTING_TABLE | **Live** — Agent-to-model mapping with cloud/local tiers for 14 agent types |
| Complexity Estimator | **Live** — `ChiefArchitect.estimate_complexity()` — low/medium/high with signal patterns |
| Smart Route API | **Live** — `POST /models/smart-route` returns model + complexity for any agent type |
| Air-Gapped Mode | **Live** — Runtime toggle via `POST /airgap/toggle`, blocks external domains |
| Air-Gapped Guard | **Live** — `guard_external_call()` raises on cloud provider access in air-gapped mode |
| Air-Gapped Settings | **Live** — "LLM & Models" tab in SettingsPage with toggle, provider picker, routing table |
| Local Vector Store | **Live** — FAISS/numpy/pure-python fallback with hashed TF-IDF embeddings (256d) |
| Vector Search API | **Live** — `POST /search/vector` for local semantic code search + `/search/vector/stats` |
| System Doctor | **Live** — `GET /health/doctor` pings DB, Redis, LLM, Git, VectorStore, Disk, Air-Gap |
| System Status Tab | **Live** — "System Status" tab in SettingsPage with readiness score + per-probe diagnostics |
| Emergency Kill Switch | **Live** — `POST /swarm/kill-all` cancels all tasks, terminates PIDs, clears events |
| EMERGENCY STOP Button | **Live** — Prominent red button on AgentPage with kill result banner |
| Onboarding Tour | **Live** — 7-step first-run guided overlay: Dashboard → Repo → IDE → Agent → Security → Settings |
| Compliance Export | **Live** — `GET /projects/{id}/export-report` generates Markdown audit report |
| Export Contents | **Live** — Project stats, swarm history, security audit, telemetry, diagnostics, air-gap status |
| Model Distillation | **Live** — `DistillationStore` collects successful executions as JSONL training data |
| Distillation API | **Live** — `GET /distill/stats`, `/distill/examples`, `POST /distill/collect`, `/distill/export` |
| CRDT Collaboration | **Live** — `CollaborationManager` with Lamport-clocked insert/delete/replace/cursor operations |
| Collaboration API | **Live** — `POST /collab/join`, `/collab/op`, `/collab/leave`, `GET /collab/doc`, `/collab/active` |
| Ephemeral Staging | **Live** — `POST /staging/create` generates Vercel, K8s namespace, or Docker Compose previews |
| Staging Lifecycle | **Live** — `GET /staging/environments`, `DELETE /staging/{id}`, `POST /staging/promote` |
| Production Smoke Test | **Live** — `POST /smoke-test` runs 10 checks with SHA-256 audit signature chain |
| Smoke Test Checks | **Live** — Doctor, routing, complexity, swarm plan, telemetry, vector, air-gap, distill, collab, staging |
| Guardian Mission Control | **Live** — 5-stage Gauntlet tracker, Security Posture gauge, Agent Activity Logs, Titan Audit Export |
| Gauntlet Simulation | **Live** — Simulated run with failure/healing/restart cycle, cycle counter, stage timing |
| Worker Vitals | **Live** — Real-time CPU/Memory radial gauges, active agent count, throttle slider (1-16), process table |
| Chaos & Resilience | **Live** — Chaos Mode toggle, intensity slider, injected faults table, resilience score gauge, RTO stats |
| Red Team & Adversarial | **Live** — Run Red Team Scan, Adversarial Hygiene Test buttons with results |
| Governance & Ethics Tab | **Live** — License Compatibility Matrix (4x4), License Violations, AI Provenance & Attribution, Toxic Snippet Scanner |
| Organization Security Heatmap | **Live** — Treemap visualization with security scores, risk distribution, project table |
| Collective Intelligence Tab | **Live** — Recently Shared Fixes, Code Reuse Opportunities, Project Wisdom Scores |
| Churn Risk Hotspots | **Live** — Files ranked by risk score with churn stats, complexity, risk bars |
| Sovereign Launch Summary | **Live** — Intelligence Gain, Safety Perimeter, Legal Purity, Performance cards + Build Journey Timeline (D1-D21) |
| Build Journey Timeline | **Live** — 7-phase visual timeline (Core → Security → Agent → Titan → Predictive → Intelligence → Launch) |
| Telemetry API | **Live** — `GET /telemetry/summary`, `/telemetry/recent`, `/telemetry/cost-breakdown` |

---

## Running Services

| App | URL | What It Is |
|-----|-----|------------|
| **Landing Page** (`frontends/dashboard/`) | `http://localhost:3000` | Public marketing page — hero, features, pricing, compliance. Fetches real data from backend. |
| **Workspace App** (`frontends/workspace/`) | `http://localhost:5173` | Main app — all pages below live here. |
| **Backend API** | `http://localhost:8000` | FastAPI with 34 route files. |
| **Swagger Docs** | `http://localhost:8000/docs` | Interactive API documentation. |

---

## Page-by-Page Status

### Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | **Complete** — fully functional, calls real API or has full local interactivity |
| 🟡 | **Mock** — UI renders but uses hardcoded data or setTimeout simulation |
| 🔴 | **Stub** — exists but has no real content or interactivity |
| 🔧 | **Needs your work** — what to build to make it real |

---

### Landing Page (`http://localhost:3000`)

| Status | Route | File |
|--------|-------|------|
| ✅ Complete | `/` (separate app) | `frontends/dashboard/src/App.tsx` (2,488 lines) |

**What works:**
- Hero section with animated background
- Feature grid (6 capabilities)
- Pricing tiers — fetches real data from `GET /api/v1/billing/tiers`
- Compliance dashboard — fetches real data from `GET /api/v1/compliance/check`
- "Get Started" button → navigates to workspace signup page
- Email capture form
- Tab navigation (Overview / Compliance / Pricing)

**🔧 Needs your work:**
- Email form just shows an `alert()` — needs real email capture API
- Logo at `/logo.png` may be missing (shows broken image)

---

### Login Page (`/login`)

| Status | Route | File |
|--------|-------|------|
| ✅ Complete (Real API) | `/login` | `frontends/workspace/src/pages/LoginPage.tsx` |

**What works:**
- Email + password form with validation
- Show/hide password toggle
- **Real authentication** — calls `POST /api/v1/auth/login` via `useAuth()` hook
- JWT stored in localStorage on success
- Error display for invalid credentials or network errors
- Loading spinner on submit
- Navigates to `/` (dashboard) after successful login
- **Route guard** — redirects to `/` if already logged in
- "← Back to Home" link (top-left) → goes to landing page
- Logo is clickable → goes to landing page
- "Sign up for free" link → goes to `/signup`

**🔧 Needs your work:**
- "Forgot password?" does nothing (needs backend endpoint)
- Social login buttons (GitHub/Google) show "coming soon" message — need OAuth integration
- "Remember me" checkbox not wired to token expiry

---

### Signup Page (`/signup`)

| Status | Route | File |
|--------|-------|------|
| ✅ Complete (Real API) | `/signup` | `frontends/workspace/src/pages/SignupPage.tsx` |

**What works:**
- Name + email + password form
- Password strength indicator (weak/medium/strong with colored bars)
- Show/hide password toggle
- **Real registration** — calls `POST /api/v1/auth/register` via `useAuth()` hook
- JWT stored in localStorage on success, auto-login after register
- Error display for duplicate email or network errors
- Loading spinner on submit
- **Route guard** — redirects to `/` if already logged in
- "← Back to Home" link (top-left) → goes to landing page
- Logo is clickable → goes to landing page
- "Sign in" link → goes to `/login`

**🔧 Needs your work:**
- Social signup buttons (GitHub/Google) show "coming soon" — need OAuth
- Company field not yet wired to signup form (backend supports it)

---

### Dashboard (`/`)

| Status | Route | File |
|--------|-------|------|
| ✅ Complete (Real API) | `/` | `frontends/workspace/src/pages/DashboardPage.tsx` (Day 4 rewrite) |

**What works:**
- **Personalized greeting** — shows `user.name` from AuthContext
- **ROI Analytics cards** — fetches `GET /api/v1/analytics/summary` and displays: Hours Saved, Suggestions Made, Adoption Rate, Active Projects
- **Real project list** — fetches `GET /api/v1/projects` and displays projects with file count, symbol count, languages, and health score
- Clicking a project sets workspace path and opens IDE
- **Recent Activity feed** — fetches `GET /api/v1/analytics/recent` and shows latest review events
- **ROI Summary panel** — shows `humanSummary` (e.g. "Code4u saved 7.7 hours across 4 repositories")
- **Getting Started checklist** — dynamically checks "Create a project" based on real project count
- Quick action buttons (IDE, Connect Repo, Agent, Refactor) — all navigate correctly
- **Auth-protected** — all calls include JWT Bearer token

**🔧 Needs your work:**
- Track getting-started steps in persistent user state
- Agent run history in getting-started (currently static)

---

### Projects Page (`/projects`)

| Status | Route | File |
|--------|-------|------|
| ✅ Complete (Real API) | `/projects` | `frontends/workspace/src/pages/ProjectsPage.tsx` (Day 4 rewrite) |

**What works:**
- **Real project data** — fetches `GET /api/v1/projects` on mount
- Grid and list view toggle
- **Health score rings** — each project displays a 0-100 health score from Sentinel (color-coded: green ≥80, amber ≥50, red <50)
- **Search** — filters projects by name/description in real-time
- File count, symbol count, and language badges per project
- "Last indexed" relative timestamp
- **Re-index button** — calls `POST /api/v1/projects/{id}/index` to trigger fresh Knowledge Graph scan
- **Delete button** — calls `DELETE /api/v1/projects/{id}` with confirmation
- Clicking a project sets workspace path in localStorage and opens IDE
- Empty state with "Create Project" CTA
- **Auth-protected** — all calls include JWT

**🔧 Needs your work:**
- Sort/filter by status, language, or health score
- Batch operations (delete multiple, re-index all)

---

### New Project Page (`/new-project`)

| Status | Route | File |
|--------|-------|------|
| 🟡 Mock | `/new-project` | `frontends/workspace/src/pages/NewProjectPage.tsx` (140 lines) |

**What works:**
- 3 project type cards (Blank, Template, Import Repo)
- Project name input
- Template selection grid (4 templates)
- "Import Repo" navigates to `/connect-repo`

**What's mock:**
- "Create Project" just navigates to `/ide` — no project is actually created
- Template selection doesn't affect anything

**🔧 Needs your work:**
- Build `POST /api/v1/projects` endpoint
- Wire form to create real project
- Pass template selection to project creation

---

### AI Agent Page (`/agent`)

| Status | Route | File |
|--------|-------|------|
| ✅ Complete (Real API) | `/agent` | `frontends/workspace/src/pages/AgentPage.tsx` (Day 3 rewrite) |

**What works:**
- Prompt input with "Start Agent" button — calls **real** `POST /api/v1/swarm/execute`
- **Real task graph** — ChiefArchitect decomposes goal into sub-tasks routed to specialist agents (Vision, Graph, Migration, Heal, Jury, Profiler, etc.)
- **Polling status** — polls `GET /api/v1/swarm/{graph_id}` every 2s for live updates
- Task list with real statuses (pending/running/completed/failed/skipped), agent labels, duration
- Progress bar reflecting real `graph.progress` from backend
- **Sentinel pre-check** — runs `POST /api/v1/sentinel/scan` before execution; shows "Security Blocked" alert if violations found
- **403 handling** — catches forbidden responses for no-ai-zone violations
- Agent status sidebar with real stats (tasks, failures, duration)
- Event log from swarm execution
- Recent runs list from `GET /api/v1/swarm` history
- **Auth-protected** — all calls include JWT Bearer token
- Quick actions: Open in IDE, Refactor Page, Sentinel Rules
- Workspace path input (persists to localStorage, shared with IDE)

**🔧 Needs your work:**
- Streaming events via SSE (currently polling, works but not real-time)
- Pause/resume agent execution (needs backend support)
- Direct link to view generated diffs from swarm output

---

### Refactor Page (`/refactor`)

| Status | Route | File |
|--------|-------|------|
| ✅ Complete (Real API) | `/refactor` | `frontends/workspace/src/pages/RefactorPage.tsx` (Day 3 enhanced) |

**What works:**
- Rename mode: old name, new name, file path, workspace path
- Refactor mode: intent, file path, workspace path
- Calls real backend: `POST /api/v1/refactor/rename/jobs` and `POST /api/v1/refactor/jobs`
- Polls `GET /api/v1/refactor/jobs/{id}` for progress
- Pipeline progress visualization (5 stages: Plan Ready → Code Generated → Code Validated → Diff Previewed → Applied)
- **Monaco DiffEditor** — side-by-side original vs proposed code review
- Unified diff view with syntax-colored additions/removals
- Toggle between Split and Unified diff views
- Error handling with real error messages
- **Auth-protected** — all API calls include JWT Bearer token (Day 3)
- **Sentinel pre-check** — runs `POST /api/v1/sentinel/scan-delta` before execution; shows "Security Blocked by Sentinel" alert if no-ai-zone violation detected (Day 3)
- **Compliance Verified badge** — after successful apply, fetches `GET /api/v1/compliance/audit-status` and displays a green "Compliance Verified" badge with signature (Day 3)
- Workspace path defaults from localStorage (shared with IDE and Agent page)

**🔧 Needs your work:**
- Additional roots input is not yet sent to API
- Could add session support for iterative refinement
- "Apply Changes" button for the preview stage (currently auto-applied)

---

### Connect Repo Page (`/connect-repo`)

| Status | Route | File |
|--------|-------|------|
| ✅ Complete (Real API for Local) | `/connect-repo` | `frontends/workspace/src/pages/ConnectRepoPage.tsx` (Day 4 rewrite) |

**What works:**
- **4 source types:** Local Folder (ready), GitHub, GitLab, Bitbucket
- **Local Folder import** — enter absolute path + optional project name, calls `POST /api/v1/projects` to register and trigger Nexus Indexing
- **Indexing progress** — shows "Nexus Indexing in progress..." during API call, then "Project indexed successfully!" with redirect to IDE
- Error handling for invalid paths
- Git provider repo list (GitHub/GitLab/Bitbucket) — shown with search, stars, visibility badges
- "Coming soon" notice for OAuth providers
- **Auth-protected** — all calls include JWT

**🔧 Needs your work:**
- GitHub/GitLab/Bitbucket OAuth flow (currently shows placeholder repos)
- Real git clone on import for remote repos

---

### Integrations Page (`/integrations`)

| Status | Route | File |
|--------|-------|------|
| 🟡 Mock Data | `/integrations` | `frontends/workspace/src/pages/IntegrationsPage.tsx` (218 lines) |

**What works:**
- Integration cards grid (GitHub, GitLab, Bitbucket, Slack, Discord, Teams, Email, Jira, Linear)
- Category filter tabs (All, IDE, Version Control, Communication, etc.)
- Search input
- "Connected" badge on GitHub and Email
- "Popular" badges

**What's mock:**
- All integrations are hardcoded
- "Connect" buttons do nothing
- Settings (gear) button does nothing
- Search does not filter
- "Request Integration" and "API Docs" links do nothing

**🔧 Needs your work:**
- Wire "Connect" buttons to OAuth flows per provider
- Wire to backend `GET /api/v1/integrations/available` (already exists)
- Make search filter the grid

---

### Docs Page (`/docs`)

| Status | Route | File |
|--------|-------|------|
| 🟡 Mock Data | `/docs` | `frontends/workspace/src/pages/DocsPage.tsx` (156 lines) |

**What works:**
- Quick links grid (Getting Started, API Reference, etc.)
- Documentation sections with article lists
- Search input UI

**What's mock:**
- All sections and articles are hardcoded
- Article links go to `#` — no navigation
- Search does not filter
- Quick link paths are `#`

**🔧 Needs your work:**
- Create real documentation pages or link to external docs
- Wire search

---

### Tutorials Page (`/tutorials`)

| Status | Route | File |
|--------|-------|------|
| 🟡 Mock Data | `/tutorials` | `frontends/workspace/src/pages/TutorialsPage.tsx` (152 lines) |

**What works:**
- Tutorial list with categories and durations
- Featured video section
- Help section with Discord/Email links

**What's mock:**
- Tutorials are hardcoded
- Tutorial buttons do nothing
- Video thumbnail does not play
- Discord link may be invalid

**🔧 Needs your work:**
- Create real tutorial content (videos, guides)
- Wire tutorial cards to actual content pages

---

### Extensions Page (`/extensions`)

| Status | Route | File |
|--------|-------|------|
| 🟡 Static Content | `/extensions` | `frontends/workspace/src/pages/ExtensionsPage.tsx` (117 lines) |

**What works:**
- VS Code extension promo
- Feature list
- "Open Web IDE" button → navigates to `/ide`

**What's mock:**
- Content is static marketing copy
- No real extension download/install

**🔧 Needs your work:**
- Add real VS Code marketplace link when extension is published
- Add download buttons

---

### Settings Page (`/settings`)

| Status | Route | File |
|--------|-------|------|
| ✅ Complete (Local State) | `/settings` | `frontends/workspace/src/App.tsx` (inline) |

**What works:**
- **5 tabs:** Profile, Notifications, API Keys, Security, Appearance
- **Profile tab:** Editable name, email, company, role dropdown. Avatar display. Save button with "✓ Saved" confirmation. Danger Zone with Delete Account button.
- **Notifications tab:** 4 toggle switches (Email, Push, Weekly Digest, Product Updates). All toggles work. Save button.
- **API Keys tab:** List existing keys. "New Key" button opens inline form. Generate key creates a real random key string. "Revoke" button deletes keys.
- **Security tab:** Two-factor authentication toggle. Session timeout dropdown (15m to 24h). Change password form (3 fields). Save button.
- **Appearance tab:** Dark mode toggle (works, persists to localStorage).

**🔧 Needs your work:**
- All state is local (React state only) — nothing persists to backend on save
- Wire Profile save to `PATCH /api/v1/user/profile` (needs backend endpoint)
- Wire API key generation to `POST /api/v1/auth/api-keys` (needs backend endpoint)
- Wire password change to `POST /api/v1/auth/change-password` (needs backend endpoint)
- Wire notification preferences to backend

---

### IDE Page (`/ide`)

| Status | Route | File |
|--------|-------|------|
| ✅ Complete (Real API) | `/ide` | `frontends/workspace/src/IDE.tsx` (Day 2 rewrite) |

**What works:**
- **Monaco Editor** with full syntax highlighting (TypeScript, Python, Go, JSON, CSS, etc.), minimap, bracket colorization, word wrap, Fira Code font
- **Workspace picker** — prompts for an absolute path on first visit, persists to localStorage
- **Live File Explorer** — fetches real directory tree from `GET /api/v1/projects/files`, respects `.gitignore`-style exclusions, auto-expands top-level folders, Refresh button
- **Real file content** — clicking a file fetches content from `GET /api/v1/files/content`, opens in Monaco with correct language mode
- **Multi-tab editing** — open multiple files, dirty indicator (amber dot), close tabs
- **Save** — Cmd/Ctrl+S saves to disk via `POST /api/v1/files/save`, Save button in header with disabled state
- **Real Terminal** — commands execute via `POST /api/v1/terminal/exec` on the backend, real stdout/stderr output, loading spinner while running, `clear` command
- **Real AI Chat** — sends queries to `POST /api/v1/chat/query` with JWT auth, passes workspace path for Knowledge Graph context, shows files-analyzed count, error handling
- **Auth-protected** — all API calls include `Authorization: Bearer` header from Day 1 auth
- **Apply code** — AI code suggestions can be applied to the current editor via "Apply" button
- **Close/Back** — X button returns to dashboard

**Day 4 additions:**
- **Knowledge Graph panel** — toggle via status bar "Graph" button. Shows total files/symbols, "Hot Spots" list of classes/functions sorted by connectivity. Clicking a symbol opens the file in Monaco.
- Fetches from `GET /api/v1/symbols/definitions` with workspace path

**🔧 Needs your work:**
- Run button — needs to be wired to a project-specific run command
- WebSocket-based PTY for interactive terminal (current is request/response)
- Monaco hover provider for symbol documentation (backend endpoint exists)
- Git branch detection (currently hardcoded to "main")

---

### Team Page (`/team`)

| Status | Route | File |
|--------|-------|------|
| 🔴 Stub | `/team` | `frontends/workspace/src/App.tsx` (inline) |

**What works:**
- Shows "Team" heading and 3 hardcoded team members with avatars

**What's mock:**
- Everything is hardcoded
- No invite, remove, or role management

**🔧 Needs your work:**
- Build team management UI (invite by email, role assignment, remove member)
- Wire to backend team/tenant API

---

## App Shell (Header / Navigation)

| Component | Status | Detail |
|-----------|--------|--------|
| Navigation bar | ✅ Working | 5 tabs: Dashboard, Projects, AI Agent, Integrations, Docs |
| Logo link | ✅ Working | Navigates to `/` |
| Dark mode | ✅ Working | Toggle in settings, persists to localStorage |
| Profile avatar | ✅ Working | Click opens dropdown with Profile, API Keys, Security, Billing links + Sign Out |
| Notifications bell | ✅ Working | Opens dropdown, shows unread count, mark all read, dismiss individual |
| Settings gear | ✅ Working | Navigates to `/settings` |
| Search bar | 🔴 Not working | Input exists but no search logic |
| Refresh button | 🟡 Mock | Spins for 1s, refreshes nothing |

---

## Backend API Endpoints — Wiring Status

| Backend Endpoint | Powers | Frontend Page | Status |
|-----------------|--------|---------------|--------|
| ~~`POST /api/v1/auth/login`~~ | ~~Login~~ | ~~LoginPage~~ | ✅ Wired (Day 1) |
| ~~`POST /api/v1/auth/register`~~ | ~~Signup~~ | ~~SignupPage~~ | ✅ Wired (Day 1) |
| ~~`GET /api/v1/projects/files`~~ | ~~File explorer~~ | ~~IDE~~ | ✅ Wired (Day 2) |
| ~~`GET /api/v1/files/content`~~ | ~~File content~~ | ~~IDE~~ | ✅ Wired (Day 2) |
| ~~`POST /api/v1/files/save`~~ | ~~File save~~ | ~~IDE~~ | ✅ Wired (Day 2) |
| ~~`POST /api/v1/terminal/exec`~~ | ~~Terminal~~ | ~~IDE~~ | ✅ Wired (Day 2) |
| ~~`POST /api/v1/chat/query`~~ | ~~AI Chat~~ | ~~IDE~~ | ✅ Wired (Day 2) |
| ~~`POST /api/v1/swarm/plan`~~ | ~~Agent planning~~ | ~~AgentPage~~ | ✅ Wired (Day 3) |
| ~~`POST /api/v1/swarm/execute`~~ | ~~Agent execution~~ | ~~AgentPage~~ | ✅ Wired (Day 3) |
| ~~`GET /api/v1/swarm/{id}`~~ | ~~Agent polling~~ | ~~AgentPage~~ | ✅ Wired (Day 3) |
| ~~`POST /api/v1/sentinel/scan`~~ | ~~Pre-check guardrail~~ | ~~AgentPage~~ | ✅ Wired (Day 3) |
| ~~`POST /api/v1/sentinel/scan-delta`~~ | ~~Pre-check guardrail~~ | ~~RefactorPage~~ | ✅ Wired (Day 3) |
| ~~`GET /api/v1/compliance/audit-status`~~ | ~~Compliance badge~~ | ~~RefactorPage~~ | ✅ Wired (Day 3) |
| ~~`GET /api/v1/analytics/summary`~~ | ~~ROI dashboard~~ | ~~DashboardPage~~ | ✅ Wired (Day 4) |
| ~~`GET /api/v1/analytics/recent`~~ | ~~Recent activity~~ | ~~DashboardPage~~ | ✅ Wired (Day 4) |
| ~~`POST /api/v1/projects`~~ | ~~Project creation~~ | ~~ConnectRepoPage~~ | ✅ Wired (Day 4) |
| ~~`GET /api/v1/projects`~~ | ~~Project listing~~ | ~~DashboardPage, ProjectsPage~~ | ✅ Wired (Day 4) |
| ~~`GET /api/v1/symbols/definitions`~~ | ~~Graph hot spots~~ | ~~IDE~~ | ✅ Wired (Day 4) |
| `GET /api/v1/integrations/available` | Integration listing | IntegrationsPage | Pending |
| `POST /api/v1/nexus/scan` | Multi-repo discovery | ProjectsPage | Pending |
| `POST /api/v1/profiler/ingest` | Performance data | DashboardPage | Pending |
| `GET /api/v1/sentinel/rules` | Architecture rules | SettingsPage | Pending |
| `POST /api/v1/migration/plan` | Code migration | RefactorPage | Pending |

---

## Priority Build Order

| Priority | Task | Status | Pages Affected | Effort |
|----------|------|--------|----------------|--------|
| ~~**P0**~~ | ~~Auth system (login/signup API, tokens, route guards)~~ | ✅ Done (Day 1) | Login, Signup, All | — |
| ~~**P1**~~ | ~~Replace textarea with Monaco in IDE~~ | ✅ Done (Day 2) | IDE | — |
| ~~**P1**~~ | ~~Wire AI chat to `/chat/query`~~ | ✅ Done (Day 2) | IDE | — |
| ~~**P1**~~ | ~~Wire terminal to backend~~ | ✅ Done (Day 2) | IDE | — |
| ~~**P1**~~ | ~~Wire Agent page to Swarm API~~ | ✅ Done (Day 3) | Agent | — |
| ~~**P1**~~ | ~~Sentinel guardrail on Agent + Refactor~~ | ✅ Done (Day 3) | Agent, Refactor | — |
| ~~**P1**~~ | ~~Compliance badge on Refactor~~ | ✅ Done (Day 3) | Refactor | — |
| ~~**P2**~~ | ~~Real project CRUD~~ | ✅ Done (Day 4) | Dashboard, Projects, ConnectRepo | — |
| ~~**P2**~~ | ~~Dashboard ROI analytics~~ | ✅ Done (Day 4) | Dashboard | — |
| ~~**P2**~~ | ~~Knowledge Graph in IDE~~ | ✅ Done (Day 4) | IDE | — |
| ~~**P2**~~ | ~~GitHub OAuth for ConnectRepo~~ | ✅ Done (Day 6) | ConnectRepo | — |
| ~~**P1**~~ | ~~Performance Profiling API + IDE tab~~ | ✅ Done (Day 8) | IDE | — |
| ~~**P1**~~ | ~~Complexity Heatmap treemap view~~ | ✅ Done (Day 8) | Projects | — |
| ~~**P1**~~ | ~~Optimization Intent (/optimize)~~ | ✅ Done (Day 8) | Chat, Agent | — |
| ~~**P1**~~ | ~~Semantic Search (concept-based)~~ | ✅ Done (Day 8) | IDE Perf panel | — |
| ~~**P1**~~ | ~~Workspace performance scanner~~ | ✅ Done (Day 8) | IDE | — |
| ~~**P1**~~ | ~~Go/Java Symbol Indexing~~ | ✅ Done (Day 9) | Backend | — |
| ~~**P1**~~ | ~~Go-to-Definition (cross-language)~~ | ✅ Done (Day 9) | IDE | — |
| ~~**P1**~~ | ~~Language Distribution breakdown~~ | ✅ Done (Day 9) | Projects | — |
| ~~**P1**~~ | ~~Polyglot linting (eslint/go vet)~~ | ✅ Done (Day 9) | Backend | — |
| ~~**P1**~~ | ~~Library Migration Agent~~ | ✅ Done (Day 9) | Chat, Backend | — |
| ~~**P0**~~ | ~~Secret Detection + SAST~~ | ✅ Done (Day 10) | Backend, IDE | — |
| ~~**P0**~~ | ~~SCA Vulnerability Scanning~~ | ✅ Done (Day 10) | Backend, Projects | — |
| ~~**P1**~~ | ~~Security Dashboard~~ | ✅ Done (Day 10) | Security page | — |
| **P2** | Persist settings to backend | Pending | Settings | Medium |
| **P2** | Monaco hover/go-to-definition via Knowledge Graph | Pending | IDE | Medium |
| **P3** | Wire search to backend | Pending | All (header) | Low |
| **P3** | Wire integration connect buttons | Pending | Integrations | High |
| **P3** | Real docs/tutorials content | Pending | Docs, Tutorials | Low |
| **P3** | WebSocket PTY for interactive terminal | Pending | IDE | High |
