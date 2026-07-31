"""Orchestrator runner that drives the main agent and yields typed SSE events.

Mirrors both reference scripts:
- `extra_doc/08 subagent/agent.py` (fresh SubAgent orchestration), and
- `extra_doc/09 fork/agent.py` (session resume + fork branching).

Supports three session modes via `ClaudeAgentOptions`:
- fresh:  full options with `agents` + `mcp_servers` (08 pattern).
- resume: `ClaudeAgentOptions(resume=session_id)` - the SDK rehydrates the
  prior SubAgent/Skill/PDF context from the stored session.
- fork:   `resume=session_id, fork_session=True` - the SDK clones the session
  into a new branch; the original stays untouched so analysts can explore
  alternative investment logic in parallel.

The terminal `ResultMessage` carries a `session_id` (new for fresh/fork, same
for resume); we attach it to the `final_result` event so the frontend can offer
resume / fork actions on the active thread.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    StreamEvent,
    UserMessage,
)
from claude_agent_sdk.types import TextBlock, ToolResultBlock, ToolUseBlock

from backend.agents.hooks import build_hooks
from backend.agents.registry import agents_config
from backend.agents.telemetry import build_otel_env
from backend.config import DISCLAIMER
from backend.mcp.websearch import websearch_server

logger = logging.getLogger(__name__)

SessionMode = Literal["fresh", "resume", "fork"]

# Tools the orchestrator itself is allowed to use. Vertical work is delegated
# to SubAgents via the built-in `Agent` tool, which keeps the orchestrator
# context clean (the core context-isolation benefit of the design).
ORCHESTRATOR_TOOLS = [
    "Read",
    "Grep",
    "Glob",
    "Agent",
    "AskUserQuestion",
    "mcp__websearch__bochasearch",
]

# Default turn cap for forked runs, matching the 09 fork reference script.
DEFAULT_FORK_MAX_TURNS = 5


def _agent_label(parent_tool_use_id: str | None, id_to_agent: dict[str, str]) -> str:
    """Resolve which SubAgent produced a message.

    Messages with a `parent_tool_use_id` come from a SubAgent invocation; we
    map that id back to the SubAgent name captured when the Agent tool was
    called. Messages without it come from the orchestrator.
    """
    if parent_tool_use_id and parent_tool_use_id in id_to_agent:
        return id_to_agent[parent_tool_use_id]
    return "orchestrator"


class _RunContext:
    """Mutable per-run state shared across `_translate` calls.

    Tracks the Agent-tool lifecycle so events can be attributed correctly:

    - `id_to_agent`: Agent tool_use_id -> SubAgent name (captured at dispatch).
    - `pending_agents`: tool_use_ids dispatched but not yet finished. The CLI
      does NOT set `parent_tool_use_id` on StreamEvents, so while a SubAgent
      is in flight we attribute orphan stream deltas to the most recently
      dispatched pending SubAgent (the orchestrator is blocked waiting for
      the Agent tool result, so it cannot be producing text concurrently).
    - `completed_agents`: SubAgents whose `subagent_result` was emitted, so
      the two emission paths (final AssistantMessage vs Agent tool_result)
      cannot double-emit.
    """

    def __init__(self) -> None:
        self.id_to_agent: dict[str, str] = {}
        self.pending_agents: list[str] = []
        self.completed_agents: set[str] = set()

    def stream_label(self, parent_tool_use_id: str | None) -> str:
        """Attribute a StreamEvent that may lack `parent_tool_use_id`."""
        if parent_tool_use_id and parent_tool_use_id in self.id_to_agent:
            return self.id_to_agent[parent_tool_use_id]
        if self.pending_agents:
            return self.id_to_agent.get(self.pending_agents[-1], "orchestrator")
        return "orchestrator"


def _build_options(
    session_id: str | None,
    mode: SessionMode,
    max_turns: int | None,
    enduser_id: str = "",
    tenant_id: str = "",
) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for the requested session mode.

    - fresh: full wiring (agents + MCP) + an explicit `session_id` so the SDK
      persists the conversation to disk and resume/fork can locate it later.
      Without an explicit session_id, the SDK may keep the conversation in a
      temporary session that cannot be resumed.
    - resume: only `resume` + `allowed_tools`; the SDK restores agents/MCP from
      the stored session (per the 09 fork reference's `run_resume`).
    - fork: `resume` + `fork_session=True` + `max_turns` cap; the SDK clones
      the session into a new branch with a fresh session_id.

    Telemetry env (``build_otel_env``) and governance hooks (``build_hooks``)
    are injected into the shared ``common`` dict so all three session modes
    carry the same observability configuration and guardrails.
    """
    common = {
        "include_partial_messages": True,
        "allowed_tools": ORCHESTRATOR_TOOLS,
        # Headless backend: no human is present to approve tool prompts, so
        # auto-approve all tool calls (orchestrator + SubAgents). Without
        # this, SubAgent tool use (Read/Bash/...) stalls waiting for an
        # approval that can never arrive and the CLI exits with an error.
        "permission_mode": "bypassPermissions",
        # Governance hook set: PreToolUse guardrail, PostToolUse* audit trail,
        # SubagentStart/Stop lifecycle logging, Stop archival. Shared by all
        # session modes so fresh/resume/fork runs are governed identically.
        "hooks": build_hooks(),
        # OpenTelemetry env: traces/metrics/log-events exported via OTLP when
        # OTEL_EXPORTER_OTLP_ENDPOINT is configured; empty dict when unset.
        # Orthogonal to session mode, like governance hooks.
        "env": build_otel_env(enduser_id=enduser_id, tenant_id=tenant_id),
    }

    if mode == "fresh":
        return ClaudeAgentOptions(
            session_id=session_id,  # required for SDK session persistence
            mcp_servers={"websearch": websearch_server},
            agents=agents_config,
            **common,
        )

    if mode == "resume":
        # The reference passes only resume + allowed_tools; the SDK rehydrates
        # the rest from the stored session file.
        return ClaudeAgentOptions(
            resume=session_id,
            **common,
        )

    # fork
    return ClaudeAgentOptions(
        resume=session_id,
        fork_session=True,  # clone the session into an isolated branch
        max_turns=max_turns or DEFAULT_FORK_MAX_TURNS,
        **common,
    )


