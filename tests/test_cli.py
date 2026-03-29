"""Tests for the mcpforge CLI."""

from click.testing import CliRunner

from mcpforge import __version__
from mcpforge.cli import cli


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
        result = runner.invoke(cli, ["generate", "A todo server"])
        assert result.exit_code == 0

    def test_generate_missing_description_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate"])
        assert result.exit_code != 0

    def test_generate_with_all_options(self):
        runner = CliRunner()
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


class TestValidate:
    def test_validate_runs_with_path(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "/tmp/some-server"])
        assert result.exit_code == 0

    def test_validate_missing_path_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate"])
        assert result.exit_code != 0
