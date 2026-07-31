# AGENTS.md

> Guidance for AI coding agents (Claude Code, Trae, etc.) working on the IIRAS codebase.

## Project Overview

IIRAS (Intelligent Investment Research Agent System) is a multi-agent investment
research platform built on the Claude Agent SDK. A main orchestrator agent
dispatches three SubAgents — financial report analysis, industry news collection,
and A-share risk alert — each mounting a dedicated Skill. The system streams
progress to a React frontend via SSE.

## Architecture

```
Browser (React+TS)  ──HTTP/SSE──▶  FastAPI Backend (Python)
                                      │
                          ┌───────────┼───────────────┐
                          ▼           ▼               ▼
                   orchestrator  websearch MCP   3 SubAgents
                   (Agent tool)  (Bocha AI)      (Skills)
```

- **Backend** (`backend/`): FastAPI + `claude_agent_sdk`. The orchestrator
  registers SubAgents via `ClaudeAgentOptions(agents=...)` and invokes them
  through the built-in `Agent` tool (SubAgent-as-tool pattern).
- **Frontend** (`frontend/`): React + TypeScript + Vite + TailwindCSS. Consumes
  typed SSE events and renders three live SubAgent panels + an aggregated summary.
- **Skills** (`backend/skills/`): Three reference Skills reused as-is from
  `extra_doc/08 subagent/.claude/skills/`. Do NOT rewrite their internal logic.

## Session Management (fresh / resume / fork)

The platform supports three session modes via `ClaudeAgentOptions`, mirroring
the `extra_doc/09 fork/agent.py` reference:

| Mode | Options | Behavior |
|------|---------|----------|
| `fresh` | `session_id=<uuid>` + agents + MCP | New run. An explicit UUID is generated and passed as `session_id` so the SDK persists the conversation to disk (required for later resume/fork). |
| `resume` | `resume=<session_id>` | Continues the session in place; the SDK rehydrates SubAgent/Skill/PDF context from the stored session. Same session_id. |
| `fork` | `resume=<session_id>, fork_session=True, max_turns=N` | Clones the session into an isolated branch with a NEW session_id; the original stays untouched. Default `max_turns=5`. |

- SDK sessions persist on local disk (`~/.claude/projects/...`), so resume/fork
  survive backend restarts; the in-memory lineage map in `RunManager` does not.
- The terminal `ResultMessage.session_id` is attached to the `final_result`
  event (plus `parent_session_id` for forks) so the frontend `SessionBar` can
  offer 继续追问 (resume) and 分叉探索 (fork) actions.
- `file_id`/`agents` routing only applies to fresh runs; resumed/forked
  sessions already carry that context from prior turns.

## Permissions (headless backend)

