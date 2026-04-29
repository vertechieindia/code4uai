"""Real-time Collaboration API — multiplayer editing.

Endpoints:
  - ``POST /collab/join``          — join a file editing session
  - ``POST /collab/leave``         — leave a session
  - ``POST /collab/op``            — apply an edit operation
  - ``GET  /collab/doc``           — get document state + participants
  - ``GET  /collab/ops``           — get operations since a Lamport clock
  - ``GET  /collab/active``        — list all active collaboration sessions
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from code4u.core.collaboration import (
    CollaborationDocument,
    Operation,
    OpType,
    ParticipantType,
    get_collaboration_manager,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class JoinRequest(BaseModel):
    filePath: str = Field(..., description="Path of the file to edit collaboratively.")
    participantId: str = Field(..., description="Unique ID of the participant (user or agent).")
    name: str = Field("Anonymous", description="Display name.")
    type: str = Field("human", description="Participant type: human | agent.")
    initialContent: str = Field("", description="Initial file content (if opening for the first time).")


class LeaveRequest(BaseModel):
    filePath: str
    participantId: str


class OpRequest(BaseModel):
    filePath: str
    participantId: str
    type: str = Field("insert", description="Operation type: insert | delete | replace | cursor.")
    offset: int = Field(0, description="Character offset in the document.")
    text: str = Field("", description="Text to insert or replace.")
    length: int = Field(0, description="Number of characters to delete or replace.")
    line: int = Field(0, description="Cursor line (for cursor ops).")
    col: int = Field(0, description="Cursor column (for cursor ops).")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/collab/join")
async def join_session(request: JoinRequest) -> Dict[str, Any]:
    """Join a collaborative editing session for a file."""
    mgr = get_collaboration_manager()
    ptype = ParticipantType.AGENT if request.type == "agent" else ParticipantType.HUMAN
    doc = mgr.get_or_create(request.filePath, request.initialContent)
    participant = doc.join(request.participantId, request.name, ptype)

    return {
        "status": "joined",
        "filePath": request.filePath,
        "participant": {
            "id": participant.id,
            "name": participant.name,
            "color": participant.color,
            "type": participant.type.value,
        },
        "participants": doc.get_participants(),
        "contentLength": len(doc.content),
    }


@router.post("/collab/leave")
async def leave_session(request: LeaveRequest) -> Dict[str, Any]:
    """Leave a collaborative editing session."""
    mgr = get_collaboration_manager()
    doc = mgr.get(request.filePath)
    if not doc:
        raise HTTPException(status_code=404, detail="No active session for this file")
    left = doc.leave(request.participantId)
    if doc.participant_count == 0:
        mgr.close(request.filePath)
    return {"status": "left" if left else "not_found", "remainingParticipants": doc.participant_count if doc else 0}


@router.post("/collab/op")
async def apply_operation(request: OpRequest) -> Dict[str, Any]:
    """Apply an edit operation to a collaborative document."""
    mgr = get_collaboration_manager()
    doc = mgr.get(request.filePath)
    if not doc:
        raise HTTPException(status_code=404, detail="No active session for this file")

    try:
        op_type = OpType(request.type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid operation type: {request.type}")

    op = Operation(
        type=op_type,
        participant_id=request.participantId,
        offset=request.offset,
        text=request.text,
        length=request.length,
        line=request.line,
        col=request.col,
    )

    resolved = doc.apply_operation(op)

    return {
        "status": "applied",
        "operation": resolved.to_dict(),
        "lamport": resolved.lamport,
        "contentLength": len(doc.content),
    }


@router.get("/collab/doc")
async def get_document(filePath: str) -> Dict[str, Any]:
    """Get the current document state and participants."""
    mgr = get_collaboration_manager()
    doc = mgr.get(filePath)
    if not doc:
        raise HTTPException(status_code=404, detail="No active session for this file")

    return {
        "filePath": doc.file_path,
        "content": doc.content,
        "participants": doc.get_participants(),
        "lamport": doc._lamport,
        "operationCount": len(doc._operations),
    }


@router.get("/collab/ops")
async def get_operations(filePath: str, since: int = 0) -> Dict[str, Any]:
    """Get operations since a given Lamport timestamp."""
    mgr = get_collaboration_manager()
    doc = mgr.get(filePath)
    if not doc:
        raise HTTPException(status_code=404, detail="No active session for this file")

    return {
        "filePath": filePath,
        "operations": doc.get_operations(since_lamport=since),
        "currentLamport": doc._lamport,
    }


@router.get("/collab/active")
async def list_active_sessions() -> Dict[str, Any]:
    """List all active collaboration sessions."""
    mgr = get_collaboration_manager()
    return {
        "sessions": mgr.list_active(),
        "totalActive": mgr.active_count,
    }
