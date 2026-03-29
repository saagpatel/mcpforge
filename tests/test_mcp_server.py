"""Tests for mcpforge MCP server tools."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mcpforge.models import ServerPlan, ToolDef, ValidationResult


def _mock_plan() -> ServerPlan:
    return ServerPlan(
        name="Todo Manager",
        slug="todo-manager",
        description="A todo server",
        tools=[ToolDef(name="create_todo", description="Create todo", params=[])],
    )


def _valid_result() -> ValidationResult:
    return ValidationResult(syntax_ok=True, import_ok=True)


class TestMcpServerTools:
    async def test_plan_tool_returns_name_and_tools(self):
        """plan() tool returns dict with name, slug, tools keys."""
        from mcpforge.mcp_server import plan

        with (
            patch("mcpforge.mcp_server.AnthropicClient"),
            patch(
                "mcpforge.mcp_server.extract_plan",
                new=AsyncMock(return_value=_mock_plan()),
            ),
        ):
            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            result = await plan("A todo server")
            del os.environ["ANTHROPIC_API_KEY"]

        assert result["name"] == "Todo Manager"
        assert result["slug"] == "todo-manager"
        assert isinstance(result["tools"], list)
        assert result["tools"][0]["name"] == "create_todo"

    async def test_validate_tool_returns_valid_true(self, tmp_path: Path):
        """validate() tool returns valid: True when server is valid."""
        from mcpforge.mcp_server import validate

        (tmp_path / "server.py").write_text("code")
        with patch(
            "mcpforge.mcp_server.validate_server",
            new=AsyncMock(return_value=_valid_result()),
        ):
            result = await validate(str(tmp_path))

        assert result["valid"] is True
        assert result["syntax_ok"] is True
        assert result["import_ok"] is True
        assert isinstance(result["lint_errors"], list)

    async def test_generate_tool_calls_extract_plan(self, tmp_path: Path):
        """generate() tool calls extract_plan."""
        from mcpforge.mcp_server import generate

        mock_extract = AsyncMock(return_value=_mock_plan())
        with (
            patch("mcpforge.mcp_server.AnthropicClient"),
            patch("mcpforge.mcp_server.extract_plan", new=mock_extract),
            patch("mcpforge.mcp_server.generate_server", new=AsyncMock(return_value="code")),
            patch("mcpforge.mcp_server.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.mcp_server.write_server", return_value=tmp_path),
            patch("mcpforge.mcp_server.uv_sync", new=AsyncMock()),
            patch(
                "mcpforge.mcp_server.validate_server",
                new=AsyncMock(return_value=_valid_result()),
            ),
        ):
            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            result = await generate("A todo server", output_path=str(tmp_path))
            del os.environ["ANTHROPIC_API_KEY"]

        mock_extract.assert_called_once()
        assert "plan" in result
        assert "valid" in result

    async def test_update_tool_calls_update_server(self, tmp_path: Path):
        """update() tool calls update_server and writes files."""
        from mcpforge.mcp_server import update

        (tmp_path / "server.py").write_text("old code")
        with (
            patch("mcpforge.mcp_server.AnthropicClient"),
            patch(
                "mcpforge.mcp_server.update_server",
                new=AsyncMock(return_value=("new code", "new tests")),
            ),
            patch("mcpforge.mcp_server.uv_sync", new=AsyncMock()),
            patch(
                "mcpforge.mcp_server.validate_server",
                new=AsyncMock(return_value=_valid_result()),
            ),
        ):
            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            result = await update(str(tmp_path), "add search tool")
            del os.environ["ANTHROPIC_API_KEY"]

        assert result["valid"] is True
        assert (tmp_path / "server.py").read_text() == "new code"

    async def test_missing_api_key_raises_tool_error(self):
        """_get_client raises ToolError when ANTHROPIC_API_KEY is not set."""
        from fastmcp.exceptions import ToolError

        from mcpforge.mcp_server import _get_client

        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(ToolError):
                _get_client()
        finally:
            if saved:
                os.environ["ANTHROPIC_API_KEY"] = saved

    def test_mcp_server_has_correct_name(self):
        """mcpforge MCP server is named 'mcpforge'."""
        from mcpforge.mcp_server import mcp

        assert mcp.name == "mcpforge"