The backend runs unattended — no human is present to answer interactive tool
approval prompts — so `_build_options()` sets
`permission_mode="bypassPermissions"` for every session mode. Without it,
SubAgent tool calls (Read/Bash/Grep/...) stall the run waiting for an approval
that can never arrive, and the CLI exits non-zero ("Command failed with exit
code 1").

## SSE Event Attribution (`_RunContext`)

`_translate()` folds SDK messages into typed SSE events using a per-run
`_RunContext` (`id_to_agent` / `pending_agents` / `completed_agents`):

- **subagent_dispatch**: an `Agent` ToolUseBlock registers
  `tool_use_id -> SubAgent name` and pushes the id onto `pending_agents`.
- **subagent_result**: the PRIMARY source is the Agent call's own
  `ToolResultBlock` (delivered inside a `UserMessage`) — that payload IS the
  SubAgent's final report in the SubAgent-as-tool pattern. A SubAgent's final
  `end_turn` AssistantMessage is a fallback path; `completed_agents` prevents
  double-emitting. `_clean_subagent_report()` strips CLI protocol trailers
  (`agentId: <hex> (use SendMessage ...)`, `<usage>...</usage>`) that the CLI
  appends to Agent tool results.
- **partial_message**: `StreamEvent`s do NOT carry a reliable
  `parent_tool_use_id`; while a SubAgent is pending, orphan deltas are
  attributed to the most recently dispatched pending SubAgent, otherwise to
  the orchestrator. (In practice the CLI does not forward SubAgent stream
  deltas to the parent process, so most observed deltas are the orchestrator's
  own aggregation output.)
- **tool_call**: `AssistantMessage.parent_tool_use_id` IS reliable — SubAgent
  internal tool calls are attributed via `id_to_agent` directly.

## Code Conventions

- **All code comments MUST be in English** — this is a hard project rule for both
  backend Python and frontend TypeScript.
- Backend: Python 3.11+, type hints required, `async`/`await` for I/O.
- Frontend: TypeScript, function components + hooks, no class components.
- API contract: JSON over HTTP; long-running agent tasks stream via SSE.
- Disclaimer text ("本工具仅供学习和研究使用，不构成投资建议。股市有风险，投资需谨慎。")
  must appear in every research result payload and in the UI.

## Key Modules

| Path | Role |
|------|------|
| `backend/config.py` | Env validation, fails fast on missing vars. `settings` singleton. |
| `backend/main.py` | FastAPI app factory, CORS, route registration. ASGI entrypoint `app`. |
| `backend/agents/orchestrator.py` | `run_research(prompt, session_id, mode, max_turns)` async generator. Builds `ClaudeAgentOptions` per session mode (with `permission_mode="bypassPermissions"`), translates SDK messages to typed SSE events via `_RunContext` attribution. |
| `backend/agents/registry.py` | Assembles `agents_config` dict (3 SubAgent keys). |
| `backend/agents/financial.py` / `industry_news.py` / `risk_alert.py` | SubAgent factories returning `AgentDefinition`. |
| `backend/mcp/websearch.py` | Bocha AI search tool + `websearch_server` MCP server. |
| `backend/api/research.py` | `POST /api/research` (accepts `session_id`/`mode`/`max_turns`), `RunManager` (in-memory queue + session lineage per run). |
| `backend/api/upload.py` | `POST /api/upload` (PDF storage). |
| `backend/api/sse.py` | `GET /api/research/{run_id}/stream` (typed SSE). |
| `frontend/src/hooks/useSSEStream.ts` | React hook consuming SSE events into panel state; captures `session_id` / `parent_session_id` from `final_result`. |
| `frontend/src/api/client.ts` | HTTP + EventSource client; `startResearch` / `resumeResearch` / `forkResearch` helpers. |
| `frontend/src/components/SessionBar.tsx` | Session bar showing session_id, mode badge, fork lineage; hosts resume/fork follow-up actions. |

## SSE Event Taxonomy

The orchestrator emits these typed events (see `backend/agents/orchestrator.py`):

| Event | Meaning |
|-------|---------|
| `subagent_dispatch` | Orchestrator invoked a SubAgent via the Agent tool. |
| `partial_message` | Streaming text delta from an agent (orchestrator or SubAgent). |
| `tool_call` | An agent called a non-Agent tool (Read, Grep, etc.). |
| `subagent_result` | A SubAgent finished; carries the final Markdown (extracted from the Agent call's tool result, CLI trailers stripped). |
| `final_result` | Orchestrator aggregated all results; carries the consolidated report plus `session_id` (and `parent_session_id` for fork runs) for resume/fork actions. |
| `error` | A run failed. |
| `done` | Stream complete; close the connection. |

## Commands

```bash
# Backend
cd backend && cp .env.example .env   # fill in real API keys
uvicorn backend.main:app --reload --port 8000   # run from project root

# Frontend
cd frontend && npm install && npm run dev   # :5173

# Build frontend
cd frontend && npm run build

# Validate OpenSpec artifacts
openspec validate iiras-multi-agent-platform
```

> **SSE through Vite proxy**: the Vite dev-server proxy buffers
> `text/event-stream` responses, which breaks live streaming. Set
> `VITE_API_BASE_URL=http://localhost:<backend-port>` in `frontend/.env` (see
> `frontend/.env.example`) so the browser connects to the backend directly,
> bypassing the proxy. Restart `npm run dev` after changing it.

## Environment Variables

Required (backend fails fast if any missing):

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_BASE_URL` | Anthropic-compatible endpoint (MiniMax, Volcengine ARK, etc.). |
| `ANTHROPIC_MODEL` | Default model (e.g. `MiniMax-M3`, `doubao-seed-2.1-turbo`). |
| `ANTHROPIC_API_KEY` | API key for the endpoint (legacy alias `MINIMAX_API_KEY` also accepted; mirrored to `ANTHROPIC_AUTH_TOKEN`). |
| `BOCHA_API_KEY` | Bocha AI web-search API key. **Optional** — backend only warns if unset, but the news/risk SubAgents' search will fail without it. |
| `FRONTEND_ORIGIN` | CORS origin (default `http://localhost:5173`). |

Optional model-alias overrides: `ANTHROPIC_DEFAULT_HAIKU_MODEL` /
`ANTHROPIC_DEFAULT_SONNET_MODEL` / `ANTHROPIC_DEFAULT_OPUS_MODEL` (each
defaults to `ANTHROPIC_MODEL` when unset).

## What NOT to Change

- `backend/skills/` — these are reference Skills reused as-is. The design
  explicitly treats them as black-box capabilities.
- `extra_doc/` — reference materials (docx, original `agent.py` script). Not
  production code.
- `openspec/` — spec-driven design artifacts. Update via `openspec` commands,
  not by hand-editing the spec structure.

## OpenSpec Workflow

This project uses OpenSpec for spec-driven development. The active change is
`iiras-multi-agent-platform` with artifacts: proposal → specs → design (SDD) → tasks.

- View status: `openspec status --change iiras-multi-agent-platform`
- Validate: `openspec validate iiras-multi-agent-platform`
- Design doc (SDD): `openspec/changes/iiras-multi-agent-platform/design.md`

## Common Tasks

- **Add a new SubAgent**: create `backend/agents/<name>.py` with a factory
  returning `AgentDefinition`, register it in `backend/agents/registry.py`, add
  a panel in the frontend.
- **Change the default model**: set `ANTHROPIC_MODEL` in `.env` (all agents read
  from `settings.anthropic_model`).
- **Add a new SSE event type**: extend `_translate()` in `orchestrator.py`, add
  the type to `useSSEStream.ts`, and handle it in the reducer.
- **Resume / fork a session via API**: `POST /api/research` with
  `{"prompt": "...", "session_id": "<sid>", "mode": "resume"}` to continue in
  place, or `"mode": "fork"` (optional `"max_turns": N`) to branch. The
  `session_id` comes from a prior run's `final_result` event.
