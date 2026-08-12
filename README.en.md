# FinSight · Full-Stack Intelligent Investment Research Platform

> A multi-agent orchestration platform for investment research with full-stack
> observability. A main orchestrator agent dispatches three SubAgents - financial
> report analysis, industry news collection, and A-share risk alert - that run in
> parallel and stream results live to a React frontend.

⚠️ **Disclaimer: This tool is for learning and research purposes only and does
not constitute investment advice. The stock market carries risks; invest with
caution.**

[中文文档](README.md)

---

## Features

- **Multi-agent orchestration**: the main agent dispatches three SubAgents via
  the `Agent` tool, achieving context isolation and parallel execution.
- **Financial report analysis**: parses PDF reports, computes profitability /
  growth / solvency / efficiency metrics, and renders visualization charts.
- **Industry news insights**: multi-dimensional web search (5 dimensions, ≥8
  queries), deduplication, and heat-ranking.
- **Risk assessment**: A-share ST / delisting / financial-fraud scanning across
  10 risk signals with a graded risk report.
- **Session resume & fork**: continue a finished research thread with full
  context (resume), or clone it into an isolated branch to explore alternative
  investment logic (fork) - SDK sessions persist on local disk.
- **Live streaming**: SSE pushes SubAgent dispatch, partial messages, tool calls,
  and final results to the browser.
- **Web workbench**: React frontend with three parallel panels + an aggregated
  research report.
- **Governance & audit**: PreToolUse permission guardrail (auto-allow read-only
  tools, block dangerous operations), PostToolUse JSONL audit trail, SubAgent
  lifecycle tracking.
- **Full-stack observability**: OpenTelemetry integration exporting
  Traces/Metrics/Log events to Jaeger/Grafana with per-user/tenant cost
  attribution.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+ · FastAPI · Uvicorn · Claude Agent SDK |
| Frontend | React + TypeScript · Vite · TailwindCSS |
| Model | Any Anthropic-compatible endpoint (MiniMax, Volcengine ARK, ...) |
| Search | Bocha AI (MCP tool `mcp__websearch__bochasearch`) |
| Protocol | HTTP + SSE (Server-Sent Events) |

## Architecture

![Architecture Overview](blog/img-architecture.png)

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (analyst)                     │
│   Composer ──▶ SSE Client ──▶ 3 SubAgent panels + summary│
└────────────────────────┬────────────────────────────────┘
            HTTPS / SSE   │
┌─────────────────────────┴────────────────────────────────┐
│              Backend (FastAPI · Python)                   │
│                                                          │
│   POST /api/upload    ──▶  PDF storage ──▶ file_id       │
│   POST /api/research  ──▶  create run  ──▶ run_id         │
│   GET  /api/research/{id}/stream ──▶ SSE event stream     │
│                                                          │
│   ┌──────────────────────────────────────────────────┐   │
│   │        Orchestrator (ClaudeSDKClient)             │   │
│   │   agents = {                                      │   │
│   │     financial-analyzer       (financial Skill)    │   │
│   │     industry_news_collector  (industry Skill)     │   │
│   │     a-share-risk-alert       (risk Skill)         │   │
│   │   }                                              │   │
│   │   mcp_servers = { websearch: Bocha }             │   │
│   └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### Session Modes

![Session Modes](blog/img-sessions.png)

- **Fresh**: a new `session_id` is generated; agents, MCP servers, hooks, and telemetry env are registered.
- **Resume**: continue in the same session with full context rehydration.
- **Fork**: clone the session into an isolated branch with a new `session_id`; the original stays untouched.

### Governance Hooks

![Governance Hooks](blog/img-hooks.png)

- **PreToolUse**: permission guardrail that auto-allows read-only tools and denies dangerous writes/commands.
- **PostToolUse**: appends a JSONL audit record per tool call.
- **SubagentStart / SubagentStop**: tracks SubAgent lifecycle and transcript paths.

### OpenTelemetry Pipeline

