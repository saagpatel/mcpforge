"""Self-heal: attempts to fix a broken server.py using LLM feedback."""

import logging

from mcpforge.api_client import AnthropicClient
from mcpforge.prompts import load_prompt
from mcpforge.utils import strip_code_fences

logger = logging.getLogger(__name__)

_FIX_PROMPT = """The following FastMCP 3.x server.py has errors. Fix ALL errors and return ONLY
the corrected Python code. No markdown fences, no explanation.

## Errors
{errors}

## Current server.py
```python
{code}
```"""


async def attempt_fix(code: str, errors: list[str], client: AnthropicClient) -> str | None:
    """Attempt to fix broken server.py code using LLM.

    Returns the fixed code string, or None if the fix failed or returned empty content.
    Uses temperature=0.0 for deterministic repair rather than creative rewriting.
    """
    system_prompt = load_prompt("generator")
    user_message = _FIX_PROMPT.format(
        errors="\n".join(f"- {e}" for e in errors),
        code=code,
    )
    try:
        raw = await client.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=16384,
            temperature=0.0,
        )
        fixed = strip_code_fences(raw)
        return fixed if fixed.strip() else None
    except Exception:
        logger.exception("Self-heal LLM call failed")
        return None
