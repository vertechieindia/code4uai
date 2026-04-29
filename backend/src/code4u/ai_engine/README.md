# ai_engine

LLM orchestration, routing, prompting, training, and completion.

## Purpose

- Route and execute LLM calls (cost-aware, self-hosted vs premium).
- Compile prompts and constraints; run evaluation and training.
- Autocomplete and supercomplete.

## Belongs here

- llm (client, router, executor, prompts, rejection).
- routing (engine, complexity, cost_controls).
- model_picker.
- compiler (prompt_compiler, constraints, scope_reducer).
- training, evaluation.
- autocomplete, supercomplete.

## Does not belong

- State machine or agents (→ `platform_core`).
- Knowledge graph (→ `code_intelligence`).
- API routes (→ `interfaces.api`).

## Depends on

- `code_intelligence.context` (context for prompts).
- `change_execution.validation` (output validation).
