# platform_core

Deterministic execution, state machine, rules, and agents.

## Purpose

- Enforce strict state transitions (no skipping).
- Run planner, verifier, orchestrator, protocol handler, agent manager, browser agent.

## Belongs here

- State machine (states, machine, coordinator).
- Rules engine.
- Agents (base, planner, verifier, orchestrator).
- IDE protocol (messages, handler, websocket).
- Agent manager (session, notifications).
- Browser agent.

## Does not belong

- LLM or routing (→ `ai_engine`).
- Knowledge graph or context (→ `code_intelligence`).
- Diffs or validation (→ `change_execution`).
- HTTP API (→ `interfaces.api`).

## Depends on

- `ai_engine.routing` (protocol handler).
- `code_intelligence`, `change_execution` used by orchestrator/agents.
