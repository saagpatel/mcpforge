"""Tests for Phase 3 CLI features: update, --from-openapi, --language, --interactive."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

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


class TestUpdateCommand:
    def test_update_exits_0_on_success(self, tmp_path: Path) -> None:
        """update command exits 0 when update_server succeeds."""
        (tmp_path / "server.py").write_text("existing code")
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch(
                "mcpforge.cli.update_server",
                new=AsyncMock(return_value=("new server code", "new test code")),
            ),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            result = runner.invoke(
                cli, ["update", str(tmp_path), "add a search tool", "--yes"]
            )
        assert result.exit_code == 0

    def test_update_rewrites_server_py(self, tmp_path: Path) -> None:
        """update command writes new code to server.py."""
        (tmp_path / "server.py").write_text("old code")
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch(
                "mcpforge.cli.update_server",
                new=AsyncMock(return_value=("updated server", "updated tests")),
            ),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            runner.invoke(cli, ["update", str(tmp_path), "add search", "--yes"])
        assert (tmp_path / "server.py").read_text() == "updated server"

    def test_update_file_not_found_exits_1(self, tmp_path: Path) -> None:
        """update exits 1 when server.py doesn't exist."""
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch(
                "mcpforge.cli.update_server",
                new=AsyncMock(side_effect=FileNotFoundError("no server.py")),
            ),
        ):
            result = runner.invoke(
                cli, ["update", str(tmp_path), "add search", "--yes"]
            )
        assert result.exit_code != 0

    def test_update_calls_update_server(self, tmp_path: Path) -> None:
        """update command calls update_server with the path and request."""
        (tmp_path / "server.py").write_text("code")
        mock_update = AsyncMock(return_value=("new code", "new tests"))
        runner = CliRunner()
        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.update_server", new=mock_update),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            runner.invoke(cli, ["update", str(tmp_path), "add search tool", "--yes"])
        mock_update.assert_called_once()


class TestFromOpenAPI:
    def test_from_openapi_skips_extract_plan(self, tmp_path: Path) -> None:
        """--from-openapi skips extract_plan and calls parse_openapi instead."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(
            '{"openapi": "3.0.0", "info": {"title": "Test"}, "paths": {'
            '"/x": {"get": {"operationId": "get_x", "summary": "Get X",'
            ' "responses": {"200": {"description": "ok"}}}}}}'
        )

        mock_extract = AsyncMock(return_value=_mock_plan())
        mock_parse = MagicMock(return_value=_mock_plan())
        runner = CliRunner()

        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=mock_extract),
            patch("mcpforge.cli.parse_openapi", new=mock_parse),
            patch("mcpforge.cli.load_spec", return_value={}),
        ):
            runner.invoke(
                cli,
                [
                    "generate", "A test server",
                    "--from-openapi", str(spec_file),
                    "--dry-run", "--yes",
                ],
            )

        mock_extract.assert_not_called()
        mock_parse.assert_called_once()

    def test_from_openapi_dry_run_exits_0(self, tmp_path: Path) -> None:
        """--from-openapi --dry-run exits 0."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text("{}")
        runner = CliRunner()

        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.parse_openapi", return_value=_mock_plan()),
            patch("mcpforge.cli.load_spec", return_value={}),
        ):
            result = runner.invoke(
                cli,
                ["generate", "ignored", "--from-openapi", str(spec_file), "--dry-run", "--yes"],
            )
        assert result.exit_code == 0


class TestLanguageFlag:
    def test_language_typescript_calls_generate_server_ts(self, tmp_path: Path) -> None:
        """--language typescript calls generate_server_ts instead of the Python generator."""
        mock_gen_ts = AsyncMock(return_value="ts server code")
        mock_gen_tests_ts = AsyncMock(return_value="ts test code")
        runner = CliRunner()

        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_server_ts", new=mock_gen_ts),
            patch("mcpforge.cli.generate_tests_ts", new=mock_gen_tests_ts),
            patch("mcpforge.cli.write_server_ts", return_value=tmp_path),
            patch("mcpforge.cli.npm_install", new=AsyncMock()),
            patch("mcpforge.cli.validate_server_ts", new=AsyncMock(return_value=_valid_result())),
        ):
            result = runner.invoke(
                cli,
                [
                    "generate", "A test server",
                    "--language", "typescript",
                    "--yes",
                    "--output", str(tmp_path),
                ],
            )
        assert result.exit_code == 0
        mock_gen_ts.assert_called_once()

    def test_invalid_language_fails(self) -> None:
        """--language with invalid value exits nonzero."""
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "desc", "--language", "ruby"])
        assert result.exit_code != 0


class TestInteractiveFlag:
    def test_interactive_calls_refine_plan_on_input(self) -> None:
        """--interactive calls refine_plan when user provides feedback."""
        refined_plan = ServerPlan(
            name="Enhanced Todo",
            slug="enhanced-todo",
            description="Enhanced",
            tools=[
                ToolDef(name="create_todo", description="Create", params=[]),
                ToolDef(name="delete_todo", description="Delete", params=[]),
            ],
        )
        mock_refine = AsyncMock(return_value=refined_plan)
        runner = CliRunner()

        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.refine_plan", new=mock_refine),
        ):
            # Provide one feedback line then empty to proceed, then dry-run exits
            runner.invoke(
                cli,
                ["generate", "A todo server", "--interactive", "--dry-run"],
                input="add a delete tool\n\n",
            )

        mock_refine.assert_called_once()

    def test_interactive_empty_input_proceeds_without_refine(self) -> None:
        """--interactive with immediate empty input skips refine_plan."""
        mock_refine = AsyncMock(return_value=_mock_plan())
        runner = CliRunner()

        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.refine_plan", new=mock_refine),
        ):
            runner.invoke(
                cli,
                ["generate", "A todo server", "--interactive", "--dry-run"],
                input="\n",  # immediate empty = proceed
            )

        mock_refine.assert_not_called()
