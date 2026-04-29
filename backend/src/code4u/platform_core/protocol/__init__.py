from __future__ import annotations
"""VS Code Extension ↔ Backend Protocol for code4u.ai.

This is NOT REST spam.
It's a contracted execution protocol.

Transport:
- HTTPS + mTLS
- WebSocket for streaming diffs
- Strict request schemas

The IDE never executes anything automatically.
"""
from code4u.platform_core.protocol.messages import (
    IntentRequest,
    ExecutionUpdate,
    DiffPayload,
    ApplyRequest,
    RejectRequest,
    ErrorResponse,
)
from code4u.platform_core.protocol.handler import ProtocolHandler
from code4u.platform_core.protocol.websocket import WebSocketHandler

__all__ = [
    "IntentRequest",
    "ExecutionUpdate",
    "DiffPayload",
    "ApplyRequest",
    "RejectRequest",
    "ErrorResponse",
    "ProtocolHandler",
    "WebSocketHandler",
]

