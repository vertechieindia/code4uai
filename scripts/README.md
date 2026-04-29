# code4u.ai Scripts

One-off and operational scripts (training, inference).

## Purpose

- LoRA training script (calls `code4u.ai_engine.training`).
- vLLM inference startup script.

## Responsibilities

- Invoke backend packages or external tools; no new domain logic.
- **Do not:** Replace CI/CD or deployment (see `../infrastructure/`).

## Interacts with

- **Backend:** `scripts/train_lora.py` imports from `code4u.ai_engine.training`. Run from repo root with backend on PYTHONPATH.
