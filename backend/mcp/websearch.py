"""Bocha AI web-search exposed as an MCP tool.

This module ports the `bochasearch` tool and `websearch_server` from the
reference `extra_doc/08 subagent/agent.py` script. The tool is registered as
an MCP server named `websearch` so it is addressable as
`mcp__websearch__bochasearch` by the orchestrator and the SubAgents.
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests
from claude_agent_sdk import tool, create_sdk_mcp_server

# Bocha AI web-search API endpoint.
BOCHA_ENDPOINT = "https://api.bochaai.com/v1/web-search"


@tool(
    "bochasearch",
    "Search the web using Bocha AI",
    {"query": str},
)
async def bochasearch(args: dict[str, Any]) -> dict[str, Any]:
    """Run a web search via the Bocha AI API.

    Reads `BOCHA_API_KEY` from the environment and fails loudly when the key
    is missing instead of silently returning empty results. Returns the raw
    Bocha JSON response wrapped in the tool content shape expected by the SDK.
    """
    bochakey = os.getenv("BOCHA_API_KEY")
    if not bochakey:
        # Fail loudly so the caller knows the key is misconfigured.
        raise RuntimeError(
            "BOCHA_API_KEY is not set. Configure it in backend/.env to enable web search."
        )

    headers = {
        "Authorization": f"Bearer {bochakey}",
        "Content-Type": "application/json",
    }
    # Request 10 summarized results per query (matches the reference script).
    data = {"query": args["query"], "summary": True, "count": 10}

    response = requests.post(BOCHA_ENDPOINT, data=json.dumps(data), headers=headers)
    result = response.json()

    # Return the standard tool content shape so agents can parse the text.
    return {
        "content": [
            {
                "type": "text",
                "text": f"result: {result}",
            }
        ]
    }


# Shared MCP server instance reused by the orchestrator and SubAgents.
websearch_server = create_sdk_mcp_server(
    name="websearch",
    version="1.0.0",
    tools=[bochasearch],
)
