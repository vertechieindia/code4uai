# requirements_intelligence

Requirements Intelligence Layer (RIL).

## Purpose

- Ingest conversations (Slack, Teams, Zoom).
- Extract and structure requirements; plan and execute commands.
- RIL-specific security (consent, redaction, audit).

## Belongs here

- ril (ingestion, intelligence, structuring, agent, graph, security, stt).

## Does not belong

- General security or compliance (→ `security_compliance`).
- API route definitions (→ `interfaces.api`).

## Depends on

- May use `code_intelligence`, `ai_engine`; exposed via `interfaces.api.routes.ril`.
