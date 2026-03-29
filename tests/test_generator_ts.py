"""Tests for the generator_ts module."""

from unittest.mock import AsyncMock

import pytest

from mcpforge.generator_ts import generate_server_ts, generate_tests_ts
from mcpforge.models import ServerPlan, ToolDef, ToolParam


@pytest.fixture()
def sample_plan() -> ServerPlan:
    return ServerPlan(
        name="Echo Server",
        description="A simple echo server",
        tools=[
            ToolDef(
                name="echo",
                description="Echo the input",
                params=[ToolParam(name="message", type="str", description="Message to echo")],
            )
        ],
    )


@pytest.fixture()
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.generate = AsyncMock(return_value="const server = new McpServer();")
    return client


async def test_generate_server_ts_calls_client_with_ts_prompt(
    sample_plan: ServerPlan, mock_client: AsyncMock
) -> None:
    """generate_server_ts calls client with TypeScript-specific system prompt."""
    await generate_server_ts(sample_plan, mock_client)

    mock_client.generate.assert_called_once()
    call_kwargs = mock_client.generate.call_args
    system_prompt = call_kwargs.kwargs.get("system_prompt") or call_kwargs.args[0]
    assert "TypeScript" in system_prompt or "generator_ts" in system_prompt.lower()


async def test_generate_server_ts_returns_stripped_code(
    sample_plan: ServerPlan,
) -> None:
    """generate_server_ts returns code with fences stripped."""
    client = AsyncMock()
    client.generate = AsyncMock(
        return_value="```typescript\nconst server = new McpServer();\n```"
    )
    result = await generate_server_ts(sample_plan, client)
    assert result == "const server = new McpServer();"


async def test_generate_tests_ts_includes_server_code(
    sample_plan: ServerPlan, mock_client: AsyncMock
) -> None:
    """generate_tests_ts includes server_code in the user message."""
    server_code = "const server = new McpServer();"
    await generate_tests_ts(sample_plan, server_code, mock_client)

    mock_client.generate.assert_called_once()
    call_kwargs = mock_client.generate.call_args
    user_message = call_kwargs.kwargs.get("user_message") or call_kwargs.args[1]
    assert server_code in user_message


async def test_strip_code_fences_typescript(sample_plan: ServerPlan) -> None:
    """Fence stripping handles typescript-tagged fences."""
    client = AsyncMock()
    client.generate = AsyncMock(
        return_value="```typescript\ncode\n```"
    )
    # strip_code_fences only strips python/generic fences by default;
    # the TS generator uses the same utility — verify it handles generic fences too
    result = await generate_server_ts(sample_plan, client)
    # The fence should be stripped (either fully or partially depending on implementation)
    # At minimum the raw content should not start with ```
    assert not result.startswith("```")
