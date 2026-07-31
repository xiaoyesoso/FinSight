"""Governance hooks for the headless orchestrator.

Mirrors the Hooks reference (`extra_doc/扩展：Hooks 机制的实战应用.docx`):
- PreToolUse guardrail: auto-allow read-only tools, deny dangerous writes/commands.
- PostToolUse / PostToolUseFailure audit logger: JSONL trail per tool call.
- SubagentStart / SubagentStop tracker: per-SubAgent lifecycle + transcript path.
- Stop archiver: session-end extension point.

All comments are in English (project rule).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk.types import (
    HookCallback,
    HookContext,
    HookInput,
    HookMatcher,
    PostToolUseFailureHookInput,
    PostToolUseHookInput,
    PreToolUseHookInput,
    StopHookInput,
    SubagentStartHookInput,
    SubagentStopHookInput,
)

logger = logging.getLogger(__name__)

# Ensure hook logs are visible when the backend is run directly (no logging
# config provided by uvicorn by default).
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")

# Audit log path: gitignored runtime data; one JSON Lines record per tool call.
AUDIT_LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "audit_log.jsonl"

# Maximum length for the free-form tool output summary stored in the audit log.
# Full tool outputs can be huge (file reads, search results), so only a prefix is
# persisted; the complete output remains available in the CLI transcript.
MAX_AUDIT_OUTPUT_SUMMARY = 500

# Read-only tools that run in every research session and never mutate state.
# Auto-approving them keeps the headless flow fast and quiet.
READONLY_TOOLS = {"Read", "Glob", "Grep"}

# Dangerous Bash substrings that are never legitimate in investment research.
# These are deliberately conservative; legitimate Skills never emit them.
DANGEROUS_BASH_PATTERNS = (
    r"rm\s+-rf\s+/",
    r"mkfs\.",
    r":\(\)\s*\{\s*:\|\:\s*&\s*\}",  # fork bomb
    r">\s*/dev/(sda|sd[b-z]|nvme|disk)",
    r"dd\s+if=.*of=/dev/",
)

# Paths that must never be written/edited by an autonomous agent.
PROTECTED_PATH_PREFIXES = ("/etc", "/sys", "/proc", "C:\\\\Windows")
PROTECTED_FILE_NAMES = {".env"}


# ---------------------------------------------------------------------------
# PreToolUse guardrail
# ---------------------------------------------------------------------------
async def pre_tool_guard(
    input_data: HookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Layered permission guard for headless agent runs.

    Returns:
        - allow: for read-only tools.
        - deny: for protected-file writes or destructive Bash commands.
        - {}: for anything else, letting the SDK fall back to its default.
    """
    if input_data.get("hook_event_name") != "PreToolUse":
        return {}

    data = PreToolUseHookInput(input_data)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}

    # Fast path: read-only tools are safe and extremely common.
    if tool_name in READONLY_TOOLS:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "read-only tool",
            }
        }

    # Deny writes to protected files / system directories.
    if tool_name in {"Write", "Edit", "MultiEdit"}:
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        if _is_protected_path(str(file_path)):
            reason = f"{tool_name} on protected path is not allowed in headless mode"
            logger.warning("Guard denied %s %s: %s", tool_name, file_path, reason)
            return _deny(reason)

    # Deny destructive Bash commands.
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if _is_dangerous_command(str(command)):
            reason = "destructive Bash command blocked"
            logger.warning("Guard denied Bash command: %s", command)
            return _deny(reason)

    # Everything else falls through. In headless mode there is no human to ask,
    # so we intentionally do NOT return "ask"; the SDK will resolve the default.
    return {}


def _deny(reason: str) -> dict[str, Any]:
    """Build a headless-safe deny decision with user + model facing reasons.

    The CLI expects permission controls nested inside ``hookSpecificOutput``
    (see ``SyncHookJSONOutput``); a top-level ``permissionDecision`` is ignored.
    """
    return {
        "systemMessage": f"Permission denied: {reason}.",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }


def _is_protected_path(file_path: str) -> bool:
    """Return True if file_path names a protected file or directory."""
    normalized = file_path.replace("\\", "/").rstrip("/")
    if normalized.split("/")[-1] in PROTECTED_FILE_NAMES:
        return True
    return any(normalized.startswith(p.replace("\\", "/")) for p in PROTECTED_PATH_PREFIXES)


