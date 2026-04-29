"""Server-Sent Events (SSE) for real-time pipeline progress.

Provides ``GET /events/{job_id}`` which streams progress updates as the
PlanExecutor works through GENERATE → VALIDATE → PREVIEW → APPLY.

Each SSE event is a JSON object with at minimum:
  - ``type``     — event category (pipeline_start, step_start, generate,
                   validate, diff, apply, step_complete, pipeline_complete,
                   pipeline_error, heartbeat).
  - ``message``  — human-readable status string.
  - ``state``    — current PlanExecutionState.

The frontend (or VS Code extension) connects to this endpoint immediately
after creating an async job and receives live updates without polling.

Usage::

    const es = new EventSource('/api/v1/events/<jobId>');
    es.onmessage = (e) => console.log(JSON.parse(e.data));
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

import structlog

logger = structlog.get_logger("events")

router = APIRouter()

_event_queues: Dict[str, asyncio.Queue] = {}

_HEARTBEAT_INTERVAL = 5.0
_MAX_IDLE_SECONDS = 120.0


def get_or_create_queue(job_id: str) -> asyncio.Queue:
    """Get the event queue for a job, creating it if needed."""
    if job_id not in _event_queues:
        _event_queues[job_id] = asyncio.Queue()
    return _event_queues[job_id]


def push_event(job_id: str, event: Dict[str, Any]) -> None:
    """Push an event to a job's queue (non-blocking).

    Called by the PlanExecutor's status_callback during pipeline execution.
    If no SSE client is listening, events are silently dropped.
    """
    q = _event_queues.get(job_id)
    if q is None:
        return
    try:
        q.put_nowait(event)
    except asyncio.QueueFull:
        pass


def cleanup_queue(job_id: str) -> None:
    """Remove a job's event queue after the SSE stream ends."""
    _event_queues.pop(job_id, None)


def make_status_callback(job_id: str):
    """Create a callback function that pushes events to the SSE queue.

    Returns a callable suitable for ``PlanExecutor(status_callback=...)``.
    """
    get_or_create_queue(job_id)

    def _callback(event: Dict[str, Any]) -> None:
        push_event(job_id, event)

    return _callback


async def _event_stream(job_id: str) -> AsyncGenerator[dict, None]:
    """Async generator that yields SSE events for a job.

    Sends heartbeats every 5s to keep the connection alive.
    Terminates when a ``pipeline_complete`` or ``pipeline_error`` event
    is received, or after 120s of inactivity.
    """
    q = get_or_create_queue(job_id)
    last_activity = time.monotonic()

    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=_HEARTBEAT_INTERVAL)
                last_activity = time.monotonic()

                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event),
                }

                if event.get("type") in ("pipeline_complete", "pipeline_error"):
                    break

            except asyncio.TimeoutError:
                if time.monotonic() - last_activity > _MAX_IDLE_SECONDS:
                    yield {
                        "event": "timeout",
                        "data": json.dumps({
                            "type": "timeout",
                            "message": "Stream timed out after inactivity",
                        }),
                    }
                    break

                yield {
                    "event": "heartbeat",
                    "data": json.dumps({
                        "type": "heartbeat",
                        "message": "keepalive",
                        "timestamp": time.time(),
                    }),
                }
    finally:
        cleanup_queue(job_id)


@router.get("/events/{job_id}")
async def stream_job_events(job_id: str):
    """Stream real-time progress events for an async refactor job.

    Returns an SSE (Server-Sent Events) stream.  Connect immediately
    after creating a job via ``POST /refactor/jobs`` to receive live
    updates as the pipeline runs.

    Event types:
      - ``pipeline_start``    — pipeline has begun.
      - ``step_start``        — a pipeline step is starting (with progress %).
      - ``generate``          — code generation progress.
      - ``generate_complete`` — code generation finished (affected files list).
      - ``validate``          — syntax validation progress (per file).
      - ``diff``              — diff generation progress (per file, streamable).
      - ``apply``             — file write progress (per file).
      - ``step_complete``     — a pipeline step finished.
      - ``pipeline_complete`` — pipeline finished successfully.
      - ``pipeline_error``    — pipeline failed (error details).
      - ``heartbeat``         — keepalive every 5s.
    """
    return EventSourceResponse(_event_stream(job_id))