![OpenTelemetry Signals](blog/img-otel.png)

- **Metrics**: token counts, session counts, tool decisions → Prometheus.
- **Traces**: Orchestrator → SubAgent → Tool → LLM spans → Jaeger.
- **Log events**: structured prompts, API requests, tool results → Grafana.

### Cost Attribution

![Cost Attribution Formula](blog/img-cost-formula.png)

- Per-request cost: `C = (Ni × Pi + No × Po + Nc × Pc) / 1,000,000`.
- Multi-agent total cost is the sum of orchestrator + all SubAgent calls.
- `enduser.id` / `tenant.id` resource attributes enable per-analyst and per-team rollups in Grafana.

### Frontend Workbench

![Frontend Homepage](blog/img-frontend-homepage.jpg)

## Quick Start

### 1. Prerequisites

- Python 3.11+ (conda base environment recommended; already includes
  `claude_agent_sdk`)
- Node.js 18+ / npm

### 2. Configure the backend

```bash
cd backend
cp .env.example .env
# Edit .env and fill in real API keys:
#   ANTHROPIC_API_KEY  - API key for your Anthropic-compatible endpoint
#                        (legacy alias MINIMAX_API_KEY also accepted)
#   BOCHA_API_KEY      - Bocha AI search key (optional; news/risk SubAgents need it)
```

### 3. Run the backend

```bash
# Run from the project root
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Verify: open http://localhost:8000/health - should return
`{"status":"ok","model":"<your-model>"}`

### 4. Run the frontend

```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Open http://localhost:5173.

> **Note**: `VITE_API_BASE_URL` makes the browser call the backend directly.
> Without it, SSE streams go through the Vite dev proxy, which buffers
> `text/event-stream` responses and breaks live updates.

## Usage

1. Enter a research prompt in the Composer (e.g. "Analyze Yanjing Beer").
2. Optional: upload a financial report PDF.
3. Select which SubAgents to dispatch (financial / industry / risk).
4. Click "开始研究" - three panels stream each SubAgent's output in real time.
5. View the aggregated report at the top once all SubAgents finish.
6. Once a run completes, the SessionBar shows the session ID and offers:
   - **继续追问 (resume)**: ask a follow-up in the same session - the agents
     keep full context (PDF path, prior findings, SubAgent routing).
   - **分叉探索 (fork)**: clone the session into an isolated branch (new
     session ID, optional turn cap) to test an alternative investment logic
     without touching the original thread.

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/upload` | Upload a PDF report, returns `file_id` |
| `POST` | `/api/research` | Submit a research task, returns `run_id`. Body: `prompt` (required), `file_id`, `agents`, `session_id`, `mode` (`fresh`/`resume`/`fork`, default `fresh`), `max_turns` (fork only, default 5) |
| `GET` | `/api/research/{run_id}/stream` | SSE stream of research progress |

### Examples

```bash
# Upload a PDF
curl -X POST http://localhost:8000/api/upload \
  -F "file=@report.pdf"

# Submit a fresh research task
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Analyze Yanjing Beer","file_id":"<id>","agents":["financial-analyzer"]}'

# Resume a session (session_id comes from the final_result SSE event)
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Add the latest weekly bearish news","session_id":"<sid>","mode":"resume"}'

