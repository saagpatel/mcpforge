"""Tests for the updater module."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from mcpforge.updater import update_server


@pytest.fixture()
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.generate = AsyncMock(
        return_value=json.dumps({"server_code": "new server", "test_code": "new tests"})
    )
    return client


async def test_update_server_calls_generate_with_server_code(
    tmp_path: Path, mock_client: AsyncMock
) -> None:
    """update_server passes existing server code in the user message to generate."""
    server_py = tmp_path / "server.py"
    server_py.write_text("# existing server code", encoding="utf-8")

    await update_server(tmp_path, "add a new tool", mock_client)

    mock_client.generate.assert_called_once()
    call_kwargs = mock_client.generate.call_args
    user_message = call_kwargs.kwargs.get("user_message") or call_kwargs.args[1]
    payload = json.loads(user_message)
    assert payload["server_code"] == "# existing server code"
    assert payload["request"] == "add a new tool"


async def test_update_server_raises_for_missing_server_py(
    tmp_path: Path, mock_client: AsyncMock
) -> None:
    """update_server raises FileNotFoundError when server.py does not exist."""
    with pytest.raises(FileNotFoundError, match="server.py"):
        await update_server(tmp_path, "add a tool", mock_client)


async def test_update_server_returns_tuple(
    tmp_path: Path, mock_client: AsyncMock
) -> None:
    """update_server returns a (server_code, test_code) tuple with fences stripped."""
    server_py = tmp_path / "server.py"
    server_py.write_text("# server", encoding="utf-8")

    server_code, test_code = await update_server(tmp_path, "add a tool", mock_client)

    assert server_code == "new server"
    assert test_code == "new tests"


async def test_update_server_includes_test_code_when_exists(
    tmp_path: Path, mock_client: AsyncMock
) -> None:
    """test_server.py content is included in LLM context when it exists."""
    (tmp_path / "server.py").write_text("# server", encoding="utf-8")
    (tmp_path / "test_server.py").write_text("# existing tests", encoding="utf-8")

    await update_server(tmp_path, "add a tool", mock_client)

    call_kwargs = mock_client.generate.call_args
    user_message = call_kwargs.kwargs.get("user_message") or call_kwargs.args[1]
    payload = json.loads(user_message)
    assert payload["test_code"] == "# existing tests"


async def test_update_server_empty_test_code_when_no_test_file(
    tmp_path: Path, mock_client: AsyncMock
) -> None:
    """When test_server.py does not exist, test_code in message is empty string."""
    (tmp_path / "server.py").write_text("# server", encoding="utf-8")

    await update_server(tmp_path, "add a tool", mock_client)

    call_kwargs = mock_client.generate.call_args
    user_message = call_kwargs.kwargs.get("user_message") or call_kwargs.args[1]
    payload = json.loads(user_message)
    assert payload["test_code"] == ""


async def test_update_server_strips_fences_from_response(
    tmp_path: Path,
) -> None:
    """Fences in LLM JSON values are stripped from returned code."""
    client = AsyncMock()
    client.generate = AsyncMock(
        return_value=json.dumps({
            "server_code": "```python\ncode here\n```",
            "test_code": "```python\ntest here\n```",
        })
    )
    (tmp_path / "server.py").write_text("# server", encoding="utf-8")

    server_code, test_code = await update_server(tmp_path, "update it", client)

    assert server_code == "code here"
    assert test_code == "test here"
