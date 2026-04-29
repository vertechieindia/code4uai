from __future__ import annotations
"""Main FastAPI application for code4u.ai."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from code4u.core import get_settings, configure_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(level="DEBUG" if settings.debug else "INFO", json_logs=settings.environment == "production")
    yield

app = FastAPI(
    title="code4u.ai API",
    description="AI-Native Engineering Platform for Enterprise-Scale Development",
    version="1.0.0",
    lifespan=lifespan
)

settings = get_settings()
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ── JWT / Tenant Isolation Middleware ─────────────────────────────
PUBLIC_PATHS = frozenset({
    "/", "/health", "/docs", "/redoc", "/openapi.json",
    "/api/v1/auth/login", "/api/v1/auth/register",
    "/api/v1/auth/github/login", "/api/v1/auth/github/callback",
    "/api/v1/webhooks/git-event",
    "/api/v1/health/doctor",
    "/api/v1/smoke-test",
})

PUBLIC_PREFIXES = ("/docs", "/redoc", "/openapi.json")


class TenantAuthMiddleware(BaseHTTPMiddleware):
    """Validate JWT on every request except public paths.

    On success, sets request.state.tenant_id and request.state.user_id.
    On failure, returns 401 JSON.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        # WebSocket upgrade and OPTIONS preflight are exempt
        if request.method == "OPTIONS" or "upgrade" in request.headers.get("connection", "").lower():
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        token = auth_header[7:]
        from code4u.interfaces.api.deps import _auth_manager
        payload = _auth_manager().verify_token(token)
        if payload is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        request.state.user_id = payload.get("sub", "")
        request.state.tenant_id = payload.get("tenant_id", "")
        request.state.email = payload.get("email", "")
        return await call_next(request)


app.add_middleware(TenantAuthMiddleware)

# Import and register routers
from code4u.interfaces.api.routes import refactor, analysis, transactions, llm
from code4u.interfaces.api.routes import websocket, billing, compliance
from code4u.interfaces.api.routes import autocomplete, browser, graph
from code4u.interfaces.api.routes import models, rules, integrations, meeting
from code4u.interfaces.api.routes import supercomplete, mcp, agent, knowledge
from code4u.interfaces.api.routes import ril
from code4u.interfaces.api.routes import ide
from code4u.interfaces.api.routes import events
from code4u.interfaces.api.routes import webhooks
from code4u.interfaces.api.routes import analytics as analytics_routes
from code4u.interfaces.api.routes import admin as admin_routes
from code4u.interfaces.api.routes import watcher as watcher_routes
from code4u.interfaces.api.routes import chat as chat_routes
from code4u.interfaces.api.routes import migration as migration_routes
from code4u.interfaces.api.routes import presence as presence_routes
from code4u.interfaces.api.routes import healing as healing_routes
from code4u.interfaces.api.routes import quality as quality_routes
from code4u.interfaces.api.routes import vision as vision_routes
from code4u.interfaces.api.routes import swarm as swarm_routes
from code4u.interfaces.api.routes import nexus as nexus_routes
from code4u.interfaces.api.routes import sentinel as sentinel_routes
from code4u.interfaces.api.routes import profiler as profiler_routes
from code4u.interfaces.api.routes import auth as auth_routes
from code4u.interfaces.api.routes import filesystem as filesystem_routes
from code4u.interfaces.api.routes import projects as projects_routes
from code4u.interfaces.api.routes import test_runner as test_runner_routes
from code4u.interfaces.api.routes import review as review_routes
from code4u.interfaces.api.routes import guardian as guardian_routes
from code4u.interfaces.api.routes import nvd_watch as nvd_watch_routes
from code4u.interfaces.api.routes import hotspot as hotspot_routes
from code4u.interfaces.api.routes import chaos as chaos_routes
from code4u.interfaces.api.routes import wisdom as wisdom_routes
from code4u.interfaces.api.routes import governance as governance_routes
from code4u.interfaces.api.routes import launch as launch_routes

# Day-2: structured error when pipeline step missing (never fake success)
from code4u.platform_core.agents.errors import PipelineIncompleteError

