"""Agent Presence WebSocket — broadcast agent locations to the IDE.

Clients connect via ``WS /api/v1/ws/presence`` and receive real-time
updates when agents start working on specific files/lines. Other
backend components broadcast activity via ``broadcast_presence()``.

Wire format (JSON)::

    # server → client
    {"type": "agent_active", "agent": "Refactor", "file": "src/utils.py", "line": 42, "action": "analyzing"}
    {"type": "agent_idle",   "agent": "Refactor"}
    {"type": "agents_list",  "agents": [...]}
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

logger = structlog.get_logger("presence")

router = APIRouter()

# Connected WebSocket clients
_clients: Set[WebSocket] = set()

# Current agent states: agent_name → state dict
_agent_states: Dict[str, Dict[str, Any]] = {}


async def broadcast_presence(
    agent: str,
    file_path: str = "",
    line: int = 0,
    action: str = "analyzing",
    detail: str = "",
) -> None:
    """Broadcast agent activity to all connected IDE clients.

    Call this from any backend component (PlanExecutor, agents, etc.)
    to notify the frontend where the AI swarm is currently active.
    """
    if file_path:
        state = {
            "type": "agent_active",
            "agent": agent,
            "file": file_path,
            "line": line,
            "action": action,
            "detail": detail,
            "ts": time.time(),
        }
    else:
        state = {
            "type": "agent_idle",
            "agent": agent,
            "ts": time.time(),
        }

    _agent_states[agent] = state
    await _broadcast(state)


async def _broadcast(data: Dict[str, Any]) -> None:
    """Send a JSON message to all connected clients."""
    if not _clients:
        return

    msg = json.dumps(data)
    dead: List[WebSocket] = []
    for ws in _clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


@router.websocket("/ws/presence")
async def presence_ws(ws: WebSocket):
    """WebSocket endpoint for agent presence updates."""
    await ws.accept()
    _clients.add(ws)
    logger.info("presence_client_connected", total=len(_clients))

    try:
        # Send current agent states on connect
        agents = [s for s in _agent_states.values() if s.get("type") == "agent_active"]
        await ws.send_text(json.dumps({"type": "agents_list", "agents": agents}))

        # Keep alive — listen for pings / disconnect
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30)
                if data == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "heartbeat", "ts": time.time()}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _clients.discard(ws)
        logger.info("presence_client_disconnected", total=len(_clients))
