# code4u.ai Backend

Python backend services for the code4u.ai platform. Single package `code4u` under `src/code4u/`.

## Purpose

- **API:** FastAPI app and HTTP/WebSocket routes (under `interfaces.api`).
- **Domain logic:** Organized by architectural layer (see below).

## Responsibilities

- Serve the REST and WebSocket API.
- Run deterministic execution (state machine, agents), LLM orchestration, code intelligence, change execution, security/compliance, and requirements intelligence (RIL).
- **Does not:** Own frontend builds, CLI packaging, or infrastructure definitions.

## Layout (under `src/code4u/`)

| Folder | Contents |
|--------|----------|
| `core/` | Shared config and logging only. |
| `platform_core/` | State machine, rules engine, agents, protocol, agent manager, browser agent. |
| `ai_engine/` | LLM, routing, model picker, compiler, training, evaluation, autocomplete, supercomplete. |
| `code_intelligence/` | Knowledge graph, context, knowledge store. |
| `change_execution/` | Diff engine, validation. |
| `security_compliance/` | Security, compliance, billing. |
| `requirements_intelligence/` | RIL pipeline. |
| `interfaces/` | API (FastAPI + routes), integrations, MCP marketplace. |

## Run

```bash
poetry install
poetry run python run.py
```

Equivalent long form:

```bash
poetry run uvicorn code4u.interfaces.api.app:app --reload --host 0.0.0.0 --port 8000
```

### Auth users in PostgreSQL

Set in `.env`:

- `DATABASE_URL` — use `postgresql://` or `postgresql+asyncpg://` (both work).
- `AUTH_PERSIST_USERS=true` — register/login read and write table **`code4u_auth_users`** (created automatically).

If `AUTH_PERSIST_USERS` is unset or `false`, users stay in-memory (default for tests).

### Google Sign-In

Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and (if different from default) `GOOGLE_REDIRECT_URI` / `GOOGLE_OAUTH_SUCCESS_REDIRECT` in `.env`. In Google Cloud Console, add **Authorized redirect URI** exactly matching `GOOGLE_REDIRECT_URI` (e.g. `http://localhost:3000/api/v1/auth/google/callback` when using the Vite proxy).

Flow: browser opens `GET /api/v1/auth/google/login` → Google → `GET /api/v1/auth/google/callback` → app JWT → redirect to `GOOGLE_OAUTH_SUCCESS_REDIRECT#c4u_token=...` (login page completes session).

### GitHub Sign-In (SSO) vs Connect Repo

- **Sign in / Sign up:** open `GET /api/v1/auth/github/login?flow=sso` (redirect). After GitHub, callback issues an app JWT and redirects to `GITHUB_OAUTH_SUCCESS_REDIRECT#c4u_token=...` (same login page handler as Google). Scopes: `read:user user:email`.
- **Connect Repo (existing):** `GET /api/v1/auth/github/login` with **no** `flow` returns JSON `{ url }` and uses `state=code4u` and `repo` scope.

Set `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI` (must match the **Authorization callback URL** in the GitHub OAuth App, e.g. `http://localhost:3000/api/v1/auth/github/callback` with Vite on port 3000), and optional `GITHUB_OAUTH_SUCCESS_REDIRECT` (default `http://localhost:3000/login`).

## Interacts with

- **Frontends:** Consumed via HTTP/WebSocket.
- **Infrastructure:** Deployed via Docker/Kubernetes in `../infrastructure/`.
- **CLI:** Calls backend API; lives in `../cli/`.
