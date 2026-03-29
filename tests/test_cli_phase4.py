"""Phase 4 CLI integration tests: list, init, stream."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from mcpforge.cli import cli
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


class TestListCommand:
    def test_list_shows_servers(self, tmp_path):
        """list command displays found servers in a table."""
        mock_servers = [
            ServerInfo(
                path=tmp_path / "server-a",
                name="server-a",
                tool_count=3,
                has_tests=True,
                language="python",
            ),
        ]
        runner = CliRunner()
        with patch("mcpforge.cli.find_servers", return_value=mock_servers):
            result = runner.invoke(cli, ["list", str(tmp_path)])
        assert result.exit_code == 0
        assert "server-a" in result.output

    def test_list_no_servers_message(self, tmp_path):
        """list outputs a message when no servers found."""
        runner = CliRunner()
        with patch("mcpforge.cli.find_servers", return_value=[]):
            result = runner.invoke(cli, ["list", str(tmp_path)])
        assert result.exit_code == 0
        assert "No mcpforge servers found" in result.output

    def test_list_recursive_flag_passed(self, tmp_path):
        """--recursive flag is forwarded to find_servers."""
        mock_find = MagicMock(return_value=[])
        runner = CliRunner()
        with patch("mcpforge.cli.find_servers", mock_find):
            runner.invoke(cli, ["list", str(tmp_path), "--recursive"])
        _, kwargs = mock_find.call_args
        assert kwargs.get("recursive") is True

    def test_list_default_path_is_cwd(self):
        """list with no path argument uses current directory."""
        mock_find = MagicMock(return_value=[])
        runner = CliRunner()
        with patch("mcpforge.cli.find_servers", mock_find):
            result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        mock_find.assert_called_once()

    def test_list_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--help"])
        assert result.exit_code == 0
        assert "--recursive" in result.output


class TestInitCommand:
    def test_init_exits_0(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "Test Server", "--output", str(tmp_path / "out")])
        assert result.exit_code == 0

    def test_init_creates_server_py(self, tmp_path):
        out = tmp_path / "out"
        runner = CliRunner()
        runner.invoke(cli, ["init", "My API Server", "--output", str(out)])
        assert (out / "server.py").exists()

    def test_init_no_api_key_needed(self, tmp_path):
        import os

        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        out = tmp_path / "out"
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "Offline", "--output", str(out)], env=env)
        assert result.exit_code == 0


class TestMultiFileFlag:
    def test_multi_file_flag_present_in_generate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert "--multi-file" in result.output

    def test_multi_file_calls_generate_server_multi(self):
        """--multi-file calls generate_server_multi and write_server_multi."""
        runner = CliRunner()
        mock_files = {"server.py": "# generated", "tools/crud.py": "# tools"}

        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch(
                "mcpforge.cli.generate_server_multi",
                new=AsyncMock(return_value=mock_files),
            ),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.cli.write_server_multi", return_value=Path("/tmp/todo")),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            result = runner.invoke(cli, ["generate", "A server", "--multi-file", "--yes"])

        assert result.exit_code == 0

    def test_multi_file_does_not_call_generate_server(self):
        """--multi-file does NOT call the single-file generate_server."""
        runner = CliRunner()
        mock_files = {"server.py": "# generated"}
        mock_single = AsyncMock()

        with (
            patch("mcpforge.cli.AnthropicClient"),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_server", mock_single),
            patch(
                "mcpforge.cli.generate_server_multi",
                new=AsyncMock(return_value=mock_files),
            ),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.cli.write_server_multi", return_value=Path("/tmp/todo")),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            runner.invoke(cli, ["generate", "A server", "--multi-file", "--yes"])

        mock_single.assert_not_called()


class TestStreamFlag:
    def test_stream_flag_present_in_generate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert "--stream" in result.output

    def test_stream_uses_generate_stream_not_generate_server(self):
        """With --stream, generate_stream is called instead of generate_server."""
        runner = CliRunner()

        async def _fake_stream(*args, **kwargs):
            yield "server code here"

        mock_client_instance = MagicMock()
        mock_client_instance.generate_stream = _fake_stream
        mock_client_class = MagicMock(return_value=mock_client_instance)

        with (
            patch("mcpforge.cli.AnthropicClient", mock_client_class),
            patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=_mock_plan())),
            patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
            patch("mcpforge.cli.write_server", return_value=Path("/tmp/todo")),
            patch("mcpforge.cli.uv_sync", new=AsyncMock()),
            patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=_valid_result())),
        ):
            result = runner.invoke(cli, ["generate", "A server", "--stream", "--yes"])

        assert result.exit_code == 0
