"""Tests for mcpforge discovery module."""

import json
from pathlib import Path

from mcpforge.discovery import find_servers


def _make_python_server(
    root: Path, name: str, tool_count: int = 2, has_tests: bool = True
) -> Path:
    """Create a fake mcpforge Python server directory."""
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    # config.json
    (d / "config.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    name: {"command": "uv", "args": ["run", "server.py"], "env": {}}
                }
            }
        )
    )
    # server.py with tool_count @mcp.tool occurrences
    tools = "\n".join(
        f"@mcp.tool\nasync def tool_{i}(): pass" for i in range(tool_count)
    )
    (d / "server.py").write_text(
        f"from fastmcp import FastMCP\nmcp = FastMCP('Test')\n{tools}"
    )
    if has_tests:
        (d / "test_server.py").write_text("# tests")
    return d


def _make_ts_server(root: Path, name: str) -> Path:
    """Create a fake mcpforge TypeScript server directory."""
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps({"mcpServers": {name: {}}}))
    src = d / "src"
    src.mkdir()
    (src / "server.ts").write_text(
        'server.tool("t1", "desc", {}, async () => ({}));\n'
        'server.tool("t2", "desc", {}, async () => ({}));'
    )
    (src / "server.test.ts").write_text("// tests")
    return d


class TestFindServers:
    def test_finds_python_server(self, tmp_path):
        _make_python_server(tmp_path, "my-server")
        servers = find_servers(tmp_path)
        assert len(servers) == 1
        assert servers[0].name == "my-server"
        assert servers[0].language == "python"

    def test_ignores_dir_without_config(self, tmp_path):
        d = tmp_path / "not-a-server"
        d.mkdir()
        (d / "server.py").write_text("code")
        servers = find_servers(tmp_path)
        assert servers == []

    def test_ignores_config_without_mcp_servers_key(self, tmp_path):
        d = tmp_path / "other"
        d.mkdir()
        (d / "config.json").write_text('{"other": "value"}')
        (d / "server.py").write_text("code")
        servers = find_servers(tmp_path)
        assert servers == []

    def test_ignores_dir_without_server_file(self, tmp_path):
        d = tmp_path / "incomplete"
        d.mkdir()
        (d / "config.json").write_text('{"mcpServers": {"incomplete": {}}}')
        servers = find_servers(tmp_path)
        assert servers == []

    def test_detects_typescript_server(self, tmp_path):
        _make_ts_server(tmp_path, "ts-server")
        servers = find_servers(tmp_path)
        assert len(servers) == 1
        assert servers[0].language == "typescript"

    def test_counts_tools_python(self, tmp_path):
        _make_python_server(tmp_path, "tool-counter", tool_count=3)
        servers = find_servers(tmp_path)
        assert servers[0].tool_count == 3

    def test_counts_tools_typescript(self, tmp_path):
        _make_ts_server(tmp_path, "ts-tools")
        servers = find_servers(tmp_path)
        assert servers[0].tool_count == 2

    def test_has_tests_true(self, tmp_path):
        _make_python_server(tmp_path, "tested", has_tests=True)
        servers = find_servers(tmp_path)
        assert servers[0].has_tests is True

    def test_has_tests_false(self, tmp_path):
        _make_python_server(tmp_path, "untested", has_tests=False)
        servers = find_servers(tmp_path)
        assert servers[0].has_tests is False

    def test_sorted_by_name(self, tmp_path):
        _make_python_server(tmp_path, "zebra")
        _make_python_server(tmp_path, "alpha")
        _make_python_server(tmp_path, "middle")
        servers = find_servers(tmp_path)
        assert [s.name for s in servers] == ["alpha", "middle", "zebra"]

    def test_non_recursive_does_not_descend(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        _make_python_server(subdir, "nested-server")
        servers = find_servers(tmp_path, recursive=False)
        assert servers == []

    def test_recursive_finds_nested_servers(self, tmp_path):
        subdir = tmp_path / "level1" / "level2"
        subdir.mkdir(parents=True)
        _make_python_server(subdir, "deep-server")
        servers = find_servers(tmp_path, recursive=True)
        assert len(servers) == 1
        assert servers[0].name == "deep-server"

    def test_multiple_servers(self, tmp_path):
        _make_python_server(tmp_path, "server-a")
        _make_python_server(tmp_path, "server-b")
        _make_ts_server(tmp_path, "server-c")
        servers = find_servers(tmp_path)
        assert len(servers) == 3
