"""Financial report analyzer SubAgent factory.

Mounts the `financial-report-analyzer` Skill to parse PDF reports, compute
key metrics (profitability / growth / solvency / efficiency) and render
charts. The SubAgent keeps its context isolated: only the final Markdown
report is returned to the orchestrator.
"""

from __future__ import annotations

from claude_agent_sdk import AgentDefinition

from backend.config import settings


def financial_analyzer_agent() -> AgentDefinition:
    """Build the financial report analyzer SubAgent definition.

    Tool set mirrors the reference `agent.py`:
      - Read/Grep/Glob/Bash/Write/Edit are required by the Skill's scripts.
      - Bocha web search is included for optional cross-source verification.
    """
    return AgentDefinition(
        description="财报分析助手",
        prompt="你是一个财报分析助手",
        tools=[
            "Read",
            "Grep",
            "Glob",
            "Bash",
            "Write",
            "Edit",
            "mcp__websearch__bochasearch",
        ],
        skills=["financial-report-analyzer"],
        # MiniMax-M3 by default; override via env if a stronger model is needed.
        model=settings.anthropic_model,
    )
