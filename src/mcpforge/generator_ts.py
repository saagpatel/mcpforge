"""TypeScript MCP server generator using @modelcontextprotocol/sdk."""

from mcpforge.api_client import AnthropicClient
from mcpforge.models import ServerPlan
from mcpforge.prompts import load_prompt
from mcpforge.utils import strip_code_fences


async def generate_server_ts(plan: ServerPlan, client: AnthropicClient) -> str:
    """Generate TypeScript server.ts using @modelcontextprotocol/sdk."""
    system_prompt = load_prompt("generator_ts")
    user_message = plan.model_dump_json(indent=2)
    raw = await client.generate(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=16384,
        temperature=0.2,
    )
    return strip_code_fences(raw)


async def generate_tests_ts(
    plan: ServerPlan,
    server_code: str,
    client: AnthropicClient,
) -> str:
    """Generate Vitest test suite for the TypeScript server."""
    system_prompt = load_prompt("test_gen_ts")
    user_message = f"{plan.model_dump_json(indent=2)}\n\n---SERVER CODE---\n{server_code}"
    raw = await client.generate(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=16384,
        temperature=0.2,
    )
    return strip_code_fences(raw)
