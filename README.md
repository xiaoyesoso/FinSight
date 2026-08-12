# FinSight · 全链路智能投研平台

> Full-Stack Intelligent Investment Research Platform - 基于多代理编排的投研平台。
> 主 Agent 统筹调度财报分析、行业新闻、风险预警三个 SubAgent,并行执行,实时流式输出。

⚠️ **免责声明：本工具仅供学习和研究使用，不构成投资建议。股市有风险，投资需谨慎。**

[English](README.en.md)

---

## 功能特性

- **多代理编排**：主 Agent 通过 `Agent` 工具调度三个 SubAgent，实现上下文隔离与并行执行
- **财报深度分析**：解析 PDF 财报，计算盈利/成长/偿债/运营四大类指标，生成可视化图表
- **行业热点洞察**：多维度网络搜索（5 维度 ≥8 次检索），去重合并，热度排序
- **风险全面评估**：A 股 ST 预警、退市风险、财务造假排查，10 大风险信号扫描
- **会话续问与分叉**：研究完成后可在原会话上继续追问（完整保留上下文），或将会话克隆为独立分支探索不同投资逻辑；SDK 会话持久化在本地磁盘
- **实时流式输出**：SSE 推送 SubAgent 调度、部分消息、工具调用、最终结果
- **Web 工作台**：React 前端，三面板并行展示 + 聚合研报
- **治理与审计**：PreToolUse 权限守卫（只读工具自动放行、危险操作拦截）、PostToolUse JSONL 审计日志、SubAgent 生命周期追踪
- **全链路可观测**：OpenTelemetry 集成，Traces/Metrics/Log events 导出至 Jaeger/Grafana，支持按用户/租户成本归因

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ · FastAPI · Uvicorn · Claude Agent SDK |
| 前端 | React + TypeScript · Vite · TailwindCSS |
| 模型 | 任意 Anthropic 兼容端点（MiniMax、火山引擎 ARK 等） |
| 搜索 | Bocha AI（MCP 工具 `mcp__websearch__bochasearch`） |
| 协议 | HTTP + SSE（Server-Sent Events） |

## 架构

![架构总览](blog/img-architecture.png)

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (分析师)                       │
│   Composer ──▶ SSE Client ──▶ 3 SubAgent 面板 + 汇总     │
└────────────────────────┬────────────────────────────────┘
            HTTPS / SSE   │
┌─────────────────────────┴────────────────────────────────┐
│              Backend (FastAPI · Python)                   │
│                                                          │
│   POST /api/upload    ──▶  PDF 存储 ──▶ file_id          │
│   POST /api/research  ──▶  创建 run ──▶ run_id            │
│   GET  /api/research/{id}/stream ──▶ SSE 事件流           │
│                                                          │
│   ┌──────────────────────────────────────────────────┐   │
│   │        Orchestrator (ClaudeSDKClient)             │   │
│   │   agents = {                                      │   │
│   │     financial-analyzer       (财报 Skill)         │   │
│   │     industry_news_collector  (行业 Skill)         │   │
│   │     a-share-risk-alert       (风险 Skill)         │   │
│   │   }                                              │   │
│   │   mcp_servers = { websearch: Bocha }             │   │
│   └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 会话模式

![会话模式](blog/img-sessions.png)

- **Fresh（新会话）**：生成新的 `session_id`，注册 SubAgent、MCP、Hooks 和 OTel 环境变量。
- **Resume（续问）**：在原会话上继续追问，SDK 恢复完整上下文。
- **Fork（分叉）**：克隆当前会话为独立分支（新 `session_id`），原会话不受影响。

### 治理与审计

![治理 Hook 流程](blog/img-hooks.png)

- **PreToolUse**：权限守卫，自动放行只读工具，拦截危险写操作和 Bash 命令。
- **PostToolUse**：每次工具调用后追加 JSONL 审计日志。
- **SubagentStart / SubagentStop**：追踪子代理生命周期和 transcript 路径。

### OpenTelemetry 可观测

![OpenTelemetry 信号流](blog/img-otel.png)

