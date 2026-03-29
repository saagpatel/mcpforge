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
    # generate_json returns BaseModel; narrow type explicitly
    if not isinstance(plan, ServerPlan):
        raise TypeError(f"Expected ServerPlan, got {type(plan).__name__}")
    if not plan.tools:
        raise ValueError(f"Planner returned a plan with no tools for: {description!r}")
    return plan


async def refine_plan(
    plan: ServerPlan,
    feedback: str,
    client: AnthropicClient,
) -> ServerPlan:
    """Apply user feedback to an existing ServerPlan via LLM."""
    system_prompt = load_prompt("planner")
    user_message = (
        f"Here is the current server plan:\n\n{plan.model_dump_json(indent=2)}\n\n"
        f"The user wants these changes: {feedback}\n\n"
        f"Return the complete updated plan JSON."
    )
    updated = await client.generate_json(
        system_prompt=system_prompt,
        user_message=user_message,
        response_model=ServerPlan,
        max_tokens=8192,
    )
    if not isinstance(updated, ServerPlan):
        raise TypeError(f"Expected ServerPlan, got {type(updated).__name__}")
    if not updated.tools:
        raise ValueError("Refined plan has no tools")
    return updated
