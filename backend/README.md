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
poetry run uvicorn code4u.interfaces.api.app:app --reload --host 0.0.0.0 --port 8000
```

## Interacts with

- **Frontends:** Consumed via HTTP/WebSocket.
- **Infrastructure:** Deployed via Docker/Kubernetes in `../infrastructure/`.
- **CLI:** Calls backend API; lives in `../cli/`.