- **Metrics**：token 数、会话数、工具决策 → Prometheus。
- **Traces**：Agent → SubAgent → Tool → LLM 调用链 → Jaeger。
- **Log Events**：结构化 prompt、API 请求、工具结果 → Grafana。

### 成本归因

![成本归因公式](blog/img-cost-formula.png)

- 单次调用成本：`C = (Ni × Pi + No × Po + Nc × Pc) / 1,000,000`。
- 多代理总成本为主代理与所有子代理各自 C 值之和。
- `enduser.id` / `tenant.id` 资源属性支持在 Grafana 中按分析师和按团队汇总成本。

### 前端工作台

![前端首页](blog/img-frontend-homepage.jpg)

## 快速开始

### 1. 环境准备

- Python 3.11+（推荐 conda base 环境，已含 `claude_agent_sdk`）
- Node.js 18+ / npm

### 2. 配置后端

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入真实的 API Key：
#   ANTHROPIC_API_KEY  - Anthropic 兼容端点的 API 密钥
#                        （兼容旧名 MINIMAX_API_KEY）
#   BOCHA_API_KEY      - Bocha AI 搜索密钥（可选；行业/风险 SubAgent 需要）
```

### 3. 启动后端

```bash
# 在项目根目录执行
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

验证：访问 http://localhost:8000/health 返回 `{"status":"ok","model":"<你的模型>"}`

### 4. 启动前端

```bash
cd frontend
npm install
cp .env.example .env   # 设置 VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

访问 http://localhost:5173 即可使用。

> **注意**：`VITE_API_BASE_URL` 让浏览器直连后端。若不设置，SSE 流会经过
> Vite 开发代理，代理会缓冲 `text/event-stream` 响应，导致实时流式更新失效。

## 使用方法

1. 在 Composer 中输入研究提示词（如"请对燕京啤酒进行全面投研分析"）
2. 可选：上传财报 PDF 文件
3. 勾选要调度的 SubAgent（财报 / 行业 / 风险）
4. 点击"开始研究"，三个面板将实时流式展示各 SubAgent 的输出
5. 最终在顶部查看聚合研报
6. 研究完成后，会话栏（SessionBar）显示会话 ID，并提供两个操作：
   - **继续追问（resume）**：在同一会话中追问，Agent 保留完整上下文（PDF 路径、已有结论、SubAgent 路由）
   - **分叉探索（fork）**：将会话克隆为独立分支（新会话 ID，可选最大轮次），在不影响原会话的情况下探索不同投资逻辑

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/upload` | 上传 PDF 财报，返回 `file_id` |
| `POST` | `/api/research` | 提交研究任务，返回 `run_id`。请求体：`prompt`（必填）、`file_id`、`agents`、`session_id`、`mode`（`fresh`/`resume`/`fork`，默认 `fresh`）、`max_turns`（仅 fork，默认 5） |
| `GET` | `/api/research/{run_id}/stream` | SSE 流式获取研究进度 |

### 请求示例

```bash
# 上传 PDF
curl -X POST http://localhost:8000/api/upload \
  -F "file=@燕京啤酒财报.pdf"

# 提交新研究任务
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"prompt":"分析燕京啤酒","file_id":"<id>","agents":["financial-analyzer"]}'

# 继续追问（session_id 来自上一轮 final_result SSE 事件）
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"prompt":"请补充最新一周行业利空","session_id":"<sid>","mode":"resume"}'

# 分叉探索（克隆会话为独立分支）
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"prompt":"基于现有分析，额外用 DCF 模型重做估值","session_id":"<sid>","mode":"fork","max_turns":5}'
```

### SSE 事件类型

| 事件 | 含义 |
|---|---|
| `subagent_dispatch` | 主 Agent 调度了某个 SubAgent |
| `partial_message` | 流式部分消息 |
| `tool_call` | 工具调用 |
| `subagent_result` | SubAgent 完成，携带最终 Markdown |
| `final_result` | 主 Agent 聚合完成，携带综合研报及 `session_id`（fork 时另带 `parent_session_id`） |
| `error` | 运行出错 |
| `done` | 流结束 |

## 项目结构