async def run_research(
    prompt: str,
    session_id: str | None = None,
    mode: SessionMode = "fresh",
    max_turns: int | None = None,
    enduser_id: str = "",
    tenant_id: str = "",
) -> AsyncIterator[dict[str, Any]]:
    """Run the orchestrator and yield typed SSE event dicts.

    Yields events of shape:
      {"type": "...", "agent": "...", "data": {...}}
    where type is one of: subagent_dispatch, partial_message, tool_call,
    subagent_result, final_result, error, done.

    For fresh runs, we generate a stable UUID and pass it as `session_id` so
    the SDK persists the conversation. The terminal `ResultMessage` returns
    the same id for resume, or a new id for fork; we attach it to the
    `final_result` event so the frontend can offer resume / fork actions.

    `enduser_id` / `tenant_id` are forwarded to `build_otel_env()` so OTel
    spans/metrics/log-events carry per-user/tenant cost attribution labels.
    """
    # Fresh runs need an explicit session_id for SDK persistence; resume/fork
    # use the id provided by the caller.
    effective_session_id = session_id or (
        str(uuid.uuid4()) if mode == "fresh" else None
    )
    options = _build_options(
        effective_session_id, mode, max_turns,
        enduser_id=enduser_id, tenant_id=tenant_id,
    )

    # Per-run attribution state (Agent dispatch map, pending SubAgents, etc.).
    ctx = _RunContext()

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for msg in client.receive_response():
                # Translate each SDK message into one or more SSE events.
                async for event in _translate(msg, ctx):
                    yield event
    except Exception as exc:  # noqa: BLE001 - surface any failure to the client.
        logger.exception("Orchestrator run failed")
        yield {
            "type": "error",
            "agent": "orchestrator",
            "data": {"message": str(exc)},
        }
        return

    # Signal completion so the SSE endpoint can close the stream cleanly.
    yield {"type": "done", "agent": "orchestrator", "data": {}}


