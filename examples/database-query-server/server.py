"""SQLite database query MCP server (read-only)."""

import os
import re

import aiosqlite
from fastmcp import FastMCP
from fastmcp.exceptions import McpError

mcp = FastMCP("Database Query Server")

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _require_select(sql: str) -> None:
    if not sql.strip().upper().startswith("SELECT"):
        raise McpError("Only SELECT queries are allowed")


def _validate_identifier(name: str) -> None:
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise McpError(f"Invalid identifier: {name!r}")


@mcp.tool
async def query_database(sql: str) -> dict:
    """Execute a SELECT query and return results."""
    _require_select(sql)
    db_path = os.environ.get("DATABASE_PATH", "database.db")
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(sql) as cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
    result_rows = [dict(zip(columns, row)) for row in rows]
    return {"rows": result_rows, "count": len(result_rows)}


@mcp.tool
async def list_tables() -> dict:
    """List all tables in the database."""
    db_path = os.environ.get("DATABASE_PATH", "database.db")
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cursor:
            rows = await cursor.fetchall()
    return {"tables": [row[0] for row in rows]}


@mcp.tool
async def describe_table(table_name: str) -> dict:
    """Get column information for a table."""
    _validate_identifier(table_name)
    db_path = os.environ.get("DATABASE_PATH", "database.db")
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute(f"PRAGMA table_info({table_name})") as cursor:
            rows = await cursor.fetchall()
    if not rows:
        raise McpError(f"Table {table_name!r} not found")
    columns = [
        {"name": row[1], "type": row[2], "notnull": bool(row[3]), "pk": bool(row[5])}
        for row in rows
    ]
    return {"table": table_name, "columns": columns}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
