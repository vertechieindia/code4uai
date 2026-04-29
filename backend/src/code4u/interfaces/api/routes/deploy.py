"""Deploy API — CI/CD pipeline generation and deployment orchestration.

Endpoints:
  - ``POST /deploy/generate``      — generate a CI/CD pipeline for a project.
  - ``POST /deploy/dockerfile``    — generate a production Dockerfile.
  - ``GET  /deploy/pipelines``     — list generated pipelines.
  - ``GET  /deploy/status``        — deployment status tracker.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_pipelines: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class GeneratePipelineRequest(BaseModel):
    workspacePath: str = Field("", description="Project workspace path.")
    language: str = Field("auto", description="Primary language (auto-detected if 'auto').")
    provider: str = Field("github", description="CI/CD provider: github | gitlab | bitbucket.")
    targetEnv: str = Field("staging", description="Target environment: staging | production.")
    includeTests: bool = Field(True, description="Include test step in pipeline.")
    includeDocker: bool = Field(True, description="Include Docker build/push step.")
    includeSecurity: bool = Field(True, description="Include security scanning step.")


class GenerateDockerfileRequest(BaseModel):
    workspacePath: str = Field("", description="Project workspace path.")
    language: str = Field("auto", description="Primary language.")
    baseImage: str = Field("", description="Override base image.")
    multistage: bool = Field(True, description="Use multi-stage build.")


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def _detect_language(workspace_path: str) -> str:
    """Auto-detect the primary language from project files."""
    if not workspace_path:
        return "python"
    p = Path(workspace_path)
    if (p / "go.mod").exists():
        return "go"
    if (p / "package.json").exists():
        if (p / "tsconfig.json").exists():
            return "typescript"
        return "javascript"
    if (p / "Cargo.toml").exists():
        return "rust"
    if (p / "build.gradle").exists() or (p / "pom.xml").exists():
        return "java"
    if (p / "requirements.txt").exists() or (p / "pyproject.toml").exists():
        return "python"
    return "python"


# ---------------------------------------------------------------------------
# Pipeline generators
# ---------------------------------------------------------------------------

def _generate_github_action(
    language: str,
    target_env: str,
    include_tests: bool,
    include_docker: bool,
    include_security: bool,
) -> str:
    test_cmds = {
        "python": "pip install -r requirements.txt && pytest",
        "go": "go test ./...",
        "typescript": "npm ci && npm test",
        "javascript": "npm ci && npm test",
        "rust": "cargo test",
        "java": "./gradlew test",
    }
    build_cmds = {
        "python": "pip install -r requirements.txt",
        "go": "go build -o app ./...",
        "typescript": "npm ci && npm run build",
        "javascript": "npm ci && npm run build",
        "rust": "cargo build --release",
        "java": "./gradlew build",
    }
    setup_steps = {
        "python": """      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'""",
        "go": """      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'""",
        "typescript": """      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'""",
        "javascript": """      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'""",
        "rust": """      - uses: dtolnay/rust-toolchain@stable""",
        "java": """      - uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'""",
    }

    yml = f"""name: Deploy to {target_env.capitalize()}

on:
  push:
    branches: [{'"main"' if target_env == 'production' else '"develop", "staging"'}]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{{{ github.repository }}}}

jobs:"""

    if include_tests:
        yml += f"""
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
{setup_steps.get(language, setup_steps['python'])}
      - name: Run Tests
        run: {test_cmds.get(language, test_cmds['python'])}
"""

    if include_security:
        yml += f"""
  security:
    runs-on: ubuntu-latest
    {"needs: test" if include_tests else ""}
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'
"""

    yml += f"""
  build:
    runs-on: ubuntu-latest
    {"needs: [test, security]" if include_tests and include_security else "needs: test" if include_tests else "needs: security" if include_security else ""}
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
{setup_steps.get(language, setup_steps['python'])}
      - name: Build
        run: {build_cmds.get(language, build_cmds['python'])}
"""

    if include_docker:
        yml += """
      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
"""

    yml += f"""
  deploy:
    runs-on: ubuntu-latest
    needs: build
    environment: {target_env}
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to {target_env.capitalize()}
        run: |
          echo "Deploying ${{{{ github.sha }}}} to {target_env}..."
          # kubectl set image deployment/app app=${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:${{{{ github.sha }}}}
          # OR: aws ecs update-service --service app --force-new-deployment
"""

    return yml


