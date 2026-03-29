"""Tests for the Database Query MCP server."""

import importlib

import aiosqlite
import pytest
import server as srv
from fastmcp import Client


@pytest.fixture
async def db(tmp_path, monkeypatch):
    """Create a temp SQLite database and point the server at it."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    importlib.reload(srv)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        await conn.execute("INSERT INTO items VALUES (1, 'apple')")
        await conn.execute("INSERT INTO items VALUES (2, 'banana')")
        await conn.commit()
    yield db_path


async def test_list_tables(db):
    async with Client(srv.mcp) as client:
        result = await client.call_tool("list_tables", {})
    assert "items" in result.data["tables"]


async def test_query_select(db):
    async with Client(srv.mcp) as client:
        result = await client.call_tool(
            "query_database", {"sql": "SELECT * FROM items ORDER BY id"}
        )
    assert result.data["count"] == 2
    assert result.data["rows"][0]["name"] == "apple"


async def test_query_rejects_non_select(db):
    async with Client(srv.mcp) as client:
        with pytest.raises(Exception, match="Only SELECT"):
            await client.call_tool(
                "query_database", {"sql": "DROP TABLE items"}
            )


async def test_describe_table(db):
    async with Client(srv.mcp) as client:
        result = await client.call_tool("describe_table", {"table_name": "items"})
    assert result.data["table"] == "items"
    col_names = [c["name"] for c in result.data["columns"]]
    assert "id" in col_names
    assert "name" in col_names


async def test_describe_nonexistent_table(db):
    async with Client(srv.mcp) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("describe_table", {"table_name": "nonexistent"})


async def test_describe_table_invalid_identifier(db):
    async with Client(srv.mcp) as client:
        with pytest.raises(Exception, match="Invalid identifier"):
            await client.call_tool("describe_table", {"table_name": "items; DROP TABLE items"})
