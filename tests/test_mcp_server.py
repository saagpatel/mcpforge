"""Tests for mcpforge MCP server tools."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mcpforge import DEFAULT_MODEL
from mcpforge.discovery import ServerInfo
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


def _invalid_result() -> ValidationResult:
    return ValidationResult(syntax_ok=True, import_ok=True, tests_passed=False, tests_run=1, tests_failed=1)


class TestMcpServerTools:
    def test_default_model_matches_package_constant(self):
        from mcpforge.mcp_server import _DEFAULT_MODEL

        assert _DEFAULT_MODEL == DEFAULT_MODEL

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

    async def test_validate_tool_returns_valid_true(self, tmp_path: Path, monkeypatch):
        """validate() tool returns valid: True when server is valid."""
        from mcpforge.mcp_server import validate

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
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

    async def test_generate_tool_calls_extract_plan(self, tmp_path: Path, monkeypatch):
        """generate() tool calls extract_plan."""
        from mcpforge.mcp_server import generate

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
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

    async def test_generate_tool_applies_profiles(self, tmp_path: Path, monkeypatch):
        """generate() tool applies Python auth and middleware profiles."""
        from mcpforge.mcp_server import generate

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        with (
            patch("mcpforge.mcp_server.AnthropicClient"),
            patch("mcpforge.mcp_server.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.mcp_server.generate_server", new=AsyncMock(return_value="code")),
            patch("mcpforge.mcp_server.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.mcp_server.write_server", return_value=tmp_path) as mock_write,
            patch("mcpforge.mcp_server.uv_sync", new=AsyncMock()),
            patch(
                "mcpforge.mcp_server.validate_server",
                new=AsyncMock(return_value=_valid_result()),
            ),
        ):
            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            result = await generate(
                "A todo server",
                output_path=str(tmp_path),
                auth_profile="api-key",
                middleware_profiles=["timing"],
            )
            del os.environ["ANTHROPIC_API_KEY"]

        plan = mock_write.call_args.args[0]
        assert result["plan"]["auth_profile"] == "api-key"
        assert plan.middleware_profiles == ["timing"]

    async def test_generate_tool_dry_run_returns_plan_without_writes(self, tmp_path: Path, monkeypatch):
        """generate() dry_run returns the plan payload without generating files."""
        from mcpforge.mcp_server import generate

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        with (
            patch("mcpforge.mcp_server.AnthropicClient"),
            patch("mcpforge.mcp_server.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.mcp_server.generate_server", new=AsyncMock()) as mock_generate,
            patch("mcpforge.mcp_server.write_server") as mock_write,
        ):
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
            result = await generate("A todo server", dry_run=True)

        assert result["dry_run"] is True
        assert result["plan"]["slug"] == "todo-manager"
        mock_generate.assert_not_called()
        mock_write.assert_not_called()

    async def test_generate_tool_rejects_typescript_profiles(self, tmp_path: Path, monkeypatch):
        """TypeScript generation rejects Python-only auth and middleware profiles."""
        from fastmcp.exceptions import ToolError

        from mcpforge.mcp_server import generate

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        with (
            patch("mcpforge.mcp_server.AnthropicClient"),
            patch("mcpforge.mcp_server.extract_plan", new=AsyncMock(return_value=_mock_plan())),
        ):
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
            with pytest.raises(ToolError, match="Python-only"):
                await generate("A todo server", language="typescript", auth_profile="api-key")

    async def test_generate_tool_from_openapi_uses_spec_and_default_output(
        self, tmp_path: Path, monkeypatch
    ):
        """from_openapi loads a workspace-bound spec and defaults output to workspace/slug."""
        from mcpforge.mcp_server import generate

        spec_path = tmp_path / "openapi.json"
        spec_path.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        mock_client = object()
        with (
            patch("mcpforge.mcp_server.load_spec", return_value={"openapi": "3.1.0"}) as mock_load,
            patch("mcpforge.mcp_server.parse_openapi", return_value=_mock_plan()) as mock_parse,
            patch("mcpforge.mcp_server.AnthropicClient", return_value=mock_client),
            patch("mcpforge.mcp_server.generate_server", new=AsyncMock(return_value="code")),
            patch("mcpforge.mcp_server.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.mcp_server.write_server") as mock_write,
            patch("mcpforge.mcp_server.uv_sync", new=AsyncMock()),
            patch(
                "mcpforge.mcp_server.validate_server",
                new=AsyncMock(return_value=_valid_result()),
            ),
        ):
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
            result = await generate("ignored", from_openapi=str(spec_path))

        expected_out = tmp_path / "todo-manager"
        mock_load.assert_called_once_with(spec_path.resolve())
        mock_parse.assert_called_once_with({"openapi": "3.1.0"})
        assert mock_write.call_args.args[3] == expected_out
        assert result["path"] == str(expected_out.resolve())
        assert result["plan"]["slug"] == "todo-manager"
        assert result["valid"] is True

    async def test_generate_tool_typescript_branch_returns_validation_payload(
        self, tmp_path: Path, monkeypatch
    ):
        """language=typescript uses the TypeScript generator, writer, and validator."""
        from mcpforge.mcp_server import generate

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        with (
            patch("mcpforge.mcp_server.AnthropicClient"),
            patch("mcpforge.mcp_server.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.mcp_server.generate_server_ts", new=AsyncMock(return_value="ts code")) as gen_ts,
            patch("mcpforge.mcp_server.generate_tests_ts", new=AsyncMock(return_value="ts tests")),
            patch("mcpforge.mcp_server.write_server_ts") as write_ts,
            patch(
                "mcpforge.mcp_server.validate_server_ts",
                new=AsyncMock(return_value=_valid_result()),
            ) as validate_ts,
        ):
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
            result = await generate(
                "A todo server",
                output_path=str(tmp_path),
                language="typescript",
            )

        gen_ts.assert_awaited_once()
        write_ts.assert_called_once()
        validate_ts.assert_awaited_once_with(tmp_path.resolve())
        assert result["valid"] is True
        assert result["structurally_valid"] is True
        assert result["tests_ok"] is True

    async def test_generate_tool_multi_file_respects_no_execute_and_strict(
        self, tmp_path: Path, monkeypatch
    ):
        """multi_file forwards strict/no_execute and validates without uv sync."""
        from mcpforge.mcp_server import generate

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        mock_validate = AsyncMock(return_value=_valid_result())
        with (
            patch("mcpforge.mcp_server.AnthropicClient"),
            patch("mcpforge.mcp_server.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch(
                "mcpforge.mcp_server.generate_server_multi",
                new=AsyncMock(return_value={"server.py": "server code", "helpers.py": "helper code"}),
            ) as gen_multi,
            patch("mcpforge.mcp_server.generate_tests", new=AsyncMock(return_value="tests")) as gen_tests,
            patch("mcpforge.mcp_server.write_server_multi") as write_multi,
            patch("mcpforge.mcp_server.uv_sync", new=AsyncMock()) as uv_sync,
            patch("mcpforge.mcp_server.validate_server", new=mock_validate),
        ):
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
            result = await generate(
                "A todo server",
                output_path=str(tmp_path),
                multi_file=True,
                no_execute=True,
                strict=True,
            )

        gen_multi.assert_awaited_once()
        gen_tests.assert_awaited_once()
        write_multi.assert_called_once()
        uv_sync.assert_not_awaited()
        mock_validate.assert_awaited_once_with(tmp_path.resolve(), skip_execution=True, strict=True)
        assert result["valid"] is True
        assert result["tests_run"] == 0

    async def test_generate_tool_multi_file_runs_uv_sync_by_default(
        self, tmp_path: Path, monkeypatch
    ):
        """multi_file runs uv sync before validation unless no_execute is set."""
        from mcpforge.mcp_server import generate

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        with (
            patch("mcpforge.mcp_server.AnthropicClient"),
            patch("mcpforge.mcp_server.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch(
                "mcpforge.mcp_server.generate_server_multi",
                new=AsyncMock(return_value={"server.py": "server code"}),
            ),
            patch("mcpforge.mcp_server.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.mcp_server.write_server_multi"),
            patch("mcpforge.mcp_server.uv_sync", new=AsyncMock()) as uv_sync,
            patch(
                "mcpforge.mcp_server.validate_server",
                new=AsyncMock(return_value=_valid_result()),
            ),
        ):
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
            result = await generate("A todo server", output_path=str(tmp_path), multi_file=True)

        uv_sync.assert_awaited_once_with(tmp_path.resolve(), plan=_mock_plan())
        assert result["valid"] is True
        assert result["tests_ok"] is True

    async def test_generate_tool_python_no_execute_strict_returns_invalid_payload(
        self, tmp_path: Path, monkeypatch
    ):
        """Python generation reports failed tests without collapsing structural validity."""
        from mcpforge.mcp_server import generate

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        mock_validate = AsyncMock(return_value=_invalid_result())
        with (
            patch("mcpforge.mcp_server.AnthropicClient"),
            patch("mcpforge.mcp_server.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.mcp_server.generate_server", new=AsyncMock(return_value="code")),
            patch("mcpforge.mcp_server.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.mcp_server.write_server"),
            patch("mcpforge.mcp_server.uv_sync", new=AsyncMock()) as uv_sync,
            patch("mcpforge.mcp_server.validate_server", new=mock_validate),
        ):
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
            result = await generate(
                "A todo server",
                output_path=str(tmp_path),
                no_execute=True,
                strict=True,
            )

        uv_sync.assert_not_awaited()
        mock_validate.assert_awaited_once_with(tmp_path.resolve(), skip_execution=True, strict=True)
        assert result["valid"] is False
        assert result["structurally_valid"] is True
        assert result["tests_ok"] is False
        assert result["tests_run"] == 1

    async def test_update_tool_calls_update_server(self, tmp_path: Path, monkeypatch):
        """update() tool calls update_server and writes files."""
        from mcpforge.mcp_server import update

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
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

    def test_get_client_uses_non_anthropic_provider_without_anthropic_key(self, monkeypatch):
        """_get_client delegates non-Anthropic providers to provider factory."""
        from mcpforge.mcp_server import _get_client

        provider_client = object()
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with patch("mcpforge.mcp_server.create_provider_client", return_value=provider_client) as factory:
            result = _get_client(model="other-model", provider="openai")

        factory.assert_called_once_with("openai", model="other-model")
        assert result is provider_client

    def test_get_client_converts_provider_value_error_to_tool_error(self, monkeypatch):
        """_get_client exposes provider configuration errors as ToolError."""
        from fastmcp.exceptions import ToolError

        from mcpforge.mcp_server import _get_client

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with patch("mcpforge.mcp_server.create_provider_client", side_effect=ValueError("bad provider")):
            with pytest.raises(ToolError, match="bad provider"):
                _get_client(provider="openai")

    async def test_validate_tool_detects_typescript_server(self, tmp_path: Path, monkeypatch):
        """validate() uses TypeScript validation when src/server.ts is present without server.py."""
        from mcpforge.mcp_server import validate

        server_dir = tmp_path / "ts-server"
        (server_dir / "src").mkdir(parents=True)
        (server_dir / "src" / "server.ts").write_text("server.tool('x')", encoding="utf-8")
        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        with (
            patch(
                "mcpforge.mcp_server.validate_server_ts",
                new=AsyncMock(return_value=_valid_result()),
            ) as validate_ts,
            patch("mcpforge.mcp_server.validate_server", new=AsyncMock()) as validate_py,
        ):
            result = await validate(str(server_dir))

        validate_ts.assert_awaited_once_with(server_dir.resolve())
        validate_py.assert_not_awaited()
        assert result["valid"] is True
        assert result["structurally_valid"] is True
        assert result["tests_ok"] is True

    async def test_inspect_tool_resolves_workspace_path_and_returns_payload(
        self, tmp_path: Path, monkeypatch
    ):
        """inspect() returns inspect_server payload for a workspace-bound path."""
        from mcpforge.mcp_server import inspect

        server_dir = tmp_path / "server"
        server_dir.mkdir()
        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        payload = {"name": "Todo Manager", "tools": [{"name": "create_todo"}]}
        with patch("mcpforge.mcp_server.inspect_server", return_value=payload) as inspect_server:
            result = await inspect(str(server_dir))

        inspect_server.assert_called_once_with(server_dir.resolve())
        assert result["name"] == "Todo Manager"
        assert result["tools"][0]["name"] == "create_todo"

    async def test_doctor_tool_uses_explicit_workspace_path(self, tmp_path: Path, monkeypatch):
        """doctor() accepts an explicit workspace path and returns run_doctor payload."""
        from mcpforge.mcp_server import doctor

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        payload = {"ok": True, "providers": {"anthropic": {"configured": False}}}
        with patch("mcpforge.mcp_server.run_doctor", return_value=payload) as run_doctor:
            result = await doctor(str(workspace))

        run_doctor.assert_called_once_with(workspace.resolve())
        assert result["ok"] is True
        assert result["providers"]["anthropic"]["configured"] is False

    async def test_doctor_tool_defaults_to_workspace_env(self, tmp_path: Path, monkeypatch):
        """doctor() defaults to MCPFORGE_WORKSPACE when no path is provided."""
        from mcpforge.mcp_server import doctor

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        with patch("mcpforge.mcp_server.run_doctor", return_value={"ok": True}) as run_doctor:
            result = await doctor()

        run_doctor.assert_called_once_with(tmp_path.resolve())
        assert result["ok"] is True

    async def test_list_generated_servers_tool_returns_structured_servers(
        self, tmp_path: Path, monkeypatch
    ):
        """list_generated_servers() returns normalized server dicts from discovery."""
        from mcpforge.mcp_server import list_generated_servers

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        server_path = workspace / "todo"
        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        servers = [
            ServerInfo(
                path=server_path,
                name="todo",
                language="python",
                tool_count=2,
                has_tests=True,
            )
        ]
        with patch("mcpforge.mcp_server.find_servers", return_value=servers) as find_servers:
            result = await list_generated_servers(str(workspace), recursive=False)

        find_servers.assert_called_once_with(workspace.resolve(), recursive=False)
        assert result["root"] == str(workspace.resolve())
        assert result["servers"] == [
            {
                "path": str(server_path),
                "name": "todo",
                "language": "python",
                "tool_count": 2,
                "has_tests": True,
            }
        ]

    async def test_list_generated_servers_tool_defaults_to_workspace_env(
        self, tmp_path: Path, monkeypatch
    ):
        """list_generated_servers() uses MCPFORGE_WORKSPACE when no path is provided."""
        from mcpforge.mcp_server import list_generated_servers

        monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
        with patch("mcpforge.mcp_server.find_servers", return_value=[]) as find_servers:
            result = await list_generated_servers()

        find_servers.assert_called_once_with(tmp_path.resolve(), recursive=True)
        assert result["root"] == str(tmp_path.resolve())
        assert result["servers"] == []

    def test_mcp_server_has_correct_name(self):
        """mcpforge MCP server is named 'mcpforge'."""
        from mcpforge.mcp_server import mcp

        assert mcp.name == "mcpforge"


class TestWorkspaceBoundary:
    """Tests for _resolve_workspace_path workspace enforcement."""

    def test_path_within_workspace_allowed(self, tmp_path: Path):
        from mcpforge.mcp_server import _resolve_workspace_path

        subdir = tmp_path / "project"
        subdir.mkdir()
        os.environ["MCPFORGE_WORKSPACE"] = str(tmp_path)
        try:
            result = _resolve_workspace_path(str(subdir))
            assert result == subdir.resolve()
        finally:
            del os.environ["MCPFORGE_WORKSPACE"]

    def test_path_outside_workspace_rejected(self, tmp_path: Path):
        from fastmcp.exceptions import ToolError

        from mcpforge.mcp_server import _resolve_workspace_path

        os.environ["MCPFORGE_WORKSPACE"] = str(tmp_path)
        try:
            with pytest.raises(ToolError, match="outside workspace"):
                _resolve_workspace_path("/etc")
        finally:
            del os.environ["MCPFORGE_WORKSPACE"]

    def test_dotdot_escape_rejected(self, tmp_path: Path):
        from fastmcp.exceptions import ToolError

        from mcpforge.mcp_server import _resolve_workspace_path

        os.environ["MCPFORGE_WORKSPACE"] = str(tmp_path)
        try:
            with pytest.raises(ToolError, match="outside workspace"):
                _resolve_workspace_path(str(tmp_path / ".." / ".." / "etc" / "passwd"))
        finally:
            del os.environ["MCPFORGE_WORKSPACE"]

    def test_must_exist_flag(self, tmp_path: Path):
        from fastmcp.exceptions import ToolError

        from mcpforge.mcp_server import _resolve_workspace_path

        os.environ["MCPFORGE_WORKSPACE"] = str(tmp_path)
        try:
            with pytest.raises(ToolError, match="does not exist"):
                _resolve_workspace_path(str(tmp_path / "nonexistent"), must_exist=True)
        finally:
            del os.environ["MCPFORGE_WORKSPACE"]

    def test_default_workspace_is_cwd(self, tmp_path: Path, monkeypatch):
        from mcpforge.mcp_server import _resolve_workspace_path

        monkeypatch.delenv("MCPFORGE_WORKSPACE", raising=False)
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "sub"
        subdir.mkdir()
        result = _resolve_workspace_path(str(subdir))
        assert result == subdir.resolve()
