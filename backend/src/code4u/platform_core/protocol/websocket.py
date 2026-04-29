from __future__ import annotations
"""WebSocket handler for streaming IDE ↔ Backend communication.

Provides real-time updates during execution.
"""
import json
from typing import Any, Callable, Awaitable
import structlog
from fastapi import WebSocket, WebSocketDisconnect

from code4u.platform_core.protocol.messages import (
    IntentRequest,
    ApplyRequest,
    RejectRequest,
    WebSocketMessage,
    ErrorResponse,
)
from code4u.platform_core.protocol.handler import ProtocolHandler

logger = structlog.get_logger("protocol.websocket")


class WebSocketHandler:
    """
    Handle WebSocket connections from IDE.
    
    Streams execution updates in real-time.
    """
    
    def __init__(self, protocol_handler: ProtocolHandler | None = None):
        self.handler = protocol_handler or ProtocolHandler()
        self._connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, workspace_id: str):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self._connections[workspace_id] = websocket
        logger.info("websocket_connected", workspace_id=workspace_id)
    
    def disconnect(self, workspace_id: str):
        """Handle disconnection."""
        self._connections.pop(workspace_id, None)
        logger.info("websocket_disconnected", workspace_id=workspace_id)
    
    async def handle_message(
        self,
        websocket: WebSocket,
        data: str,
        workspace_id: str
    ):
        """
        Handle incoming WebSocket message.
        
        Parses the message and routes to appropriate handler.
        """
        try:
            message = WebSocketMessage.model_validate_json(data)
            
            if message.type == "ping":
                await self._send(websocket, {
                    "type": "pong",
                    "payload": {},
                    "request_id": message.request_id,
                })
                return
            
            if message.type == "intent_request":
                await self._handle_intent(
                    websocket,
                    message.payload,
                    message.request_id
                )
            
            elif message.type == "apply_request":
                await self._handle_apply(
                    websocket,
                    message.payload,
                    message.request_id
                )
            
            elif message.type == "reject_request":
                await self._handle_reject(
                    websocket,
                    message.payload,
                    message.request_id
                )
            
            else:
                await self._send_error(
                    websocket,
                    f"Unknown message type: {message.type}",
                    "UNKNOWN_MESSAGE_TYPE",
                    message.request_id
                )
        
        except Exception as e:
            logger.error("websocket_message_error", error=str(e))
            await self._send_error(
                websocket,
                str(e),
                "MESSAGE_PARSE_ERROR"
            )
    
    async def _handle_intent(
        self,
        websocket: WebSocket,
        payload: Dict[str, Any],
        request_id: Optional[str]
    ):
        """Handle intent request with streaming updates."""
        try:
            request = IntentRequest.model_validate(payload)
            
            async for update in self.handler.handle_intent(request):
                await self._send(websocket, {
                    "type": "execution_update" if hasattr(update, "state") else "error",
                    "payload": update.model_dump(),
                    "request_id": request_id,
                })
        
        except Exception as e:
            await self._send_error(websocket, str(e), "INTENT_ERROR", request_id)
    
    async def _handle_apply(
        self,
        websocket: WebSocket,
        payload: Dict[str, Any],
        request_id: Optional[str]
    ):
        """Handle apply request."""
        try:
            request = ApplyRequest.model_validate(payload)
            result = await self.handler.handle_apply(request)
            
            await self._send(websocket, {
                "type": "execution_update" if not isinstance(result, ErrorResponse) else "error",
                "payload": result.model_dump(),
                "request_id": request_id,
            })
        
        except Exception as e:
            await self._send_error(websocket, str(e), "APPLY_ERROR", request_id)
    
    async def _handle_reject(
        self,
        websocket: WebSocket,
        payload: Dict[str, Any],
        request_id: Optional[str]
    ):
        """Handle reject request."""
        try:
            request = RejectRequest.model_validate(payload)
            result = await self.handler.handle_reject(request)
            
            await self._send(websocket, {
                "type": "execution_update" if not isinstance(result, ErrorResponse) else "error",
                "payload": result.model_dump(),
                "request_id": request_id,
            })
        
        except Exception as e:
            await self._send_error(websocket, str(e), "REJECT_ERROR", request_id)
    
    async def _send(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send a message over WebSocket."""
        await websocket.send_json(message)
    
    async def _send_error(
        self,
        websocket: WebSocket,
        error: str,
        error_code: str,
        request_id: Optional[str] = None
    ):
        """Send an error message."""
        await self._send(websocket, {
            "type": "error",
            "payload": {
                "error": error,
                "error_code": error_code,
            },
            "request_id": request_id,
        })


async def websocket_endpoint(websocket: WebSocket, workspace_id: str):
    """
    FastAPI WebSocket endpoint handler.
    
    Usage:
    @app.websocket("/ws/{workspace_id}")
    async def ws_handler(websocket: WebSocket, workspace_id: str):
        await websocket_endpoint(websocket, workspace_id)
    """
    handler = WebSocketHandler()
    
    await handler.connect(websocket, workspace_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            await handler.handle_message(websocket, data, workspace_id)
    
    except WebSocketDisconnect:
        handler.disconnect(workspace_id)
    
    except Exception as e:
        logger.error("websocket_error", workspace_id=workspace_id, error=str(e))
        handler.disconnect(workspace_id)

