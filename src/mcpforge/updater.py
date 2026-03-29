"""Updater: applies natural-language modification requests to existing MCP servers."""

import json
from pathlib import Path

from mcpforge.api_client import AnthropicClient
from mcpforge.prompts import load_prompt
from mcpforge.utils import strip_code_fences


async def update_server(
    output_dir: Path,
    request: str,
    client: AnthropicClient,
) -> tuple[str, str]:
    """Apply a natural-language modification request to an existing server.

    Reads server.py (raises FileNotFoundError if missing), reads test_server.py
    if it exists, sends both to LLM with the modification request.
    Returns (updated_server_code, updated_test_code) — both with fences stripped.
    """
    server_py = output_dir / "server.py"
    if not server_py.exists():
        raise FileNotFoundError(f"No server.py found in {output_dir}")

    server_code = server_py.read_text(encoding="utf-8")
    test_py = output_dir / "test_server.py"
    test_code = test_py.read_text(encoding="utf-8") if test_py.exists() else ""

    system_prompt = load_prompt("updater")
    user_message = json.dumps({
        "request": request,
        "server_code": server_code,
        "test_code": test_code,
    })

    raw = await client.generate(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=16384,
        temperature=0.1,
    )

    # Response should be JSON with server_code and test_code keys
    try:
        data = json.loads(raw.strip())
        updated_server = strip_code_fences(data["server_code"])
        updated_test = strip_code_fences(data["test_code"])
    except (json.JSONDecodeError, KeyError):
        # Fallback: treat entire response as server code
        updated_server = strip_code_fences(raw)
        updated_test = test_code

    return updated_server, updated_test
