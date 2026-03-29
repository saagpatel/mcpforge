"""Tests for template hints module and --template CLI flag."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from mcpforge.cli import cli
from mcpforge.models import ServerPlan, ToolDef, ValidationResult
from mcpforge.template_hints import TEMPLATE_HINTS


def _mock_plan() -> ServerPlan:
    return ServerPlan(
        name="Test Server",
        slug="test-server",
        description="A test server",
        tools=[ToolDef(name="test_tool", description="Test tool", params=[])],
    )


def _valid_result() -> ValidationResult:
    return ValidationResult(syntax_ok=True, import_ok=True)


class TestTemplateHints:
    def test_hints_dict_is_not_empty(self):
        assert len(TEMPLATE_HINTS) >= 3

    def test_all_values_are_non_empty_strings(self):
        for key, value in TEMPLATE_HINTS.items():
            assert isinstance(value, str)
            assert value.strip()

    def test_known_keys_present(self):
        for key in ("rest-api", "database", "filesystem"):
            assert key in TEMPLATE_HINTS

    def test_rest_api_hint_mentions_httpx(self):
        assert "httpx" in TEMPLATE_HINTS["rest-api"].lower()

    def test_database_hint_mentions_parameterization(self):
        hint = TEMPLATE_HINTS["database"].lower()
        assert "parameterize" in hint or "parameterized" in hint

    def test_filesystem_hint_mentions_path_traversal(self):
        assert "path traversal" in TEMPLATE_HINTS["filesystem"].lower()


class TestTemplateCLIFlag:
    def test_invalid_template_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "desc", "--template", "nonexistent"])
        assert result.exit_code != 0

    def test_template_flag_accepted_dry_run(self):
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
        ):
            result = runner.invoke(
                cli,
                [
                    "generate",
                    "A REST API server",
                    "--template",
                    "rest-api",
                    "--dry-run",
                    "--yes",
                ],
            )
        assert result.exit_code == 0

    def test_template_hint_forwarded_to_generate_server(self, tmp_path: Path):
        mock_generate = AsyncMock(return_value="code")
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_server", new=mock_generate),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.cli.write_server", return_value=tmp_path),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            runner.invoke(
                cli,
                [
                    "generate",
                    "A REST API server",
                    "--template",
                    "rest-api",
                    "--yes",
                    "--output",
                    str(tmp_path),
                ],
            )
        mock_generate.assert_called_once()
        _, kwargs = mock_generate.call_args
        assert kwargs.get("template_hint") == TEMPLATE_HINTS["rest-api"]

    def test_no_template_passes_empty_hint(self, tmp_path: Path):
        mock_generate = AsyncMock(return_value="code")
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_server", new=mock_generate),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.cli.write_server", return_value=tmp_path),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            runner.invoke(
                cli,
                ["generate", "A server", "--yes", "--output", str(tmp_path)],
            )
        mock_generate.assert_called_once()
        _, kwargs = mock_generate.call_args
        assert kwargs.get("template_hint") == ""
