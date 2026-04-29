# code4u.ai Infrastructure

Deployment and run-time infrastructure only.

## Purpose

- Docker Compose (API, DB, Redis, Qdrant; optional GPU/vLLM).
- Kubernetes manifests for API and vLLM.

## Responsibilities

- Define how the backend and dependencies are built and run.
- **Do not:** Contain application or domain code; that lives in `../backend/`.

## Layout

| Folder | Contents |
|--------|----------|
| `docker/` | Dockerfile(s), docker-compose.yml, docker-compose.gpu.yml. |
| `kubernetes/` | Deployments and related K8s manifests. |

## Run

- **Docker:** From `infrastructure/docker/`, e.g. `docker-compose up -d` or `docker-compose -f docker-compose.gpu.yml up -d`.
- **Kubernetes:** `kubectl apply -f infrastructure/kubernetes/` (after configuring namespace/secrets).

## Interacts with

- **Backend:** Builds and runs `backend` image; entrypoint `code4u.interfaces.api.app:app`.
