"""Generator: converts a ServerPlan into FastMCP 3.x server.py source code.

Phase 1 implementation.
"""

from mcpforge.api_client import AnthropicClient
from mcpforge.models import ServerPlan


async def generate_server(plan: ServerPlan, client: AnthropicClient) -> str:
    """Call the LLM to generate a complete server.py from a ServerPlan.

    Args:
        plan: Validated ServerPlan describing tools, resources, and configuration.
        client: Configured AnthropicClient instance.

    Returns:
        Raw Python source code for the FastMCP server (no markdown fences).
    """
    raise NotImplementedError("generator.generate_server is implemented in Phase 1")
