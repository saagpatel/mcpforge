"""Test generator: produces a pytest test suite for a generated MCP server.

Phase 1 implementation.
"""

from mcpforge.api_client import AnthropicClient
from mcpforge.models import ServerPlan


async def generate_tests(
    plan: ServerPlan,
    server_code: str,
    client: AnthropicClient,
) -> str:
    """Call the LLM to generate a pytest test suite for a generated server.

    Args:
        plan: The ServerPlan the server was generated from.
        server_code: The generated server.py source code.
        client: Configured AnthropicClient instance.

    Returns:
        Raw Python source code for the pytest test suite (no markdown fences).
    """
    raise NotImplementedError("test_generator.generate_tests is implemented in Phase 1")
