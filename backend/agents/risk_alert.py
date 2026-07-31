"""A-share risk alert SubAgent factory.

Mounts the `a-share-risk-alert` Skill to scan ST / delisting / financial-fraud
risk signals (10 signals), assign a risk grade, and emit a graded report.
Requires WebFetch + Bocha search to retrieve audit opinions, regulatory
penalties, litigation and ST announcements.
"""

from __future__ import annotations

from claude_agent_sdk import AgentDefinition

from backend.config import settings


def risk_alert_agent() -> AgentDefinition:
    """Build the A-share risk alert SubAgent definition."""
    return AgentDefinition(
        description="A股个股风险分析助手",
        prompt="你是一个A股个股风险分析助手",
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
        skills=["a-share-risk-alert"],
        model=settings.anthropic_model,
    )
