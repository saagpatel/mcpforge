"""Generator: produces server.py source code from a ServerPlan."""

import logging

from mcpforge.api_client import AnthropicClient
from mcpforge.models import ServerPlan
from mcpforge.prompts import load_prompt
from mcpforge.utils import strip_code_fences

logger = logging.getLogger(__name__)


async def generate_server(plan: ServerPlan, client: AnthropicClient) -> str:
    """Generate FastMCP 3.x server.py source code from a ServerPlan."""
    system_prompt = load_prompt("generator")
    user_message = plan.model_dump_json(indent=2)
    raw = await client.generate(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=16384,
        temperature=0.2,
    )
    return strip_code_fences(raw)