def _generate_gitlab_ci(
    language: str,
    target_env: str,
    include_tests: bool,
    include_docker: bool,
    include_security: bool,
) -> str:
    test_cmds = {
        "python": "pip install -r requirements.txt && pytest --junitxml=report.xml",
        "go": "go test -v ./... 2>&1 | go-junit-report > report.xml",
        "typescript": "npm ci && npm test -- --reporter junit --outputFile report.xml",
        "javascript": "npm ci && npm test",
        "rust": "cargo test",
        "java": "./gradlew test",
    }
    images = {
        "python": "python:3.12-slim",
        "go": "golang:1.22",
        "typescript": "node:20-alpine",
        "javascript": "node:20-alpine",
        "rust": "rust:latest",
        "java": "gradle:jdk21",
    }

    yml = f"""stages:
  - test
  - security
  - build
  - deploy

variables:
  DOCKER_TLS_CERTDIR: "/certs"
"""

    if include_tests:
        yml += f"""
test:
  stage: test
  image: {images.get(language, images['python'])}
  script:
    - {test_cmds.get(language, test_cmds['python'])}
  artifacts:
    when: always
    reports:
      junit: report.xml
"""

    if include_security:
        yml += """
sast:
  stage: security
  image: returntocorp/semgrep
  script:
    - semgrep scan --config=auto --json -o semgrep-report.json .
  artifacts:
    reports:
      sast: semgrep-report.json
  allow_failure: true
"""

    if include_docker:
        yml += f"""
build:
  stage: build
  image: docker:24-dind
  services:
    - docker:24-dind
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - docker tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA $CI_REGISTRY_IMAGE:latest
    - docker push $CI_REGISTRY_IMAGE:latest
"""

    only_branch = "- main" if target_env == "production" else "- develop"
    extra_branch = "" if target_env == "production" else "\n    - staging"

    yml += f"""
deploy_{target_env}:
  stage: deploy
  environment:
    name: {target_env}
  script:
    - echo "Deploying to {target_env}..."
  only:
    {only_branch}{extra_branch}
"""

    return yml


def _generate_dockerfile(
    language: str,
    multistage: bool,
    base_image: str = "",
) -> str:
    if language == "go":
        builder = base_image or "golang:1.22-alpine"
        return f"""FROM {builder} AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/server ./...

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /app/server /server
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/server"]
"""
    elif language in ("typescript", "javascript"):
        return f"""FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --production=false
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
RUN addgroup -g 1001 -S app && adduser -S app -u 1001 -G app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
USER app
EXPOSE 3000
CMD ["node", "dist/index.js"]
"""
    elif language == "rust":
        return f"""FROM rust:latest AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {{}}" > src/main.rs && cargo build --release && rm -rf src
COPY . .
RUN cargo build --release

FROM gcr.io/distroless/cc-debian12:nonroot
COPY --from=builder /app/target/release/app /app
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/app"]
"""
    elif language == "java":
        return f"""FROM gradle:jdk21 AS builder
WORKDIR /app
COPY . .
RUN gradle build --no-daemon -x test

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN addgroup -g 1001 -S app && adduser -S app -u 1001 -G app
COPY --from=builder /app/build/libs/*.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
"""
    else:
        base = base_image or "python:3.12-slim"
        return f"""FROM {base} AS builder
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM {base}
WORKDIR /app
RUN groupadd -r app && useradd -r -g app app
COPY --from=builder /install /usr/local
COPY . .
USER app
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/deploy/generate")
async def generate_pipeline(request: GeneratePipelineRequest):
    """Generate a CI/CD pipeline configuration for the project."""
    lang = request.language
    if lang == "auto":
        lang = _detect_language(request.workspacePath)

    if request.provider == "github":
        content = _generate_github_action(
            lang, request.targetEnv,
            request.includeTests, request.includeDocker, request.includeSecurity,
        )
        filename = ".github/workflows/deploy.yml"
    elif request.provider == "gitlab":
        content = _generate_gitlab_ci(
            lang, request.targetEnv,
            request.includeTests, request.includeDocker, request.includeSecurity,
        )
        filename = ".gitlab-ci.yml"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {request.provider}")

    entry = {
        "id": f"pipeline-{int(time.time())}",
        "provider": request.provider,
        "language": lang,
        "targetEnv": request.targetEnv,
        "filename": filename,
        "createdAt": time.time(),
    }
    _pipelines.append(entry)

    return {
        "filename": filename,
        "content": content,
        "language": lang,
        "provider": request.provider,
        "targetEnv": request.targetEnv,
        "pipelineId": entry["id"],
    }


@router.post("/deploy/dockerfile")
async def generate_dockerfile(request: GenerateDockerfileRequest):
    """Generate a production-ready Dockerfile for the project."""
    lang = request.language
    if lang == "auto":
        lang = _detect_language(request.workspacePath)

    content = _generate_dockerfile(lang, request.multistage, request.baseImage)

    return {
        "filename": "Dockerfile",
        "content": content,
        "language": lang,
        "multistage": request.multistage,
    }


@router.get("/deploy/pipelines")
async def list_pipelines():
    """List all generated pipelines."""
    return {
        "pipelines": sorted(_pipelines, key=lambda p: p.get("createdAt", 0), reverse=True),
        "total": len(_pipelines),
    }


@router.get("/deploy/status")
async def deployment_status():
    """Get current deployment status (simulated for demo)."""
    return {
        "environments": [
            {
                "name": "staging",
                "status": "healthy",
                "lastDeploy": time.time() - 3600,
                "version": "0.11.0-rc.1",
                "commit": "abc1234",
            },
            {
                "name": "production",
                "status": "healthy",
                "lastDeploy": time.time() - 86400,
                "version": "0.10.0",
                "commit": "def5678",
            },
        ],
    }