```
FinSight/
├── backend/                    # Python 后端
│   ├── config.py               # 环境变量校验（fail-fast）
│   ├── main.py                 # FastAPI 应用工厂
│   ├── api/                    # HTTP + SSE 接口层
│   │   ├── research.py         # POST /api/research + RunManager
│   │   ├── upload.py           # POST /api/upload
│   │   └── sse.py              # GET /api/research/{id}/stream
│   ├── agents/                 # 多代理定义
│   │   ├── orchestrator.py     # 主 Agent 驱动 + SSE 事件翻译
│   │   ├── financial.py        # 财报 SubAgent
│   │   ├── industry_news.py    # 行业新闻 SubAgent
│   │   ├── risk_alert.py       # 风险预警 SubAgent
│   │   ├── hooks.py            # 治理 Hooks（权限守卫 + 审计日志 + 生命周期追踪）
│   │   ├── telemetry.py        # OpenTelemetry 环境变量工厂
│   │   └── registry.py         # agents_config 注册表
│   ├── mcp/
│   │   └── websearch.py        # Bocha AI 搜索 MCP 工具
│   ├── skills/                 # 三个 Skill（原样复用）
│   └── data/uploads/           # PDF 上传存储
├── frontend/                   # React + TS 前端
│   └── src/
│       ├── App.tsx             # 工作台主视图
│       ├── api/client.ts       # HTTP + EventSource 客户端（start/resume/fork 封装）
│       ├── hooks/useSSEStream.ts  # SSE 消费 Hook（捕获会话 lineage）
│       └── components/         # Composer / SubAgentPanel / SummaryView / SessionBar / Disclaimer
├── AGENTS.md                   # AI 代理开发指南
├── README.md                   # 本文件（中文）
└── README.en.md                # 英文文档
```

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `ANTHROPIC_BASE_URL` | ✅ | Anthropic 兼容端点（MiniMax、火山引擎 ARK 等） |
| `ANTHROPIC_MODEL` | ✅ | 默认模型（如 `MiniMax-M3`、`doubao-seed-2.1-turbo`） |
| `ANTHROPIC_API_KEY` | ✅ | 端点 API 密钥（兼容旧名 `MINIMAX_API_KEY`） |
| `BOCHA_API_KEY` | | Bocha AI 搜索密钥。可选，但未配置时行业/风险 SubAgent 的联网搜索会失败 |
| `FRONTEND_ORIGIN` | | CORS 来源（默认 `http://localhost:5173`） |
| `VITE_API_BASE_URL` | | 仅前端：开发环境下指向后端地址，使 SSE 绕过 Vite 代理 |

## 核心设计

- **SubAgent 即工具**：每个 SubAgent 挂载一个专属 Skill，主 Agent 通过 `Agent` 工具调度，中间过程隔离在 SubAgent 内部，主 Agent 仅获取精炼结论
- **并行执行**：三个 SubAgent 逻辑互不依赖，可并发运行
- **会话管理**：fresh 会话显式生成 UUID 作为 `session_id`，确保 SDK 将会话持久化到本地磁盘；`resume` 在原会话上完整恢复上下文继续追问，`fork` 则会话克隆为独立分支（新会话 ID、轮次上限），用于并行探索不同投资逻辑
- **无头权限模式**：后端以 `permission_mode="bypassPermissions"` 运行，SubAgent 的工具调用（Read/Bash/Grep 等）自动批准——服务端没有人工响应交互式审批提示
- **实时事件归属**：每次运行维护独立上下文，将 Agent 工具调用映射到对应 SubAgent，从 Agent 工具返回值中提取 SubAgent 最终报告（剥离 CLI 协议尾巴），并将文本增量以 `partial_message` 事件流式推送
- **显式路由**：部分国产模型自主规划能力有限，前端支持显式指定 SubAgent，提示词注入"必须使用子agent"指令
- **英文注释**：所有自写代码注释统一使用英文（Skills 为原样复用的参考资产）

## 开发指南

详见 [AGENTS.md](AGENTS.md) - 包含架构说明、代码规范、常用命令和扩展指南。

## 许可与免责

本项目仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。
