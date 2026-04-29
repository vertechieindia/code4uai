# code4u.ai Frontends

All user-facing frontend applications and IDE integrations.

## Purpose

- Web workspace, dashboards, admin UI, web agent manager.
- VS Code and JetBrains IDE extensions.
- Mobile app and shared packages (e.g. knowledge-graph).

## Responsibilities

- Implement UI and call backend API (`backend` → `code4u.interfaces.api`).
- **Do not:** Implement business or execution logic; that lives in the backend.

## Layout

| Folder | Contents |
|--------|----------|
| `workspace/` | Main web workspace (React). |
| `dashboard/` | User dashboard. |
| `admin-dashboard/` | Admin UI. |
| `web-agent-manager/` | Web UI for agent management. |
| `vscode-extension/` | VS Code extension. |
| `jetbrains-plugin/` | JetBrains IDE plugin. |
| `mobile-app/` | React Native app. |
| `packages/knowledge-graph/` | Shared knowledge-graph library. |

## Run

From repo root: `pnpm install` then `pnpm dev:frontend`. Or run a single app, e.g. `pnpm --filter code4u-workspace dev`.

## Interacts with

- **Backend:** HTTP/WebSocket to `code4u.interfaces.api.app` (see `../backend/`).
