"""Generator: produces server.py source code from a ServerPlan."""

import json as _json
import logging

from mcpforge.api_client import AnthropicClient
from mcpforge.models import ServerPlan
from mcpforge.prompts import load_prompt
from mcpforge.utils import strip_code_fences

logger = logging.getLogger(__name__)


async def generate_server(
    plan: ServerPlan,
    client: AnthropicClient,
    template_hint: str = "",
) -> str:
    """Generate FastMCP 3.x server.py source code from a ServerPlan."""
    system_prompt = load_prompt("generator")
    if template_hint:
        system_prompt = f"{system_prompt}\n\n## Template Guidance\n\n{template_hint}"
    user_message = plan.model_dump_json(indent=2)
    raw = await client.generate(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=16384,
        temperature=0.2,
    )
    return strip_code_fences(raw)


async def generate_server_multi(
    plan: ServerPlan,
    client: AnthropicClient,
    template_hint: str = "",
) -> dict[str, str]:
    """Generate a multi-file FastMCP server split across multiple modules.

    Returns a dict mapping relative file paths to their content.
    Always includes at least 'server.py'. Falls back to single-file dict
    on malformed LLM response.
    """
    system_prompt = load_prompt("generator_multi")
    if template_hint:
        system_prompt = f"{system_prompt}\n\n## Template Guidance\n\n{template_hint}"
    user_message = plan.model_dump_json(indent=2)
    raw = await client.generate(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=16384,
        temperature=0.2,
    )
    cleaned = strip_code_fences(raw)
    try:
        result = _json.loads(cleaned)
        if not isinstance(result, dict) or "server.py" not in result:
            raise ValueError("Missing server.py key")
        return {k: str(v) for k, v in result.items()}
    except (ValueError, _json.JSONDecodeError):
        logger.warning(
            "generate_server_multi: LLM returned malformed JSON, using single-file fallback"
        )
        return {"server.py": cleaned}
