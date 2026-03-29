"""Tests for the mcpforge CLI."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from mcpforge import __version__
from mcpforge.cli import cli
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


class TestHelp:
    def test_root_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Generate FastMCP 3.x MCP servers" in result.output

    def test_generate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--model" in result.output
        assert "--transport" in result.output
        assert "--dry-run" in result.output
        assert "--yes" in result.output

    def test_validate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0

    def test_version_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["version", "--help"])
        assert result.exit_code == 0


class TestVersion:
    def test_version_command(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestGenerate:
    def test_generate_runs_with_description(self):
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_server", new=AsyncMock(return_value="code")),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.cli.write_server", return_value=Path("/tmp/todo-manager")),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            result = runner.invoke(cli, ["generate", "A todo server", "--yes"])
        assert result.exit_code == 0

    def test_generate_missing_description_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate"])
        assert result.exit_code != 0

    def test_generate_with_all_options(self):
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_server", new=AsyncMock(return_value="code")),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.cli.write_server", return_value=Path("/tmp/test-out")),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            result = runner.invoke(
                cli,
                [
                    "generate",
                    "A todo server",
                    "--output",
                    "/tmp/test-out",
                    "--model",
                    "claude-haiku-4-5-20251001",
                    "--transport",
                    "stdio",
                    "--dry-run",
                    "--yes",
                ],
            )
        assert result.exit_code == 0

    def test_generate_invalid_transport_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "desc", "--transport", "invalid"])
        assert result.exit_code != 0

    def test_generate_dry_run_skips_generation(self):
        runner = CliRunner()
        mock_generate = AsyncMock(return_value="code")
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_server", new=mock_generate),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
        ):
            result = runner.invoke(cli, ["generate", "A todo server", "--dry-run", "--yes"])
        assert result.exit_code == 0
        mock_generate.assert_not_called()

    def test_generate_self_heal_path(self, tmp_path):
        """When first validate returns invalid, attempt_fix is called and server.py is rewritten."""
        runner = CliRunner()
        invalid_result = ValidationResult(syntax_ok=False, errors=["SyntaxError at line 1"])
        valid_result = _valid_result()
        server_py = tmp_path / "server.py"
        server_py.write_text("broken code")

        mock_validate = AsyncMock(side_effect=[invalid_result, valid_result])
        mock_fix = AsyncMock(return_value="fixed code")

        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_server", new=AsyncMock(return_value="broken code")),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.cli.write_server", return_value=tmp_path),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=mock_validate),
            patch("mcpforge.cli.attempt_fix", new=mock_fix),
        ):
            result = runner.invoke(
                cli, ["generate", "A todo server", "--yes", "--output", str(tmp_path)]
            )

        assert result.exit_code == 0
        mock_fix.assert_called_once()
        assert mock_validate.call_count == 2
        assert server_py.read_text() == "fixed code"

    def test_generate_value_error_exits_1(self):
        """ValueError from extract_plan (e.g. no tools) exits with code 1."""
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch(
                "mcpforge.cli.extract_plan",
                new=AsyncMock(side_effect=ValueError("no tools generated")),
            ),
        ):
            result = runner.invoke(cli, ["generate", "A todo server", "--yes"])
        assert result.exit_code != 0

    def test_generate_file_exists_error_exits_1(self):
        """FileExistsError from write_server exits with code 1."""
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_server", new=AsyncMock(return_value="code")),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            patch(
                "mcpforge.cli.write_server",
                side_effect=FileExistsError("dir not empty"),
            ),
        ):
            result = runner.invoke(cli, ["generate", "A todo server", "--yes"])
        assert result.exit_code != 0

    def test_generate_force_flag_passed_to_writer(self, tmp_path):
        """--force flag is forwarded to write_server."""
        runner = CliRunner()
        mock_write = patch("mcpforge.cli.write_server", return_value=tmp_path)
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_server", new=AsyncMock(return_value="code")),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            mock_write as mock_w,
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            result = runner.invoke(
                cli, ["generate", "A todo server", "--yes", "--force", "--output", str(tmp_path)]
            )
        assert result.exit_code == 0
        _, kwargs = mock_w.call_args
        assert kwargs.get("force") is True


class TestValidate:
    def test_validate_runs_with_path(self, tmp_path):
        (tmp_path / "server.py").write_text("from fastmcp import FastMCP\nmcp = FastMCP('Test')")
        runner = CliRunner()
        with patch(
            "mcpforge.cli.validate_server",
            new=AsyncMock(return_value=_valid_result()),
        ):
            result = runner.invoke(cli, ["validate", str(tmp_path)])
        assert result.exit_code == 0

    def test_validate_missing_path_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate"])
        assert result.exit_code != 0

    def test_validate_missing_server_py_fails(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(tmp_path)])
        assert result.exit_code != 0

    def test_validate_invalid_result_exits_1(self, tmp_path):
        """validate exits 1 when ValidationResult.is_valid is False."""
        (tmp_path / "server.py").write_text("from fastmcp import FastMCP\nmcp = FastMCP('Test')")
        runner = CliRunner()
        invalid = ValidationResult(syntax_ok=False, errors=["SyntaxError at line 1"])
        with patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=invalid)):
            result = runner.invoke(cli, ["validate", str(tmp_path)])
        assert result.exit_code != 0


class TestStream:
    def test_stream_flag_in_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert "--stream" in result.output

    def test_stream_flag_calls_generate_stream(self):
        """--stream uses client.generate_stream instead of generate_server."""
        runner = CliRunner()

        async def _fake_stream(*args, **kwargs):
            yield "code chunk"

        mock_client_instance = MagicMock()
        mock_client_instance.generate_stream = _fake_stream
        mock_client_class = MagicMock(return_value=mock_client_instance)

        with (
            patch("mcpforge.cli.AnthropicClient", mock_client_class),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.cli.write_server", return_value=Path("/tmp/todo-manager")),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            result = runner.invoke(cli, ["generate", "A todo server", "--stream", "--yes"])
        assert result.exit_code == 0


class TestInit:
    def test_init_creates_output_directory(self, tmp_path):
        runner = CliRunner()
        out = tmp_path / "my-server"
        result = runner.invoke(cli, ["init", "My Server", "--output", str(out)])
        assert result.exit_code == 0
        assert (out / "server.py").exists()
        assert (out / "test_server.py").exists()

    def test_init_does_not_require_api_key(self, tmp_path):
        """init works without ANTHROPIC_API_KEY set."""
        import os

        runner = CliRunner()
        out = tmp_path / "offline-server"
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        result = runner.invoke(cli, ["init", "Offline Server", "--output", str(out)], env=env)
        assert result.exit_code == 0

    def test_init_server_py_contains_mcp_tool(self, tmp_path):
        runner = CliRunner()
        out = tmp_path / "echo-server"
        runner.invoke(cli, ["init", "Echo Server", "--output", str(out)])
        content = (out / "server.py").read_text()
        assert "@mcp.tool" in content
        assert "echo" in content

    def test_init_existing_dir_fails_without_force(self, tmp_path):
        runner = CliRunner()
        out = tmp_path / "existing"
        out.mkdir()
        (out / "something.py").write_text("# existing")
        result = runner.invoke(cli, ["init", "My Server", "--output", str(out)])
        assert result.exit_code != 0

    def test_init_force_overwrites(self, tmp_path):
        runner = CliRunner()
        out = tmp_path / "existing"
        out.mkdir()
        (out / "old.py").write_text("# old")
        result = runner.invoke(cli, ["init", "My Server", "--output", str(out), "--force"])
        assert result.exit_code == 0

    def test_init_help_shows_in_root(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # 'init' command should be listed
        assert "init" in result.output
