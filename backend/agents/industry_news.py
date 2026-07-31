"""Industry news collector SubAgent factory.

Mounts the `industry-news-collector` Skill to run multi-dimensional web
searches across 5 dimensions, deduplicate coverage, and heat-rank results.
Requires WebFetch (to fetch full article text) and the Bocha search tool.
"""

from __future__ import annotations

from claude_agent_sdk import AgentDefinition

from backend.config import settings


def industry_news_collector_agent() -> AgentDefinition:
    """Build the industry news collector SubAgent definition.

    WebFetch + Bocha search are mandatory because the Skill fetches full
    article text for cross-verification and heat ranking.
    """
    return AgentDefinition(
        description="行业信息收集助手",
        prompt="你是一个行业信息收集助手",
        tools=[
            "Read",
            "Grep",
            "Glob",
            "Bash",
            "Write",
            "Edit",
            "WebFetch",
            "mcp__websearch__bochasearch",
        ],
        skills=["industry_news_collector"],
        model=settings.anthropic_model,
    )
