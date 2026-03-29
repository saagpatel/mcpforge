"""Tests for the Todo Manager MCP server."""

import pytest
import server
from fastmcp import Client
from server import mcp


@pytest.fixture(autouse=True)
def reset_state():
    """Reset in-memory state before each test."""
    server._todos.clear()
    server._next_id = 1
    yield


async def test_create_todo_success():
    async with Client(mcp) as client:
        result = await client.call_tool("create_todo", {"title": "Buy milk"})
    assert result.data["id"] == "1"
    assert result.data["title"] == "Buy milk"
    assert result.data["done"] is False


async def test_create_todo_with_description():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "create_todo", {"title": "Buy milk", "description": "Whole milk"}
        )
    assert result.data["description"] == "Whole milk"


async def test_create_todo_empty_title_raises():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="empty"):
            await client.call_tool("create_todo", {"title": "  "})


async def test_get_todo_success():
    async with Client(mcp) as client:
        await client.call_tool("create_todo", {"title": "Task"})
        result = await client.call_tool("get_todo", {"todo_id": "1"})
    assert result.data["id"] == "1"


async def test_get_todo_not_found():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("get_todo", {"todo_id": "999"})


async def test_list_todos_empty():
    async with Client(mcp) as client:
        result = await client.call_tool("list_todos", {})
    assert result.data == []


async def test_list_todos_non_empty():
    async with Client(mcp) as client:
        await client.call_tool("create_todo", {"title": "A"})
        await client.call_tool("create_todo", {"title": "B"})
        result = await client.call_tool("list_todos", {})
    assert len(result.data) == 2


async def test_update_todo_done():
    async with Client(mcp) as client:
        await client.call_tool("create_todo", {"title": "Task"})
        result = await client.call_tool("update_todo", {"todo_id": "1", "done": True})
    assert result.data["done"] is True


async def test_update_todo_not_found():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("update_todo", {"todo_id": "999", "done": True})


async def test_delete_todo_success():
    async with Client(mcp) as client:
        await client.call_tool("create_todo", {"title": "Task"})
        result = await client.call_tool("delete_todo", {"todo_id": "1"})
    assert result.data["deleted"] is True
    assert "1" not in server._todos


async def test_delete_todo_not_found():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("delete_todo", {"todo_id": "999"})
