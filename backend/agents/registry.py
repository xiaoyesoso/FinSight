"""Registry that assembles the SubAgent configuration dict.

The keys here are the names the orchestrator uses to dispatch SubAgents
(`financial-analyzer`, `industry_news_collector`, `a-share-risk-alert`).
They match the reference `agent.py` so prompt templates that reference
SubAgent names keep working unchanged.
"""

from __future__ import annotations

from claude_agent_sdk import AgentDefinition

from backend.agents.financial import financial_analyzer_agent
from backend.agents.industry_news import industry_news_collector_agent
from backend.agents.risk_alert import risk_alert_agent


def build_agents_config() -> dict[str, AgentDefinition]:
    """Return the SubAgent config dict registered on the orchestrator."""
    return {
        "financial-analyzer": financial_analyzer_agent(),
        "industry_news_collector": industry_news_collector_agent(),
        "a-share-risk-alert": risk_alert_agent(),
    }


# Shared singleton reused across research runs.
agents_config = build_agents_config()
