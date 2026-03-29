"""Tests for self_heal module."""

from unittest.mock import AsyncMock

from mcpforge.api_client import AnthropicClient
from mcpforge.self_heal import attempt_fix


class TestAttemptFix:
    async def test_returns_fixed_code(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "from fastmcp import FastMCP\nmcp = FastMCP('Test')"
        result = await attempt_fix("broken code", ["SyntaxError: invalid syntax"], client)
        assert result == "from fastmcp import FastMCP\nmcp = FastMCP('Test')"

    async def test_errors_in_user_message(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "fixed code"
        await attempt_fix("broken code", ["ImportError: no module named foo"], client)
        user_msg = client.generate.call_args.kwargs["user_message"]
        assert "ImportError: no module named foo" in user_msg

    async def test_code_in_user_message(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "fixed code"
        await attempt_fix("ORIGINAL_CODE_XYZ", ["error"], client)
        user_msg = client.generate.call_args.kwargs["user_message"]
        assert "ORIGINAL_CODE_XYZ" in user_msg

    async def test_uses_temperature_zero(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "fixed code"
        await attempt_fix("code", ["error"], client)
        assert client.generate.call_args.kwargs["temperature"] == 0.0

    async def test_returns_none_on_empty_response(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "   "
        result = await attempt_fix("code", ["error"], client)
        assert result is None

    async def test_returns_none_on_exception(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.side_effect = RuntimeError("API error")
        result = await attempt_fix("code", ["error"], client)
        assert result is None

    async def test_strips_code_fences(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "```python\nfixed code\n```"
        result = await attempt_fix("code", ["error"], client)
        assert result == "fixed code"

    async def test_multiple_errors_all_present(self):
        client = AsyncMock(spec=AnthropicClient)
        client.generate.return_value = "fixed"
        errors = ["SyntaxError at line 1", "ImportError: missing module", "NameError: x"]
        await attempt_fix("code", errors, client)
        user_msg = client.generate.call_args.kwargs["user_message"]
        for err in errors:
            assert err in user_msg
