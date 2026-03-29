"""Tests for mcpforge multi-file server generator."""

import json
from unittest.mock import AsyncMock, patch

from mcpforge.generator import generate_server_multi
from mcpforge.models import ServerPlan, ToolDef


def _mock_plan_many_tools() -> ServerPlan:
    return ServerPlan(
        name="Big Server",
        slug="big-server",
        description="A server with many tools",
        tools=[
            ToolDef(name=f"tool_{i}", description=f"Tool {i}", params=[])
            for i in range(5)
        ],
    )


class TestGenerateServerMulti:
    async def test_returns_dict_with_server_py(self):
        """generate_server_multi returns dict containing 'server.py' key."""
        plan = _mock_plan_many_tools()
        mock_client = AsyncMock()
        response = json.dumps({
            "server.py": "from fastmcp import FastMCP\nmcp = FastMCP('Test')",
            "tools/crud.py": "async def create(): pass",
        })
        mock_client.generate = AsyncMock(return_value=response)
        with patch("mcpforge.generator.load_prompt", return_value="system"):
            result = await generate_server_multi(plan, mock_client)
        assert "server.py" in result
        assert "tools/crud.py" in result

    async def test_malformed_json_fallback(self):
        """Malformed JSON response falls back to single-file dict."""
        plan = _mock_plan_many_tools()
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="not valid json { broken")
        with patch("mcpforge.generator.load_prompt", return_value="system"):
            result = await generate_server_multi(plan, mock_client)
        assert "server.py" in result

    async def test_missing_server_py_key_fallback(self):
        """JSON missing 'server.py' key falls back to single-file dict."""
        plan = _mock_plan_many_tools()
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value='{"tools/crud.py": "code"}')
        with patch("mcpforge.generator.load_prompt", return_value="system"):
            result = await generate_server_multi(plan, mock_client)
        assert "server.py" in result

    async def test_calls_client_with_multi_file_prompt(self):
        """generate_server_multi loads the 'generator_multi' prompt."""
        plan = _mock_plan_many_tools()
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value='{"server.py": "code"}')
        with patch("mcpforge.generator.load_prompt", return_value="system") as mock_load:
            await generate_server_multi(plan, mock_client)
        mock_load.assert_called_with("generator_multi")

    async def test_template_hint_appended_to_prompt(self):
        """Template hint is appended to system prompt when provided."""
        plan = _mock_plan_many_tools()
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value='{"server.py": "code"}')
        with patch("mcpforge.generator.load_prompt", return_value="base prompt"):
            await generate_server_multi(plan, mock_client, template_hint="use httpx")
        call_kwargs = mock_client.generate.call_args.kwargs
        assert "use httpx" in call_kwargs["system_prompt"]

    async def test_all_values_are_strings(self):
        """All values in returned dict are strings."""
        plan = _mock_plan_many_tools()
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=json.dumps({
            "server.py": "code1",
            "tools/a.py": "code2",
        }))
        with patch("mcpforge.generator.load_prompt", return_value="system"):
            result = await generate_server_multi(plan, mock_client)
        for v in result.values():
            assert isinstance(v, str)
