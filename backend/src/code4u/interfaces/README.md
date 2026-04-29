# interfaces

HTTP API, external integrations, and MCP marketplace.

## Purpose

- Expose FastAPI app and all route modules.
- Integrate with Jira, Slack, meeting AI, etc.
- MCP marketplace and server.

## Belongs here

- api (app, routes).
- integrations (per-service adapters).
- mcp_marketplace.

## Does not belong

- Domain logic (state machine, LLM, KG, etc.) — import from other layers.
- Core config (→ `core`).

## Depends on

- All other code4u domains (platform_core, ai_engine, code_intelligence, change_execution, security_compliance, requirements_intelligence).
