"""Planner: converts a natural-language description into a structured ServerPlan."""

import logging

from mcpforge.api_client import AnthropicClient
from mcpforge.models import ServerPlan
from mcpforge.prompts import load_prompt

logger = logging.getLogger(__name__)


async def extract_plan(
    description: str,
    client: AnthropicClient,
    transport: str = "streamable-http",
) -> ServerPlan:
    """Call the LLM to extract a ServerPlan from a plain-English description."""
    system_prompt = load_prompt("planner")
    user_message = f"Description: {description}\nTransport: {transport}"
    plan = await client.generate_json(
        system_prompt=system_prompt,
        user_message=user_message,
        response_model=ServerPlan,
        max_tokens=8192,
    )
    # generate_json returns BaseModel; cast for type checker
    assert isinstance(plan, ServerPlan)
    if not plan.tools:
        raise ValueError(f"Planner returned a plan with no tools for: {description!r}")
    return plan
