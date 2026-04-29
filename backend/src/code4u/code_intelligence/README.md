# code_intelligence

Knowledge graph, context selection, and knowledge store.

## Purpose

- Model codebase (repos, packages, modules, symbols, ownership).
- Compile context for intents (symbol lookup, dependency traversal, impact).
- Knowledge items and memories.

## Belongs here

- knowledge_graph (graph, indexer, query, traversal).
- context (compiler, planner).
- knowledge (store, items, memories).

## Does not belong

- LLM or prompts (→ `ai_engine`).
- Diff application (→ `change_execution`).
- API routes (→ `interfaces.api`).

## Depends on

- Used by `ai_engine`, `platform_core` (orchestrator, protocol).
