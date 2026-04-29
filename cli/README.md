# code4u.ai CLI

Terminal client for the code4u.ai API.

## Purpose

- Expose refactor, analyze, chat, generate, agent, and config commands.
- Call backend HTTP API; no domain logic here.

## Responsibilities

- Parse commands and options, call backend, display results.
- **Do not:** Implement state machine, LLM, or execution logic; that lives in the backend.

## Run

From repo root (or `cli/`): `code4u` or `c4u` after installing the CLI package. Requires backend to be running for most commands.

## Interacts with

- **Backend:** HTTP to `code4u.interfaces.api` (see `../backend/`).
