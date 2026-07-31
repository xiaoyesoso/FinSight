"""SSE stream endpoint.

`GET /api/research/{run_id}/stream` consumes typed events from the run's
queue and emits them as Server-Sent Events. The `X-Accel-Buffering: no`
header disables proxy buffering so partial messages reach the browser live.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.api.research import run_manager

router = APIRouter()


async def _event_stream(run_id: str, request: Request) -> Any:
    """Yield SSE-formatted strings from the run's event queue.

    Stops when the client disconnects or when the `None` sentinel is pushed
    by the background driver (meaning the run finished).
    """
    queue = run_manager.queue(run_id)
    try:
        while True:
            # Honor client disconnects so we stop streaming to closed tabs.
            if await request.is_disconnected():
                break

            event = await queue.get()
            if event is None:
                # Sentinel: the background driver finished the run.
                break

            event_type = event.get("type", "message")
            payload = {
                "run_id": run_id,
                "agent": event.get("agent", "orchestrator"),
                "type": event_type,
                "data": event.get("data", {}),
            }
            yield f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
    finally:
        # Clean up the in-memory run once the stream ends.
        run_manager.remove(run_id)


@router.get("/research/{run_id}/stream")
async def stream_research(run_id: str, request: Request) -> StreamingResponse:
    """Return an SSE stream of typed events for the given run."""
    # Validate the run exists (raises 404 via run_manager.queue).
    run_manager.queue(run_id)

    return StreamingResponse(
        _event_stream(run_id, request),
        media_type="text/event-stream",
        # Disable buffering by reverse proxies (nginx) for live streaming.
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
