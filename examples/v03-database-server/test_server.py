"""Tests for the SQLite Analytics Server MCP server."""

import os
import sqlite3
import tempfile

import pytest

os.environ.setdefault("DATABASE_PATH", "/tmp/mcpforge-v03-test-placeholder.db")

import server
from fastmcp import Client
from server import mcp

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def tmp_db():
    """Create a temporary SQLite database for testing and point the server at it."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            age INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            amount REAL NOT NULL,
            created_at TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
        [
            ("Alice", "alice@example.com", 30),
            ("Bob", "bob@example.com", 25),
            ("Charlie", "charlie@example.com", 35),
        ],
    )
    conn.executemany(
        "INSERT INTO orders (user_id, amount, created_at) VALUES (?, ?, ?)",
        [
            (1, 99.99, "2024-01-01"),
            (1, 49.50, "2024-01-15"),
            (2, 200.00, "2024-02-01"),
        ],
    )
    conn.commit()
    conn.close()

    # Patch the server's DATABASE_PATH to point at our temp DB
    original_path = server.DATABASE_PATH
    server.DATABASE_PATH = db_path

    yield db_path

    server.DATABASE_PATH = original_path
    os.unlink(db_path)


@pytest.fixture(autouse=True)
def reset_query_history():
    """Clear in-memory query history before each test."""
    server._query_history.clear()
    yield
    server._query_history.clear()


# ---------------------------------------------------------------------------
# list_tables tests
# ---------------------------------------------------------------------------


async def test_list_tables_success(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("list_tables", {})
        data = result.data
        assert "tables" in data
        assert "count" in data
        assert "users" in data["tables"]
        assert "orders" in data["tables"]
        assert data["count"] == 2


async def test_list_tables_returns_correct_count(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("list_tables", {})
        data = result.data
        assert data["count"] == len(data["tables"])


async def test_list_tables_database_not_found():
    original = server.DATABASE_PATH
    server.DATABASE_PATH = "/nonexistent/path/to/database.db"
    try:
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("list_tables", {})
    finally:
        server.DATABASE_PATH = original


# ---------------------------------------------------------------------------
# describe_table tests
# ---------------------------------------------------------------------------


async def test_describe_table_success(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("describe_table", {"table_name": "users"})
        data = result.data
        assert data["table_name"] == "users"
        assert "columns" in data
        assert "column_count" in data
        assert data["column_count"] == 4
        col_names = [c["name"] for c in data["columns"]]
        assert "id" in col_names
        assert "name" in col_names
        assert "email" in col_names
        assert "age" in col_names


async def test_describe_table_column_details(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("describe_table", {"table_name": "users"})
        data = result.data
        id_col = next(c for c in data["columns"] if c["name"] == "id")
        assert id_col["primary_key"] is True
        name_col = next(c for c in data["columns"] if c["name"] == "name")
        assert name_col["not_null"] is True


async def test_describe_table_with_foreign_keys(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("describe_table", {"table_name": "orders"})
        data = result.data
        assert "foreign_keys" in data
        assert len(data["foreign_keys"]) >= 1
        fk = data["foreign_keys"][0]
        assert fk["to_table"] == "users"
        assert fk["from_column"] == "user_id"


async def test_describe_table_not_found(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("describe_table", {"table_name": "nonexistent_table"})


async def test_describe_table_invalid_table_name(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("describe_table", {"table_name": "drop; --"})


async def test_describe_table_empty_name(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("describe_table", {"table_name": ""})


async def test_describe_table_database_not_found():
    original = server.DATABASE_PATH
    server.DATABASE_PATH = "/nonexistent/path/to/database.db"
    try:
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("describe_table", {"table_name": "users"})
    finally:
        server.DATABASE_PATH = original


# ---------------------------------------------------------------------------
# run_select_query tests
# ---------------------------------------------------------------------------


async def test_run_select_query_success(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("run_select_query", {"query": "SELECT * FROM users"})
        data = result.data
        assert "columns" in data
        assert "rows" in data
        assert "row_count" in data
        assert data["row_count"] == 3
        assert "name" in data["columns"]


async def test_run_select_query_with_row_limit(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool(
            "run_select_query", {"query": "SELECT * FROM users", "row_limit": 2}
        )
        data = result.data
        assert data["row_count"] == 2
        assert data["truncated"] is True
        assert data["row_limit_applied"] == 2


async def test_run_select_query_not_truncated(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool(
            "run_select_query", {"query": "SELECT * FROM users", "row_limit": 100}
        )
        data = result.data
        assert data["truncated"] is False


async def test_run_select_query_records_history(tmp_db):
    async with Client(mcp) as client:
        await client.call_tool("run_select_query", {"query": "SELECT * FROM users"})
        assert len(server._query_history) == 1
        assert "users" in server._query_history[0]["query"]
        assert server._query_history[0]["row_count"] == 3


async def test_run_select_query_with_where_clause(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool(
            "run_select_query",
            {"query": "SELECT * FROM users WHERE age > 28"},
        )
        data = result.data
        assert data["row_count"] == 2


async def test_run_select_query_mutating_insert_rejected(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="SELECT"):
            await client.call_tool(
                "run_select_query",
                {"query": "INSERT INTO users (name) VALUES ('Eve')"},
            )


async def test_run_select_query_mutating_update_rejected(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "run_select_query",
                {"query": "UPDATE users SET name='Eve' WHERE id=1"},
            )


async def test_run_select_query_mutating_delete_rejected(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "run_select_query",
                {"query": "DELETE FROM users WHERE id=1"},
            )


async def test_run_select_query_mutating_drop_rejected(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "run_select_query",
                {"query": "DROP TABLE users"},
            )


async def test_run_select_query_syntax_error(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "run_select_query",
                {"query": "SELECT FROM WHERE"},
            )


async def test_run_select_query_nonexistent_table(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "run_select_query",
                {"query": "SELECT * FROM nonexistent_table"},
            )


async def test_run_select_query_nonexistent_column(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "run_select_query",
                {"query": "SELECT nonexistent_column FROM users"},
            )


async def test_run_select_query_row_limit_exceeds_maximum(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="maximum"):
            await client.call_tool(
                "run_select_query",
                {"query": "SELECT * FROM users", "row_limit": 99999},
            )


async def test_run_select_query_row_limit_zero_rejected(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "run_select_query",
                {"query": "SELECT * FROM users", "row_limit": 0},
            )


async def test_run_select_query_row_limit_negative_rejected(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "run_select_query",
                {"query": "SELECT * FROM users", "row_limit": -5},
            )


async def test_run_select_query_database_not_found():
    original = server.DATABASE_PATH
    server.DATABASE_PATH = "/nonexistent/path/to/database.db"
    try:
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("run_select_query", {"query": "SELECT * FROM users"})
    finally:
        server.DATABASE_PATH = original


# ---------------------------------------------------------------------------
# get_query_history tests
# ---------------------------------------------------------------------------


async def test_get_query_history_empty(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("get_query_history", {})
        data = result.data
        assert data["entries"] == []
        assert data["count"] == 0
        assert data["total_session_queries"] == 0


async def test_get_query_history_after_queries(tmp_db):
    async with Client(mcp) as client:
        await client.call_tool("run_select_query", {"query": "SELECT * FROM users"})
        await client.call_tool("run_select_query", {"query": "SELECT * FROM orders"})

        result = await client.call_tool("get_query_history", {})
        data = result.data
        assert data["count"] == 2
        assert data["total_session_queries"] == 2
        # Most recent first
        assert "orders" in data["entries"][0]["query"]
        assert "users" in data["entries"][1]["query"]


async def test_get_query_history_with_limit(tmp_db):
    async with Client(mcp) as client:
        await client.call_tool("run_select_query", {"query": "SELECT * FROM users"})
        await client.call_tool("run_select_query", {"query": "SELECT * FROM orders"})
        await client.call_tool("run_select_query", {"query": "SELECT id FROM users"})

        result = await client.call_tool("get_query_history", {"limit": 2})
        data = result.data
        assert data["count"] == 2
        assert data["total_session_queries"] == 3


async def test_get_query_history_with_filter_keyword(tmp_db):
    async with Client(mcp) as client:
        await client.call_tool("run_select_query", {"query": "SELECT * FROM users"})
        await client.call_tool("run_select_query", {"query": "SELECT * FROM orders"})

        result = await client.call_tool("get_query_history", {"filter_keyword": "orders"})
        data = result.data
        assert data["count"] == 1
        assert "orders" in data["entries"][0]["query"]


async def test_get_query_history_filter_no_match(tmp_db):
    async with Client(mcp) as client:
        await client.call_tool("run_select_query", {"query": "SELECT * FROM users"})

        result = await client.call_tool(
            "get_query_history", {"filter_keyword": "nonexistent_keyword_xyz"}
        )
        data = result.data
        assert data["count"] == 0
        assert data["total_session_queries"] == 1


async def test_get_query_history_entry_fields(tmp_db):
    async with Client(mcp) as client:
        await client.call_tool("run_select_query", {"query": "SELECT * FROM users"})

        result = await client.call_tool("get_query_history", {})
        data = result.data
        entry = data["entries"][0]
        assert "query" in entry
        assert "row_count" in entry
        assert "executed_at" in entry
        assert entry["row_count"] == 3


async def test_get_query_history_limit_zero_rejected(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="positive"):
            await client.call_tool("get_query_history", {"limit": 0})


async def test_get_query_history_limit_negative_rejected(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("get_query_history", {"limit": -1})


# ---------------------------------------------------------------------------
# get_table_sample tests
# ---------------------------------------------------------------------------


async def test_get_table_sample_success(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("get_table_sample", {"table_name": "users"})
        data = result.data
        assert data["table_name"] == "users"
        assert "columns" in data
        assert "rows" in data
        assert "row_count" in data
        assert data["row_count"] <= 10  # default sample_size
        assert data["sample_size_requested"] == 10


async def test_get_table_sample_custom_size(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_table_sample", {"table_name": "users", "sample_size": 2}
        )
        data = result.data
        assert data["row_count"] == 2
        assert data["sample_size_requested"] == 2


async def test_get_table_sample_returns_correct_columns(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("get_table_sample", {"table_name": "users"})
        data = result.data
        assert "id" in data["columns"]
        assert "name" in data["columns"]
        assert "email" in data["columns"]
        assert "age" in data["columns"]


async def test_get_table_sample_table_not_found(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("get_table_sample", {"table_name": "nonexistent_table"})


async def test_get_table_sample_size_zero_rejected(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="positive"):
            await client.call_tool("get_table_sample", {"table_name": "users", "sample_size": 0})


async def test_get_table_sample_size_negative_rejected(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("get_table_sample", {"table_name": "users", "sample_size": -3})


async def test_get_table_sample_invalid_table_name(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("get_table_sample", {"table_name": "'; DROP TABLE users; --"})


async def test_get_table_sample_database_not_found():
    original = server.DATABASE_PATH
    server.DATABASE_PATH = "/nonexistent/path/to/database.db"
    try:
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("get_table_sample", {"table_name": "users"})
    finally:
        server.DATABASE_PATH = original


# ---------------------------------------------------------------------------
# get_table_row_count tests
# ---------------------------------------------------------------------------


async def test_get_table_row_count_success(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("get_table_row_count", {"table_name": "users"})
        data = result.data
        assert data["table_name"] == "users"
        assert data["row_count"] == 3


async def test_get_table_row_count_orders(tmp_db):
    async with Client(mcp) as client:
        result = await client.call_tool("get_table_row_count", {"table_name": "orders"})
        data = result.data
        assert data["table_name"] == "orders"
        assert data["row_count"] == 3


async def test_get_table_row_count_table_not_found(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="not found"):
            await client.call_tool("get_table_row_count", {"table_name": "nonexistent_table"})


async def test_get_table_row_count_invalid_table_name(tmp_db):
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("get_table_row_count", {"table_name": "123invalid"})


async def test_get_table_row_count_database_not_found():
    original = server.DATABASE_PATH
    server.DATABASE_PATH = "/nonexistent/path/to/database.db"
    try:
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("get_table_row_count", {"table_name": "users"})
    finally:
        server.DATABASE_PATH = original


# ---------------------------------------------------------------------------
# Resource tests
# ---------------------------------------------------------------------------


async def test_database_overview_resource(tmp_db):
    async with Client(mcp) as client:
        result = await client.read_resource("sqlite://overview")
        # result is a list of resource contents; parse the first one
        import json

        content = result[0]
        # content.text contains the JSON-serialized dict
        data = json.loads(content.text) if hasattr(content, "text") else content
        assert "tables" in data
        assert "table_count" in data
        assert data["table_count"] == 2


# ---------------------------------------------------------------------------
# Prompt tests
# ---------------------------------------------------------------------------


async def test_explain_query_results_prompt(tmp_db):
    async with Client(mcp) as client:
        result = await client.get_prompt(
            "explain_query_results",
            {
                "query": "SELECT * FROM users",
                "results_summary": "3 rows returned with columns id, name, email, age",
            },
        )
        # result.messages is a list of prompt messages
        assert result.messages
        text = result.messages[0].content.text
        assert "SELECT * FROM users" in text
        assert "3 rows returned" in text
        assert "non-technical" in text.lower() or "data analyst" in text.lower()
