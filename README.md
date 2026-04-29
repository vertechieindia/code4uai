# code4u.ai

**AI-Native Engineering Platform for Enterprise-Scale Development**

code4u.ai is NOT a chat assistant. It is:
- A **Code Intelligence Platform**
- A **Deterministic Refactoring Engine**  
- A **Frontend–Backend Contract-Aware AI IDE**
- An **Enterprise-Grade Developer Execution System**

## Project Structure

```
code4u.ai/
├── backend/                   # Python backend services
│   └── src/code4u/
│       ├── core/              # Config, logging
│       ├── platform_core/     # State machine, agents, protocol
│       ├── ai_engine/         # LLM, routing, training
│       ├── code_intelligence/ # Knowledge graph, context
│       ├── change_execution/  # Diff engine, validation
│       ├── security_compliance/ # Security, compliance, billing
│       ├── requirements_intelligence/ # RIL pipeline
│       └── interfaces/        # API, integrations, MCP
├── frontends/                 # Frontend apps & extensions
│   ├── packages/knowledge-graph/
│   ├── workspace/             # Web workspace
│   ├── vscode-extension/
│   └── ...
├── docs/                      # Documentation
└── infrastructure/            # Docker, Kubernetes
```

## Quick Start

### Frontend Development

```bash
pnpm install
pnpm dev:frontend
```

### Backend Development

```bash
cd backend
poetry install
poetry run uvicorn code4u.interfaces.api.app:app --reload
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

## Core Principles

1. **No direct file writes** - All edits show diff previews first
2. **AST-based edits** - Never regex-based modifications
3. **Structured outputs** - JSON + unified diffs
4. **No hallucinations** - STOP and request clarification if context is insufficient
5. **Rollback & validation** - First-class citizens

## License

Proprietary - code4u.ai