def _is_dangerous_command(command: str) -> bool:
    """Return True if the Bash command matches a destructive pattern."""
    return any(re.search(pattern, command) for pattern in DANGEROUS_BASH_PATTERNS)


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------
async def audit_logger(
    input_data: HookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Append a JSONL record for every completed or failed tool call.

    Fail-safe: internal logging errors are caught and logged; they never break
    the research run.
    """
    event_name = input_data.get("hook_event_name")
    if event_name not in {"PostToolUse", "PostToolUseFailure"}:
        return {}

    try:
        record = _build_audit_record(input_data, tool_use_id)
        _append_jsonl(record)
    except Exception as exc:  # noqa: BLE001 - audit must never break the run
        logger.exception("audit_logger failed to record tool call: %s", exc)

    return {}


def _build_audit_record(
    input_data: HookInput,
    tool_use_id: str | None,
) -> dict[str, Any]:
    """Normalize a PostToolUse* event into a flat JSONL record."""
    event_name = input_data.get("hook_event_name")
    base = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "session_id": input_data.get("session_id") or "",
        "agent_id": input_data.get("agent_id") or None,
        "hook": event_name,
        "tool_name": input_data.get("tool_name") or "",
        "tool_use_id": tool_use_id or input_data.get("tool_use_id") or "",
        "tool_input": input_data.get("tool_input") or {},
    }

    if event_name == "PostToolUse":
        data = PostToolUseHookInput(input_data)
        base["tool_output_summary"] = _summarize(data.get("tool_response"))
    elif event_name == "PostToolUseFailure":
        data = PostToolUseFailureHookInput(input_data)
        base["tool_output_summary"] = _summarize(data.get("error"))

    return base


def _summarize(value: Any) -> str:
    """Return a short string representation for the audit log."""
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) > MAX_AUDIT_OUTPUT_SUMMARY:
        return text[:MAX_AUDIT_OUTPUT_SUMMARY] + "... [truncated]"
    return text


def _append_jsonl(record: dict[str, Any]) -> None:
    """Append a single JSON object as a line, creating the file if needed."""
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------------------------
# SubAgent lifecycle tracker
# ---------------------------------------------------------------------------
async def subagent_tracker(
    input_data: HookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Log SubagentStart / SubagentStop with transcript paths for observability."""
    event_name = input_data.get("hook_event_name")
    if event_name == "SubagentStart":
        data = SubagentStartHookInput(input_data)
        logger.info(
            "[SubagentStart] agent_id=%s agent_type=%s",
            data.get("agent_id"),
            data.get("agent_type"),
        )
    elif event_name == "SubagentStop":
        data = SubagentStopHookInput(input_data)
        logger.info(
            "[SubagentStop] agent_id=%s agent_type=%s transcript=%s",
            data.get("agent_id"),
            data.get("agent_type"),
            data.get("agent_transcript_path"),
        )
    return {}


# ---------------------------------------------------------------------------
# Session archiver
# ---------------------------------------------------------------------------
async def session_archiver(
    input_data: HookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Record session end; extension point for external log shipping."""
    if input_data.get("hook_event_name") != "Stop":
        return {}

    try:
        data = StopHookInput(input_data)
        session_id = data.get("session_id") or ""
        logger.info(
            "[SessionStop] session_id=%s audit_log=%s",
            session_id,
            AUDIT_LOG_PATH,
        )
    except Exception as exc:  # noqa: BLE001 - archiver must never break the run
        logger.exception("session_archiver failed: %s", exc)

    return {}


# ---------------------------------------------------------------------------
# Public assembly
# ---------------------------------------------------------------------------
def build_hooks() -> dict[str, list[HookMatcher]]:
    """Assemble the governance hook set shared by all session modes.

    The hook map is passed as `ClaudeAgentOptions(hooks=build_hooks())`. It is
    orthogonal to session mode: fresh, resume and fork runs are governed and
    audited identically.
    """
    return {
        "PreToolUse": [HookMatcher(hooks=[pre_tool_guard])],
        "PostToolUse": [HookMatcher(hooks=[audit_logger])],
        "PostToolUseFailure": [HookMatcher(hooks=[audit_logger])],
        "SubagentStart": [HookMatcher(hooks=[subagent_tracker])],
        "SubagentStop": [HookMatcher(hooks=[subagent_tracker])],
        "Stop": [HookMatcher(hooks=[session_archiver])],
    }