async def _translate(
    msg: Any, ctx: _RunContext
) -> AsyncIterator[dict[str, Any]]:
    """Convert a single SDK message into typed SSE events."""
    # Terminal result message -> emit the aggregated final report.
    if isinstance(msg, ResultMessage):
        report = msg.result or ""
        # Capture the SDK session_id so the frontend can resume / fork. For
        # fresh/resume this is the same id we passed in; for fork it is the
        # new branch id generated by the SDK.
        session_id = getattr(msg, "session_id", None)
        if msg.is_error:
            yield {
                "type": "error",
                "agent": "orchestrator",
                "data": {"message": report or "run ended with an error"},
            }
        else:
            yield {
                "type": "final_result",
                "agent": "orchestrator",
                "data": {
                    "report": report,
                    "disclaimer": DISCLAIMER,
                    "session_id": session_id or "",
                },
            }
        return

    # Tool results arrive as UserMessages. The result whose tool_use_id matches
    # a dispatched Agent call IS the SubAgent's final report (SubAgent-as-tool
    # pattern) -> emit subagent_result and close the pending entry. Results of
    # a SubAgent's INTERNAL tools have unknown tool_use_ids and are ignored.
    if isinstance(msg, UserMessage):
        if isinstance(msg.content, list):
            for block in msg.content:
                if not isinstance(block, ToolResultBlock):
                    continue
                if block.tool_use_id not in ctx.id_to_agent:
                    continue
                agent = ctx.id_to_agent[block.tool_use_id]
                if block.tool_use_id in ctx.pending_agents:
                    ctx.pending_agents.remove(block.tool_use_id)
                if agent in ctx.completed_agents:
                    continue
                text = _clean_subagent_report(_extract_tool_result_text(block.content))
                if text:
                    ctx.completed_agents.add(agent)
                    yield {
                        "type": "subagent_result",
                        "agent": agent,
                        "data": {"markdown": text, "disclaimer": DISCLAIMER},
                    }
        return

    if not isinstance(msg, AssistantMessage):
        # Fine-grained streaming: forward raw text deltas as partial_message
        # events so the browser renders token-by-token output. SDK content
        # blocks are dataclasses WITHOUT a `.type` discriminator (TextBlock,
        # ToolUseBlock, ...), so complete AssistantMessages alone cannot drive
        # live streaming; the Anthropic API stream events carry the deltas.
        # StreamEvents lack parent_tool_use_id, so attribute via the pending
        # SubAgent stack (orchestrator is blocked while a SubAgent runs).
        if isinstance(msg, StreamEvent):
            event = msg.event or {}
            if event.get("type") == "content_block_delta":
                delta = event.get("delta") or {}
                if delta.get("type") == "text_delta":
                    text = delta.get("text") or ""
                    if text:
                        yield {
                            "type": "partial_message",
                            "agent": ctx.stream_label(msg.parent_tool_use_id),
                            "data": {"text": text},
                        }
        # Other non-assistant messages (system notifications, non-text stream
        # events) are ignored.
        return

    agent = _agent_label(msg.parent_tool_use_id, ctx.id_to_agent)

    for block in msg.content:
        if isinstance(block, TextBlock):
            text = block.text or ""
            if not text:
                continue
            # Fallback subagent_result path: a SubAgent's final message
            # (stop_reason "end_turn") carries its complete report. The Agent
            # tool_result above is the primary path; this covers SDK versions
            # where the tool_result content is empty. Guarded against
            # double-emitting via completed_agents. Intermediate text was
            # already streamed as partial_message deltas.
            if (
                agent != "orchestrator"
                and msg.stop_reason == "end_turn"
                and agent not in ctx.completed_agents
            ):
                ctx.completed_agents.add(agent)
                yield {
                    "type": "subagent_result",
                    "agent": agent,
                    "data": {"markdown": text, "disclaimer": DISCLAIMER},
                }

        elif isinstance(block, ToolUseBlock):
            tool_name = block.name
            tool_input = block.input or {}
            tool_id = block.id
            # An Agent tool call dispatches a SubAgent. Capture the mapping so
            # later child messages can be attributed to the right SubAgent.
            if tool_name == "Agent":
                sub_name = _extract_agent_name(tool_input)
                if sub_name and tool_id:
                    ctx.id_to_agent[tool_id] = sub_name
                    ctx.pending_agents.append(tool_id)
                yield {
                    "type": "subagent_dispatch",
                    "agent": sub_name or "unknown",
                    "data": {"prompt": str(tool_input.get("prompt", ""))},
                }
            else:
                yield {
                    "type": "tool_call",
                    "agent": agent,
                    "data": {"tool": tool_name, "input": tool_input},
                }

        # ThinkingBlock / server-tool blocks are not surfaced as separate
        # events to keep the stream focused on assistant reasoning; they are
        # reflected in the subsequent stream deltas.


def _extract_tool_result_text(content: Any) -> str:
    """Flatten a ToolResultBlock payload into plain text.

    The SDK types the content as `str | list[dict] | None`; list entries are
    Anthropic content blocks (e.g. {"type": "text", "text": "..."}).
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(part for part in parts if part)
    return ""


# CLI-internal metadata appended to Agent tool results, e.g.
#   "\nagentId: a8f3... (use SendMessage with to: 'a8f3...', ...)"
#   "\n<usage>subagent_tokens: 3654\ntool_uses: 0\nduration_ms: 5793</usage>"
# These are control-protocol noise for the CLI's own agent-to-agent messaging,
# not analyst-facing content, so strip them before emitting subagent_result.
_AGENT_ID_TRAILER_RE = re.compile(r"\n?agentId: [0-9a-f]+ \(use SendMessage.*?\)\s*", re.DOTALL)
_USAGE_TRAILER_RE = re.compile(r"\n?<usage>.*?</usage>\s*", re.DOTALL)


def _clean_subagent_report(text: str) -> str:
    """Strip CLI agent-protocol trailers from a SubAgent's final report."""
    text = _AGENT_ID_TRAILER_RE.sub("\n", text)
    text = _USAGE_TRAILER_RE.sub("\n", text)
    return text.strip()


def _extract_agent_name(tool_input: dict[str, Any]) -> str:
    """Best-effort extraction of the SubAgent name from an Agent tool call.

    The SDK's Agent tool input uses one of a few common field names for the
    target SubAgent; check them in priority order.
    """
    for key in ("agent", "subagent_type", "name", "subagent"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""
