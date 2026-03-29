"""Tests for the mcpforge CLI."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

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
