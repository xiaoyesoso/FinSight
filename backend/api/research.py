"""Research task submission endpoint with an in-memory run manager.

`POST /api/research` creates a run, starts the orchestrator as a background
task that pushes typed events onto an asyncio.Queue, and returns the `run_id`.
The companion SSE endpoint in `sse.py` consumes events from the same queue.

Supports three session modes (per the 09 fork reference design):
- fresh:  a brand-new orchestrator run with full SubAgent + MCP wiring.
- resume: continue an existing SDK session (full context reuse).
- fork:   clone an existing session into an isolated branch (new session_id).
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.orchestrator import run_research
from backend.config import DISCLAIMER, settings

router = APIRouter()

SessionMode = Literal["fresh", "resume", "fork"]


@dataclass
class SessionInfo:
    """In-memory record linking a run to its SDK session and lineage.

    - `session_id` is captured from the terminal `ResultMessage` during the
      run and may be updated mid-flight (fork produces a new id).
    - `parent_session_id` is set only for fork runs, so the UI can render
      the branch lineage (A -> A').
    """

    session_id: str | None = None
    parent_session_id: str | None = None
    mode: SessionMode = "fresh"


class ResearchRequest(BaseModel):
    """Body for POST /api/research.

    - `mode` defaults to "fresh"; `session_id` is REQUIRED for resume/fork
      and ignored for fresh.
    - `file_id`/`agents` only apply to fresh runs (a resumed session already
      knows its PDF path and SubAgent routing from prior turns).
    - `max_turns` is fork-only and caps the branch's turn count (default 5,
      matching the 09 fork reference).
    - `user_id`/`tenant_id` are optional OpenTelemetry attribution labels;
      when set, every span/metric/log-event carries them for per-user /
      per-tenant cost rollups in Grafana.
    """

    prompt: str
    file_id: str | None = None
    agents: list[str] | None = None
    session_id: str | None = None
    mode: SessionMode = "fresh"
    max_turns: int | None = None
    user_id: str | None = None
    tenant_id: str | None = None


class ResearchResponse(BaseModel):
    run_id: str
    disclaimer: str


class RunManager:
    """In-memory store mapping run_id -> asyncio.Queue + session metadata.

    v1 is single-instance and ephemeral: runs vanish on restart. SDK sessions
    themselves persist on local disk (so resume/fork survive a restart), but
    the in-memory lineage map does not.
    """

    def __init__(self) -> None:
        self._runs: dict[str, asyncio.Queue[dict[str, Any] | None]] = {}
        # Side-table tracking session_id + lineage per run. Kept separate from
        # the queue so the SSE consumer does not need to know about sessions.
        self._sessions: dict[str, SessionInfo] = {}

    def create(
        self,
        mode: SessionMode = "fresh",
        parent_session_id: str | None = None,
    ) -> str:
        """Register a new run and return its id.

        For fork runs, `parent_session_id` is the session being branched from;
        it is stored on the SessionInfo so the final_result event can carry
        lineage metadata for the UI.
        """
        run_id = uuid.uuid4().hex
        self._runs[run_id] = asyncio.Queue()
        self._sessions[run_id] = SessionInfo(
            parent_session_id=parent_session_id,
            mode=mode,
        )
        return run_id

    def queue(self, run_id: str) -> asyncio.Queue[dict[str, Any] | None]:
        """Return the event queue for a run, raising 404 if unknown."""
        if run_id not in self._runs:
            raise HTTPException(status_code=404, detail="run_id not found")
        return self._runs[run_id]

    def session(self, run_id: str) -> SessionInfo:
        """Return the session metadata for a run, raising 404 if unknown."""
        if run_id not in self._sessions:
            raise HTTPException(status_code=404, detail="run_id not found")
        return self._sessions[run_id]

    def set_session_id(self, run_id: str, session_id: str) -> None:
        """Record the SDK session_id captured from a ResultMessage.

        Called by the background driver once the orchestrator finishes (or
        when a fork produces the new branch session_id).
        """
        info = self._sessions.get(run_id)
        if info is not None:
            info.session_id = session_id

    def find_run_by_session(self, session_id: str) -> str | None:
        """Best-effort lookup: find the run_id that produced a session_id.

        Used to validate resume/fork requests against sessions this backend
        instance knows about. Returns None for sessions created elsewhere
        (e.g. before a restart); callers still pass them through to the SDK.
        """
        for run_id, info in self._sessions.items():
            if info.session_id == session_id:
                return run_id
        return None

    def remove(self, run_id: str) -> None:
        """Drop a finished run from memory."""
        self._runs.pop(run_id, None)
        self._sessions.pop(run_id, None)


# Shared singleton used by both the research and SSE endpoints.
run_manager = RunManager()


def _build_prompt(req: ResearchRequest) -> str:
    """Augment the user prompt with file path and explicit SubAgent routing.

    Only applies to fresh runs: a resumed/forked session already knows its
    PDF path and SubAgent routing from prior turns, so we pass the prompt as-is.

    Explicit routing matches the reference script's `必须使用子agent` pattern:
    some models (e.g. MiniMax) otherwise prefer to call Skills directly,
    which defeats the parallel SubAgent design.
    """
    if req.mode != "fresh":
        # Resume/fork: the session already has context; just send the follow-up.
        return req.prompt

    parts: list[str] = []

    if req.agents:
        # Force the orchestrator to dispatch named SubAgents.
        names = "、".join(req.agents)
        parts.append(f"必须使用以下子agent完成任务，不能自行调用skills：{names}。")

    parts.append(req.prompt)

    if req.file_id:
        # Resolve the uploaded PDF path for the financial SubAgent.
        path = f"{settings.upload_dir}/{req.file_id}.pdf"
        parts.append(
            f"财报PDF文件路径为：{path}（请使用 financial-analyzer agent 读取并分析）。"
        )

    return "\n".join(parts)


async def _drive_run(
    run_id: str,
    prompt: str,
    session_id: str | None,
    mode: SessionMode,
    max_turns: int | None,
    enduser_id: str = "",
    tenant_id: str = "",
) -> None:
    """Background task: run the orchestrator and forward events to the queue.

    When the orchestrator finishes, the SDK session_id captured from the
    terminal `ResultMessage` is stored on the run's `SessionInfo` (via
    `run_manager.set_session_id`) and attached to the `final_result` event
    so the frontend can offer resume / fork actions.

    A `None` sentinel is pushed at the end to signal the SSE consumer that the
    stream is complete.
    """
    queue = run_manager._runs.get(run_id)
    if queue is None:
        return
    try:
        async for event in run_research(
            prompt,
            session_id=session_id,
            mode=mode,
            max_turns=max_turns,
            enduser_id=enduser_id,
            tenant_id=tenant_id,
        ):
            # If the orchestrator captured a session_id on final_result, mirror
            # it into the RunManager so later resume/fork requests can find it,
            # and attach lineage metadata (parent_session_id) for fork runs.
            if event.get("type") == "final_result":
                data = event.get("data", {})
                sid = data.get("session_id")
                if sid:
                    run_manager.set_session_id(run_id, sid)
                # For fork runs, attach the parent session so the UI can show
                # the branch lineage (A -> A').
                info = run_manager.session(run_id)
                if info.parent_session_id:
                    data["parent_session_id"] = info.parent_session_id
                    event["data"] = data
            await queue.put(event)
    except Exception as exc:  # noqa: BLE001 - never let the task die silently.
        await queue.put(
            {"type": "error", "agent": "orchestrator", "data": {"message": str(exc)}}
        )
    finally:
        # Sentinel: tells the SSE consumer to close the stream.
        await queue.put(None)


@router.post("/research", response_model=ResearchResponse, status_code=202)
async def create_research(req: ResearchRequest) -> ResearchResponse:
    """Create a research run and start streaming in the background.

    Dispatches to one of three session modes:
    - fresh:  full orchestrator + SubAgents + MCP (default).
    - resume: continue `session_id` in place (full context reuse).
    - fork:   clone `session_id` into a new branch (new session_id returned).
    """
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    # Validate session-mode requirements.
    if req.mode in ("resume", "fork"):
        if not req.session_id:
            raise HTTPException(
                status_code=400,
                detail=f"session_id is required for mode '{req.mode}'",
            )
        # Best-effort lineage check. We do NOT 422 on unknown sessions because
        # SDK sessions persist on local disk and survive backend restarts; the
        # in-memory map is just for display lineage.
        parent_session_id = req.session_id if req.mode == "fork" else None
    else:
        # Fresh runs ignore session_id even if one was sent.
        parent_session_id = None

    run_id = run_manager.create(mode=req.mode, parent_session_id=parent_session_id)
    prompt = _build_prompt(req)

    # Kick off the orchestrator as a background task on the running loop.
    asyncio.create_task(
        _drive_run(
            run_id,
            prompt,
            session_id=req.session_id,
            mode=req.mode,
            max_turns=req.max_turns,
            enduser_id=req.user_id or "",
            tenant_id=req.tenant_id or "",
        )
    )

    return ResearchResponse(run_id=run_id, disclaimer=DISCLAIMER)