# Fork a session into an isolated branch
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Redo the valuation with a DCF model","session_id":"<sid>","mode":"fork","max_turns":5}'
```

### SSE Event Types

| Event | Meaning |
|-------|---------|
| `subagent_dispatch` | Orchestrator dispatched a SubAgent |
| `partial_message` | Streaming partial text |
| `tool_call` | A tool was invoked |
| `subagent_result` | SubAgent finished; carries final Markdown |
| `final_result` | Orchestrator aggregated results; carries the full report plus `session_id` (and `parent_session_id` for forks) |
| `error` | A run failed |
| `done` | Stream complete |

## Project Structure

```
FinSight/
├── backend/                    # Python backend
│   ├── config.py               # Env validation (fail-fast)
│   ├── main.py                 # FastAPI app factory
│   ├── api/                    # HTTP + SSE layer
│   │   ├── research.py         # POST /api/research + RunManager
│   │   ├── upload.py           # POST /api/upload
│   │   └── sse.py              # GET /api/research/{id}/stream
│   ├── agents/                 # Multi-agent definitions
│   │   ├── orchestrator.py     # Main agent driver + SSE event translation
│   │   ├── financial.py        # Financial report SubAgent
│   │   ├── industry_news.py    # Industry news SubAgent
│   │   ├── risk_alert.py       # Risk alert SubAgent
│   │   ├── hooks.py            # Governance hooks (permission guard + audit + lifecycle)
│   │   ├── telemetry.py        # OpenTelemetry env factory
│   │   └── registry.py         # agents_config registry
│   ├── mcp/
│   │   └── websearch.py        # Bocha AI search MCP tool
│   ├── skills/                 # Three Skills (reused as-is)
│   └── data/uploads/           # PDF upload storage
├── frontend/                   # React + TS frontend
│   └── src/
│       ├── App.tsx             # Workbench main view
│       ├── api/client.ts       # HTTP + EventSource client (start/resume/fork helpers)
│       ├── hooks/useSSEStream.ts  # SSE consumer hook (captures session lineage)
│       └── components/         # Composer / SubAgentPanel / SummaryView / SessionBar / Disclaimer
├── AGENTS.md                   # AI agent development guide
├── README.md                   # Chinese documentation
└── README.en.md                # This file (English)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_BASE_URL` | ✅ | Anthropic-compatible endpoint (MiniMax, Volcengine ARK, ...) |
| `ANTHROPIC_MODEL` | ✅ | Default model (e.g. `MiniMax-M3`, `doubao-seed-2.1-turbo`) |
| `ANTHROPIC_API_KEY` | ✅ | API key for the endpoint (legacy alias `MINIMAX_API_KEY` also accepted) |
| `BOCHA_API_KEY` | | Bocha AI search key. Optional, but news/risk SubAgents' web search fails without it |
| `FRONTEND_ORIGIN` | | CORS origin (default `http://localhost:5173`) |
| `VITE_API_BASE_URL` | | Frontend only: backend base URL in dev so SSE bypasses the Vite proxy |

## Core Design

- **SubAgent as a tool**: each SubAgent mounts a dedicated Skill; the main agent
  invokes it via the `Agent` tool. Intermediate steps stay inside the SubAgent,
  so the orchestrator only receives the refined conclusion - keeping its context
  clean.
- **Parallel execution**: the three SubAgents are logically independent and run
  concurrently.
- **Session management**: fresh runs get an explicit UUID `session_id` so the
  SDK persists the conversation to disk; `resume` rehydrates the full context
  in place, and `fork` clones it into an isolated branch (new session ID, turn
  cap) for exploring alternative investment logic in parallel.
- **Headless permissions**: the backend sets `permission_mode="bypassPermissions"`
  so SubAgent tool calls (Read/Bash/Grep/...) auto-approve - there is no human
  in the loop to answer interactive approval prompts.
- **Live event attribution**: a per-run context maps Agent tool calls to
  SubAgents, extracts each SubAgent's final report from the Agent tool result
  (stripping CLI protocol trailers), and streams text deltas as
  `partial_message` events.
- **Explicit routing**: some domestic models have limited autonomous planning; the
  frontend supports explicit SubAgent selection and injects a "must use subagent"
  directive into the prompt.
- **English comments**: all hand-written code comments are in English (Skills are
  reused reference assets, left unchanged).

## Development Guide

See [AGENTS.md](AGENTS.md) for architecture details, code conventions, common
commands, and extension guides.

## License & Disclaimer

This project is for learning and research purposes only and does not constitute
any investment advice. The stock market carries risks; invest with caution.
