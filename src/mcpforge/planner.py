"""Planner: converts a natural-language description into a structured ServerPlan.

Phase 1 implementation.
"""

from mcpforge.api_client import AnthropicClient
from mcpforge.models import ServerPlan


async def extract_plan(
    description: str,
    client: AnthropicClient,
    transport: str = "streamable-http",
) -> ServerPlan:
    """Call the LLM to extract a ServerPlan from a plain-English description.

    Args:
        description: Natural language description of the desired MCP server.
        client: Configured AnthropicClient instance.
        transport: MCP transport type to embed in the plan.

    Returns:
        Validated ServerPlan instance.
    """
    raise NotImplementedError("planner.extract_plan is implemented in Phase 1")
