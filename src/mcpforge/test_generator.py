"""Test generator: produces test_server.py source code from a ServerPlan and server code."""

import json
import logging

from mcpforge.api_client import AnthropicClient
from mcpforge.models import ServerPlan
from mcpforge.prompts import load_prompt
from mcpforge.utils import strip_code_fences

logger = logging.getLogger(__name__)


async def generate_tests(plan: ServerPlan, server_code: str, client: AnthropicClient) -> str:
    """Generate pytest test suite for the generated server."""
    system_prompt = load_prompt("test_gen")
    user_message = json.dumps(
        {"plan": json.loads(plan.model_dump_json()), "server_code": server_code},
        indent=2,
    )
    raw = await client.generate(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=16384,
        temperature=0.2,
    )
    return strip_code_fences(raw)
