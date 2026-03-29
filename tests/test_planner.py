"""Tests for mcpforge planner module."""

from unittest.mock import AsyncMock

import pytest

from mcpforge.api_client import AnthropicClient
from mcpforge.models import ServerPlan, ToolDef
from mcpforge.planner import extract_plan


def _make_plan_json(tools_count: int = 1) -> str:
    tools = [
        {
            "name": f"tool_{i}",
            "description": f"Tool {i}",
            "params": [],
            "return_type": "dict",
            "is_async": True,
            "error_cases": [],
        }
        for i in range(tools_count)
    ]
    import json

    return json.dumps(
        {
            "name": "Test Server",
            "description": "A test server",
            "tools": tools,
            "resources": [],
            "env_vars": [],
            "external_packages": [],
            "transport": "streamable-http",
            "version": "0.1.0",
            "slug": "test-server",
        }
    )


class TestExtractPlan:
    async def test_returns_server_plan(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate_json.return_value = ServerPlan(
            name="Test Server",
            description="A test server",
            tools=[ToolDef(name="do_thing", description="Does thing", params=[])],
        )
        result = await extract_plan("A test server", client)
        assert isinstance(result, ServerPlan)

    async def test_calls_generate_json_with_correct_response_model(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate_json.return_value = ServerPlan(
            name="Test Server",
            description="A test server",
            tools=[ToolDef(name="do_thing", description="Does thing", params=[])],
        )
        await extract_plan("A test server", client)
        call_kwargs = client.generate_json.call_args.kwargs
        assert call_kwargs["response_model"] == ServerPlan
        assert call_kwargs["max_tokens"] == 8192

    async def test_transport_in_user_message(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate_json.return_value = ServerPlan(
            name="Test Server",
            description="desc",
            tools=[ToolDef(name="t", description="t", params=[])],
        )
        await extract_plan("A test server", client, transport="stdio")
        user_msg = client.generate_json.call_args.kwargs["user_message"]
        assert "stdio" in user_msg

    async def test_description_in_user_message(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate_json.return_value = ServerPlan(
            name="Test Server",
            description="desc",
            tools=[ToolDef(name="t", description="t", params=[])],
        )
        await extract_plan("A unique description XYZ123", client)
        user_msg = client.generate_json.call_args.kwargs["user_message"]
        assert "A unique description XYZ123" in user_msg

    async def test_empty_tools_raises_value_error(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate_json.return_value = ServerPlan(
            name="Empty Server",
            description="No tools",
            tools=[],
        )
        with pytest.raises(ValueError, match="no tools"):
            await extract_plan("A server with no tools", client)

    async def test_default_transport_is_streamable_http(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate_json.return_value = ServerPlan(
            name="Test Server",
            description="desc",
            tools=[ToolDef(name="t", description="t", params=[])],
        )
        await extract_plan("A test server", client)
        user_msg = client.generate_json.call_args.kwargs["user_message"]
        assert "streamable-http" in user_msg
