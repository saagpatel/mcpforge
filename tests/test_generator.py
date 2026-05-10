"""Tests for generator, test_generator, and utils modules."""

from unittest.mock import AsyncMock

from mcpforge.api_client import AnthropicClient
from mcpforge.generator import generate_server
from mcpforge.models import ServerPlan, ToolDef, ToolParam
from mcpforge.test_generator import generate_tests
from mcpforge.utils import strip_code_fences


def _sample_plan() -> ServerPlan:
    return ServerPlan(
        name="Test Server",
        description="A test server",
        tools=[
            ToolDef(
                name="do_thing",
                description="Does thing",
                params=[ToolParam(name="x", type="str", description="x")],
            )
        ],
    )


class TestStripCodeFences:
    def test_strips_python_fence(self):
        text = "```python\nprint('hello')\n```"
        assert strip_code_fences(text) == "print('hello')"

    def test_strips_plain_fence(self):
        text = "```\nprint('hello')\n```"
        assert strip_code_fences(text) == "print('hello')"

    def test_no_fence_passthrough(self):
        text = "print('hello')"
        assert strip_code_fences(text) == "print('hello')"

    def test_strips_whitespace(self):
        text = "  \n```python\ncode\n```\n  "
        assert strip_code_fences(text) == "code"

    def test_empty_string(self):
        assert strip_code_fences("") == ""

    def test_multiline_code(self):
        text = "```python\nline1\nline2\nline3\n```"
        assert strip_code_fences(text) == "line1\nline2\nline3"


class TestGenerateServer:
    async def test_returns_stripped_code(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "```python\nfrom fastmcp import FastMCP\n```"
        result = await generate_server(_sample_plan(), client)
        assert result == "from fastmcp import FastMCP"

    async def test_calls_generate_with_correct_params(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "from fastmcp import FastMCP"
        await generate_server(_sample_plan(), client)
        call_kwargs = client.generate.call_args.kwargs
        assert call_kwargs["max_tokens"] == 16384
        assert call_kwargs["temperature"] == 0.2

    async def test_plan_json_in_user_message(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "code"
        plan = _sample_plan()
        await generate_server(plan, client)
        user_msg = client.generate.call_args.kwargs["user_message"]
        assert plan.name in user_msg

    async def test_no_fence_passthrough(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "from fastmcp import FastMCP"
        result = await generate_server(_sample_plan(), client)
        assert result == "from fastmcp import FastMCP"


class TestGenerateTests:
    async def test_returns_stripped_code(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "```python\nimport pytest\n```"
        result = await generate_tests(_sample_plan(), "server_code_here", client)
        assert result == "import pytest"

    async def test_server_code_in_user_message(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "test code"
        await generate_tests(_sample_plan(), "UNIQUE_SERVER_CODE_XYZ", client)
        user_msg = client.generate.call_args.kwargs["user_message"]
        assert "UNIQUE_SERVER_CODE_XYZ" in user_msg

    async def test_calls_generate_with_correct_params(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "test code"
        await generate_tests(_sample_plan(), "code", client)
        call_kwargs = client.generate.call_args.kwargs
        assert call_kwargs["max_tokens"] == 16384
        assert call_kwargs["temperature"] == 0.2

    async def test_plan_in_user_message(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "test code"
        plan = _sample_plan()
        await generate_tests(plan, "code", client)
        user_msg = client.generate.call_args.kwargs["user_message"]
        assert plan.name in user_msg

    async def test_openapi_plan_uses_deterministic_tests(self):
        client = AsyncMock(spec=AnthropicClient)
        plan = ServerPlan(
            name="Ticket API",
            description="Ticket operations",
            tools=[
                ToolDef(
                    name="get_ticket",
                    description="Get a ticket",
                    params=[
                        ToolParam(
                            name="ticket_id",
                            type="str",
                            description="Ticket ID",
                            location="path",
                        ),
                        ToolParam(
                            name="include_history",
                            type="bool",
                            description="Include history",
                            required=False,
                            location="query",
                        ),
                    ],
                    method="GET",
                    path="/tickets/{ticket_id}",
                    auth="api_key",
                    auth_env_var="TICKET_API_KEY",
                    auth_location="header",
                    auth_parameter_name="X-API-Key",
                )
            ],
            env_vars=["BASE_URL", "TICKET_API_KEY", "REQUEST_TIMEOUT_SECONDS"],
            external_packages=["httpx"],
            openapi_metadata={"source": "openapi"},
        )

        result = await generate_tests(plan, "server code should not be sent", client)

        assert "FakeAsyncClient" in result
        assert "test_openapi_tool_http_wiring" in result
        assert "X-API-Key" in result
        assert "include_history" in result
        client.generate.assert_not_called()
