"""Self-heal: attempt to fix a generated server using LLM-assisted repair.

Phase 1 implementation.
"""

from mcpforge.api_client import AnthropicClient


async def attempt_fix(
    code: str,
    errors: list[str],
    client: AnthropicClient,
) -> str | None:
    """Ask the LLM to fix a generated server given a list of error messages.

    Called at most once per generation (1 retry max per roadmap spec).

    Args:
        code: The generated server.py source that failed validation.
        errors: List of error strings from the validation layers.
        client: Configured AnthropicClient instance.

    Returns:
        Fixed Python source code, or None if the fix could not be generated.
    """
    raise NotImplementedError("self_heal.attempt_fix is implemented in Phase 1")
