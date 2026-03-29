"""Tests for the File Reader MCP server."""

import importlib

import pytest
import server as srv
from fastmcp import Client


@pytest.fixture
def file_root(tmp_path, monkeypatch):
    """Set FILES_ROOT to a temp directory and reload the server module."""
    monkeypatch.setenv("FILES_ROOT", str(tmp_path))
    importlib.reload(srv)
    (tmp_path / "hello.txt").write_text("Hello, world!")
    (tmp_path / "notes.txt").write_text("Some notes")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("Nested file")
    yield tmp_path


async def test_read_file_success(file_root):
    async with Client(srv.mcp) as client:
        result = await client.call_tool("read_file", {"path": "hello.txt"})
    assert result.data["content"] == "Hello, world!"


async def test_read_file_not_found(file_root):
    async with Client(srv.mcp) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("read_file", {"path": "nonexistent.txt"})


async def test_path_traversal_blocked(file_root):
    async with Client(srv.mcp) as client:
        with pytest.raises(Exception, match="Access denied"):
            await client.call_tool("read_file", {"path": "../../etc/passwd"})


async def test_list_files_root(file_root):
    async with Client(srv.mcp) as client:
        result = await client.call_tool("list_files", {})
    assert "hello.txt" in result.data["files"]
    assert "notes.txt" in result.data["files"]
    assert "subdir" in result.data["subdirectories"]


async def test_search_files(file_root):
    async with Client(srv.mcp) as client:
        result = await client.call_tool("search_files", {"pattern": "**/*.txt"})
    assert "hello.txt" in result.data["matches"] or any(
        "hello.txt" in m for m in result.data["matches"]
    )


async def test_get_file_info(file_root):
    async with Client(srv.mcp) as client:
        result = await client.call_tool("get_file_info", {"path": "hello.txt"})
    assert result.data["is_file"] is True
    assert result.data["size"] > 0
