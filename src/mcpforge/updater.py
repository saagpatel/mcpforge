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
    user_message = json.dumps(
        {
            "request": request,
            "server_code": server_code,
            "test_code": test_code,
        }
    )

    raw = await client.generate(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=16384,
        temperature=0.1,
    )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid provider response: expected a JSON object") from exc
    if not isinstance(data, dict) or not all(
        isinstance(data.get(key), str) for key in ("server_code", "test_code")
    ):
        raise ValueError("Invalid provider response: server_code and test_code must be strings")

    updated_server = strip_code_fences(data["server_code"])
    updated_tests = strip_code_fences(data["test_code"])
    if not updated_server:
        raise ValueError("Invalid provider response: server_code is empty")
    if test_code and not updated_tests:
        raise ValueError("Invalid provider response: empty test_code would erase existing tests")
    return updated_server, updated_tests
