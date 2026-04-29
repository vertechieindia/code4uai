# change_execution

Diff engine and validation.

## Purpose

- Manage diff transactions (create, add_diff, apply, rollback).
- Validate diffs and ASTs.

## Belongs here

- diff_engine (transaction, FileDiff, TransactionManager).
- validation (diff_validator, ast_validator).

## Does not belong

- State machine (→ `platform_core`).
- LLM (→ `ai_engine`).
- API routes (→ `interfaces.api`).

## Depends on

- Used by `platform_core.protocol` and API routes.
