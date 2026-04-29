from __future__ import annotations
"""WebSocket API routes for IDE ↔ Backend communication.

This is the real-time streaming endpoint for the VS Code extension.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

from code4u.platform_core.protocol.websocket import WebSocketHandler

logger = structlog.get_logger("api.websocket")
router = APIRouter()

# Global handler instance
ws_handler = WebSocketHandler()


@router.websocket("/ws/{workspace_id}")
async def websocket_endpoint(websocket: WebSocket, workspace_id: str):
    """
    WebSocket endpoint for IDE communication.
    
    Protocol:
    - Intent requests stream execution updates
    - Diff payloads are sent when ready for review
    - Apply/reject requests complete the flow
    """
    await ws_handler.connect(websocket, workspace_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            await ws_handler.handle_message(websocket, data, workspace_id)
    
    except WebSocketDisconnect:
        ws_handler.disconnect(workspace_id)
        logger.info("client_disconnected", workspace_id=workspace_id)
    
    except Exception as e:
        logger.error("websocket_error", workspace_id=workspace_id, error=str(e))
        ws_handler.disconnect(workspace_id)