@app.exception_handler(PipelineIncompleteError)
async def pipeline_incomplete_handler(request, exc: PipelineIncompleteError):
    return JSONResponse(
        status_code=500,
        content={"detail": exc.message, "code": "PIPELINE_INCOMPLETE"},
    )

# Authentication (public — no JWT required)
app.include_router(auth_routes.router, prefix="/api/v1", tags=["Authentication"])

# Core API routes
app.include_router(refactor.router, prefix="/api/v1", tags=["Refactor"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis"])
app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["Transactions"])
app.include_router(llm.router, prefix="/api/v1", tags=["Internal LLM"])

# WebSocket for IDE protocol
app.include_router(websocket.router, tags=["IDE Protocol"])

# Billing & usage
app.include_router(billing.router, prefix="/api/v1", tags=["Billing"])

# Compliance & audit
app.include_router(compliance.router, prefix="/api/v1", tags=["Compliance"])

# Autocomplete & Tab completion
app.include_router(autocomplete.router, prefix="/api/v1", tags=["Autocomplete"])

# Browser Agent
app.include_router(browser.router, prefix="/api/v1", tags=["Browser Agent"])

# Knowledge Graph
app.include_router(graph.router, prefix="/api/v1", tags=["Knowledge Graph"])

# Model Picker & Routing
app.include_router(models.router, prefix="/api/v1", tags=["Models"])

# Rules & Workflows
app.include_router(rules.router, prefix="/api/v1", tags=["Rules & Workflows"])

# External Integrations (Slack, Jira, ServiceNow, etc.)
app.include_router(integrations.router, prefix="/api/v1", tags=["Integrations"])

# Meeting AI & Approval Workflow
app.include_router(meeting.router, prefix="/api/v1", tags=["Meeting AI"])

# Supercomplete (Enhanced Autocomplete)
app.include_router(supercomplete.router, prefix="/api/v1", tags=["Supercomplete"])

# MCP Marketplace
app.include_router(mcp.router, prefix="/api/v1", tags=["MCP Marketplace"])

# Agent Manager (Mobile/Web)
app.include_router(agent.router, prefix="/api/v1", tags=["Agent Manager"])

# Knowledge Items & Memories
app.include_router(knowledge.router, prefix="/api/v1", tags=["Knowledge"])

# Requirements Intelligence Layer (RIL)
# Full pipeline: Slack/Teams/Zoom → Transcript → Requirements → Execution
app.include_router(ril.router, prefix="/api/v1", tags=["Requirements Intelligence"])

# IDE-specific routes (VS Code, JetBrains, etc.)
app.include_router(ide.router, prefix="/api/v1", tags=["IDE Integration"])

# SSE streaming for real-time pipeline progress
app.include_router(events.router, prefix="/api/v1", tags=["Events"])

# GitHub/GitLab webhooks for PR automation
app.include_router(webhooks.router, prefix="/api/v1", tags=["Webhooks"])

# Analytics & ROI dashboard
app.include_router(analytics_routes.router, prefix="/api/v1", tags=["Analytics"])

# Admin — recipe governance & global config
app.include_router(admin_routes.router, prefix="/api/v1", tags=["Admin"])

# File watcher — real-time incremental reindexing
app.include_router(watcher_routes.router, prefix="/api/v1", tags=["Watcher"])

# Graph-augmented code chat
app.include_router(chat_routes.router, prefix="/api/v1", tags=["Chat"])

# Multi-file structural migration
app.include_router(migration_routes.router, prefix="/api/v1", tags=["Migration"])

# Real-time presence & collaborative staging (WebSocket + REST)
app.include_router(presence_routes.router, prefix="/api/v1", tags=["Presence"])

# Self-healing build agent — error diagnosis & automated repair
app.include_router(healing_routes.router, prefix="/api/v1", tags=["Healing"])

# Quality gate — Critic, Guardrails, Consensus
app.include_router(quality_routes.router, prefix="/api/v1", tags=["Quality"])

# Vision-to-Code — multimodal UI analysis and refactoring
app.include_router(vision_routes.router, prefix="/api/v1", tags=["Vision"])

# Autonomous Swarm Orchestrator — multi-agent task decomposition
app.include_router(swarm_routes.router, prefix="/api/v1", tags=["Swarm"])

# Multi-Repo Nexus — cross-repo impact analysis
app.include_router(nexus_routes.router, prefix="/api/v1", tags=["Nexus"])

# Drift Sentinel — architectural guardrails
app.include_router(sentinel_routes.router, prefix="/api/v1", tags=["Sentinel"])

# Performance Profiler — AI-driven optimization
app.include_router(profiler_routes.router, prefix="/api/v1", tags=["Profiler"])

# File system — IDE file tree, content, save, terminal, symbols
app.include_router(filesystem_routes.router, prefix="/api/v1", tags=["File System"])

# Project management — CRUD, indexing, health scores
app.include_router(projects_routes.router, prefix="/api/v1", tags=["Projects"])

# Test Runner — execute tests and return structured results
app.include_router(test_runner_routes.router, prefix="/api/v1", tags=["Test Runner"])

# Synthetic Code Review — AI-powered review without a real PR
app.include_router(review_routes.router, prefix="/api/v1", tags=["Code Review"])

# Optimization & Semantic Search — performance analysis and concept search
from code4u.interfaces.api.routes import optimize as optimize_routes
app.include_router(optimize_routes.router, prefix="/api/v1", tags=["Optimization"])

# Library Migration — dependency analysis and upgrade planning
from code4u.interfaces.api.routes import migration as migration_routes
app.include_router(migration_routes.router, prefix="/api/v1", tags=["Migration"])

# Notification Bridge — Slack/Teams webhook integration
from code4u.interfaces.api.routes import notifications as notifications_routes
app.include_router(notifications_routes.router, prefix="/api/v1", tags=["Notifications"])

# Deploy — CI/CD pipeline generation and deployment orchestration
from code4u.interfaces.api.routes import deploy as deploy_routes
app.include_router(deploy_routes.router, prefix="/api/v1", tags=["Deploy"])

# Telemetry — token usage, cost tracking, observability
from code4u.interfaces.api.routes import telemetry as telemetry_routes
app.include_router(telemetry_routes.router, prefix="/api/v1", tags=["Telemetry"])

# Air-Gapped Mode — local-only operation toggle
from code4u.interfaces.api.routes import airgap as airgap_routes
app.include_router(airgap_routes.router, prefix="/api/v1", tags=["Air-Gapped"])

# System Doctor — comprehensive health diagnostics
from code4u.interfaces.api.routes import doctor as doctor_routes
app.include_router(doctor_routes.router, prefix="/api/v1", tags=["Doctor"])

# Compliance Export — audit report generation
from code4u.interfaces.api.routes import export as export_routes
app.include_router(export_routes.router, prefix="/api/v1", tags=["Export"])

# Model Distillation — fine-tuning data collection & export
from code4u.interfaces.api.routes import distillation as distillation_routes
app.include_router(distillation_routes.router, prefix="/api/v1", tags=["Distillation"])

# Real-time Collaboration — multiplayer editing
from code4u.interfaces.api.routes import collaboration as collaboration_routes
app.include_router(collaboration_routes.router, prefix="/api/v1", tags=["Collaboration"])

# Autonomous PR Staging — ephemeral preview environments
from code4u.interfaces.api.routes import staging as staging_routes
app.include_router(staging_routes.router, prefix="/api/v1", tags=["Staging"])

# Production Smoke Test — end-to-end readiness verification
from code4u.interfaces.api.routes import smoke as smoke_routes
app.include_router(smoke_routes.router, prefix="/api/v1", tags=["Smoke Test"])

# Guardian — Gauntlet Orchestrator & Security Fortress (Titan Phase)
app.include_router(guardian_routes.router, prefix="/api/v1", tags=["Guardian"])

# NVD Vulnerability Watch — real-time CVE monitoring
app.include_router(nvd_watch_routes.router, prefix="/api/v1", tags=["NVD Watch"])

# Hotspot Analytics & Predictive Risk
app.include_router(hotspot_routes.router, prefix="/api/v1", tags=["Hotspot Analytics"])

# Chaos Engineering & Adversarial Testing & Red Team
app.include_router(chaos_routes.router, prefix="/api/v1", tags=["Chaos & Red Team"])

# Collective Intelligence — Wisdom Nuggets & Cross-Project Patterns
app.include_router(wisdom_routes.router, prefix="/api/v1", tags=["Collective Intelligence"])

# Legal, License & Ethical Governance
app.include_router(governance_routes.router, prefix="/api/v1", tags=["Legal & Ethics"])

# Launch Command Center — stress test, impact summary, readiness check
app.include_router(launch_routes.router, prefix="/api/v1", tags=["Launch Command Center"])


@app.get("/health")
async def health(): 
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/")
async def root():
    return {
        "name": "code4u.ai",
        "version": "0.1.0",
        "description": "AI-Native Engineering Platform",
        "tagline": "We don't generate code — we execute verified engineering changes.",
        "endpoints": {
            "refactor": "/api/v1/refactor",
            "analysis": "/api/v1/analysis",
            "transactions": "/api/v1/transactions",
            "internal_llm": "/api/v1/internal",
            "billing": "/api/v1/billing",
            "compliance": "/api/v1/compliance",
            "autocomplete": "/api/v1/autocomplete",
            "supercomplete": "/api/v1/supercomplete",
            "browser": "/api/v1/browser",
            "graph": "/api/v1/graph",
            "models": "/api/v1/models",
            "rules": "/api/v1/rules",
            "integrations": "/api/v1/integrations",
            "meeting": "/api/v1/meeting",
            "mcp": "/api/v1/mcp",
            "agent": "/api/v1/agent",
            "knowledge": "/api/v1/knowledge",
            "ril": "/api/v1/ril",
            "notifications": "/api/v1/notifications",
            "deploy": "/api/v1/deploy",
            "telemetry": "/api/v1/telemetry",
            "airgap": "/api/v1/airgap",
            "doctor": "/api/v1/health/doctor",
            "distillation": "/api/v1/distill",
            "collaboration": "/api/v1/collab",
            "staging": "/api/v1/staging",
            "smoke_test": "/api/v1/smoke-test",
            "nvd_watch": "/api/v1/nvd/watch",
            "hotspot_analytics": "/api/v1/analytics/hotspots",
            "chaos": "/api/v1/chaos",
            "wisdom": "/api/v1/wisdom",
            "red_team": "/api/v1/red-team",
            "adversarial": "/api/v1/adversarial",
            "governance": "/api/v1/governance",
            "launch": "/api/v1/launch",
            "websocket": "/ws/{workspace_id}",
            "health": "/health",
            "docs": "/docs"
        },
        "requirements_intelligence": {
            "description": "Full pipeline from conversation to execution",
            "capture": "/api/v1/ril/capture",
            "requirements": "/api/v1/ril/requirements",
            "plans": "/api/v1/ril/plans",
            "execute": "/api/v1/ril/execute",
            "commands": "/api/v1/ril/commands",
            "audit": "/api/v1/ril/audit",
        },
        "developer_delight": {
            "supercomplete": "Multi-step intelligent code generation with Tab navigation",
            "mcp_marketplace": "Discover and install MCP tools and extensions",
            "agent_manager": "Control agents from mobile, web, or CLI",
            "knowledge_memories": "Persistent knowledge and learning from corrections",
        },
        "integrations": {
            "project_management": ["jira", "asana", "trello", "monday", "clickup", "wrike", "basecamp"],
            "itsm": ["servicenow", "zendesk", "freshservice"],
            "communication": ["slack", "teams", "discord"],
            "meetings": ["zoom", "teams", "google_meet", "webex"],
            "documentation": ["notion", "confluence"],
            "design": ["miro", "figma"],
        },
        "moat": {
            "knowledge_graph": "First-class code relationship modeling",
            "state_machine": "Deterministic agent coordination",
            "contracts": "Schema and API enforcement",
            "compliance": "SOC 2 + ISO 27001 built-in",
            "cost_control": "Self-hosted first, premium fallback",
        }
    }
