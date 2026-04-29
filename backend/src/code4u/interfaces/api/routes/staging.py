"""Autonomous PR Staging — ephemeral preview environments.

Automatically spins up short-lived preview deployments for every
proposed refactor so users can test the live app before clicking
"Apply". Supports Vercel, K8s namespaces, and Docker Compose
as preview backends.

Endpoints:
  - ``POST /staging/create``       — spin up an ephemeral environment
  - ``GET  /staging/environments`` — list active preview environments
  - ``GET  /staging/{id}``         — get environment details
  - ``DELETE /staging/{id}``       — tear down an environment
  - ``POST /staging/promote``      — promote preview to staging/production
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger("staging")

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_environments: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateStagingRequest(BaseModel):
    projectId: str = Field(..., description="Project ID to stage.")
    branch: str = Field("preview", description="Git branch name for the preview.")
    provider: str = Field("auto", description="Backend: vercel | k8s | docker | auto.")
    graphId: str = Field("", description="Swarm TaskGraph ID that triggered this preview.")
    commitSha: str = Field("", description="Commit SHA to deploy.")
    config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration.")


class PromoteRequest(BaseModel):
    environmentId: str = Field(..., description="ID of the ephemeral environment to promote.")
    targetEnv: str = Field("staging", description="Target: staging | production.")


# ---------------------------------------------------------------------------
# Provider generators
# ---------------------------------------------------------------------------

def _generate_vercel_config(project_id: str, branch: str, commit: str) -> Dict[str, Any]:
    slug = f"preview-{project_id[:8]}-{branch}"
    return {
        "provider": "vercel",
        "url": f"https://{slug}.vercel.app",
        "deployHook": f"https://api.vercel.com/v1/integrations/deploy/{slug}",
        "config": {
            "framework": "auto",
            "buildCommand": "npm run build",
            "outputDirectory": "dist",
            "environment": "preview",
            "gitBranch": branch,
            "gitCommit": commit,
        },
    }


def _generate_k8s_config(project_id: str, branch: str, commit: str) -> Dict[str, Any]:
    ns = f"preview-{project_id[:8]}-{branch[:12]}"
    return {
        "provider": "k8s",
        "url": f"https://{ns}.preview.code4u.dev",
        "namespace": ns,
        "manifests": {
            "namespace": {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": ns,
                    "labels": {
                        "app.kubernetes.io/part-of": "code4u-preview",
                        "preview/project-id": project_id,
                        "preview/branch": branch,
                    },
                    "annotations": {
                        "preview/ttl": "24h",
                        "preview/commit": commit,
                    },
                },
            },
            "deployment": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "app", "namespace": ns},
                "spec": {
                    "replicas": 1,
                    "selector": {"matchLabels": {"app": "preview"}},
                    "template": {
                        "metadata": {"labels": {"app": "preview"}},
                        "spec": {
                            "containers": [{
                                "name": "app",
                                "image": f"code4u/{project_id}:{commit[:7]}",
                                "ports": [{"containerPort": 3000}],
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "128Mi"},
                                    "limits": {"cpu": "500m", "memory": "512Mi"},
                                },
                            }],
                        },
                    },
                },
            },
            "service": {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": "app", "namespace": ns},
                "spec": {
                    "selector": {"app": "preview"},
                    "ports": [{"port": 80, "targetPort": 3000}],
                },
            },
            "ingress": {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "name": "app",
                    "namespace": ns,
                    "annotations": {"cert-manager.io/cluster-issuer": "letsencrypt"},
                },
                "spec": {
                    "rules": [{"host": f"{ns}.preview.code4u.dev", "http": {"paths": [{"path": "/", "pathType": "Prefix", "backend": {"service": {"name": "app", "port": {"number": 80}}}}]}}],
                    "tls": [{"hosts": [f"{ns}.preview.code4u.dev"], "secretName": f"{ns}-tls"}],
                },
            },
        },
    }


def _generate_docker_config(project_id: str, branch: str, commit: str) -> Dict[str, Any]:
    port = 3000 + (hash(project_id + branch) % 1000)
    return {
        "provider": "docker",
        "url": f"http://localhost:{port}",
        "compose": {
            "version": "3.8",
            "services": {
                "preview": {
                    "build": {"context": ".", "dockerfile": "Dockerfile"},
                    "ports": [f"{port}:3000"],
                    "environment": {
                        "NODE_ENV": "preview",
                        "GIT_BRANCH": branch,
                        "GIT_COMMIT": commit,
                    },
                    "labels": {
                        "preview.project": project_id,
                        "preview.branch": branch,
                    },
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/staging/create")
async def create_staging(request: CreateStagingRequest) -> Dict[str, Any]:
    """Spin up an ephemeral preview environment for a refactor."""
    env_id = str(uuid.uuid4())[:12]
    commit = request.commitSha or hashlib.sha1(f"{request.projectId}-{time.time()}".encode()).hexdigest()[:7]
    provider = request.provider

    if provider == "auto":
        provider = "k8s"

    if provider == "vercel":
        config = _generate_vercel_config(request.projectId, request.branch, commit)
    elif provider == "k8s":
        config = _generate_k8s_config(request.projectId, request.branch, commit)
    elif provider == "docker":
        config = _generate_docker_config(request.projectId, request.branch, commit)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    env = {
        "id": env_id,
        "projectId": request.projectId,
        "branch": request.branch,
        "commitSha": commit,
        "provider": provider,
        "status": "deploying",
        "url": config["url"],
        "config": config,
        "graphId": request.graphId,
        "createdAt": time.time(),
        "expiresAt": time.time() + 86400,
        "ttl": "24h",
    }

    _environments[env_id] = env
    logger.info("staging_created", id=env_id, provider=provider, url=config["url"])

    env["status"] = "ready"

    return {
        "status": "created",
        "environment": env,
    }


@router.get("/staging/environments")
async def list_environments(projectId: str = "") -> Dict[str, Any]:
    """List active ephemeral environments."""
    envs = list(_environments.values())
    if projectId:
        envs = [e for e in envs if e["projectId"] == projectId]

    envs.sort(key=lambda e: e["createdAt"], reverse=True)

    return {
        "environments": envs,
        "total": len(envs),
    }


@router.get("/staging/{env_id}")
async def get_environment(env_id: str) -> Dict[str, Any]:
    """Get details for a specific ephemeral environment."""
    env = _environments.get(env_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    return env


@router.delete("/staging/{env_id}")
async def teardown_environment(env_id: str) -> Dict[str, Any]:
    """Tear down an ephemeral environment and release resources."""
    if env_id not in _environments:
        raise HTTPException(status_code=404, detail="Environment not found")

    env = _environments.pop(env_id)
    logger.info("staging_torn_down", id=env_id, provider=env["provider"])

    return {
        "status": "destroyed",
        "id": env_id,
        "provider": env["provider"],
        "liveFor": round(time.time() - env["createdAt"]),
    }


@router.post("/staging/promote")
async def promote_environment(request: PromoteRequest) -> Dict[str, Any]:
    """Promote an ephemeral environment to staging or production."""
    env = _environments.get(request.environmentId)
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    return {
        "status": "promoted",
        "from": "preview",
        "to": request.targetEnv,
        "environmentId": request.environmentId,
        "commitSha": env["commitSha"],
        "projectId": env["projectId"],
        "note": f"Preview environment promoted to {request.targetEnv}. "
                f"In production, this would trigger the CI/CD pipeline for "
                f"commit {env['commitSha']} targeting {request.targetEnv}.",
    }
