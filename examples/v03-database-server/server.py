"""MCP server for read-only querying and exploration of a local SQLite analytics database."""

import os
import re
from datetime import UTC, datetime

import aiosqlite
import sqlparse
from fastmcp import FastMCP
from sqlparse.sql import Statement
from sqlparse.tokens import DDL, DML, Keyword

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_PATH = os.environ.get("DATABASE_PATH") or os.environ.get("DATABASE_URL")
if not DATABASE_PATH:
    raise RuntimeError(
        "Either DATABASE_PATH or DATABASE_URL environment variable must be set "
        "to the path of the SQLite database file."
    )

# Strip sqlite:/// prefix if provided as a URL
if DATABASE_PATH.startswith("sqlite:///"):
    DATABASE_PATH = DATABASE_PATH[len("sqlite:///") :]

MAX_ROW_LIMIT = 5000  # Hard cap on rows returned by run_select_query

# ---------------------------------------------------------------------------
# In-memory query history store
# ---------------------------------------------------------------------------

_query_history: list[dict] = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MUTATING_STATEMENT_TYPES = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "REPLACE",
    "TRUNCATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    "ANALYZE",
}

_VALID_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _is_safe_select(query: str) -> bool:
    """Return True only if the query is a single, non-mutating SELECT statement."""
    stripped = query.strip().rstrip(";")
    parsed = sqlparse.parse(stripped)
    if not parsed or len(parsed) != 1:
        return False
    stmt: Statement = parsed[0]
    stmt_type = stmt.get_type()
    if stmt_type != "SELECT":
        return False
    # Double-check: walk tokens for any DDL or mutating DML keywords
    for token in stmt.flatten():
        if token.ttype in (DDL,):
            return False
        if token.ttype in (DML,) and token.normalized.upper() != "SELECT":
            return False
        if token.ttype is Keyword and token.normalized.upper() in _MUTATING_STATEMENT_TYPES:
            return False
    return True


def _validate_identifier(name: str, label: str = "table_name") -> None:
    """Raise ValueError if name is not a safe SQL identifier."""
    if not name or not _VALID_IDENTIFIER_RE.match(name):
        raise ValueError(
            f"{label} {name!r} is not a valid SQL identifier. "
            "Use only letters, digits, and underscores, starting with a letter or underscore."
        )


async def _get_connection() -> aiosqlite.Connection:
    """Open and return an aiosqlite connection in read-only mode."""
    try:
        conn = await aiosqlite.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)
        conn.row_factory = aiosqlite.Row
        return conn
    except Exception as exc:
        raise RuntimeError(
            f"Failed to connect to SQLite database at {DATABASE_PATH!r}: {exc}"
        ) from exc


async def _table_exists(conn: aiosqlite.Connection, table_name: str) -> bool:
    """Return True if the table exists in the database."""
    async with conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ) as cursor:
        row = await cursor.fetchone()
        return row is not None


def _record_history(query: str, row_count: int) -> None:
    """Append a query execution record to the in-memory history."""
    _query_history.append(
        {
            "query": query,
            "row_count": row_count,
            "executed_at": datetime.now(UTC).isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("SQLite Analytics Server")


@mcp.tool
async def list_tables() -> dict:
    """List all tables available in the SQLite database."""
    try:
        conn = await _get_connection()
    except RuntimeError:
        raise

    try:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cursor:
            rows = await cursor.fetchall()
        tables = [row["name"] for row in rows]
        return {"tables": tables, "count": len(tables)}
    except Exception as exc:
        raise RuntimeError(f"Failed to list tables: {exc}") from exc
    finally:
        await conn.close()


@mcp.tool
async def describe_table(table_name: str) -> dict:
    """Return table schema details: columns, types, nullability, and defaults."""
    _validate_identifier(table_name, "table_name")

    try:
        conn = await _get_connection()
    except RuntimeError:
        raise

    try:
        if not await _table_exists(conn, table_name):
            raise ValueError(f"Table {table_name!r} not found in the database.")

        async with conn.execute(f"PRAGMA table_info({table_name})") as cursor:
            rows = await cursor.fetchall()

        columns = [
            {
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "not_null": bool(row["notnull"]),
                "default_value": row["dflt_value"],
                "primary_key": bool(row["pk"]),
            }
            for row in rows
        ]

        # Also fetch foreign keys
        async with conn.execute(f"PRAGMA foreign_key_list({table_name})") as cursor:
            fk_rows = await cursor.fetchall()

        foreign_keys = [
            {
                "id": fk["id"],
                "from_column": fk["from"],
                "to_table": fk["table"],
                "to_column": fk["to"],
            }
            for fk in fk_rows
        ]

        return {
            "table_name": table_name,
            "columns": columns,
            "column_count": len(columns),
            "foreign_keys": foreign_keys,
        }
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to describe table {table_name!r}: {exc}") from exc
    finally:
        await conn.close()


@mcp.tool
async def run_select_query(query: str, row_limit: int = 500) -> dict:
    """Execute a safe, read-only SELECT query against the database.

    Mutating SQL statements (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, etc.)
    are rejected. Results are capped at a configurable row limit (max 5000).
    """
    if not query or not query.strip():
        raise ValueError("query must not be empty.")

    if row_limit <= 0:
        raise ValueError("row_limit must be a positive integer.")

    if row_limit > MAX_ROW_LIMIT:
        raise ValueError(
            f"row_limit {row_limit} exceeds the maximum allowed value of {MAX_ROW_LIMIT}."
        )

    if not _is_safe_select(query):
        raise ValueError(
            "Only single SELECT statements are permitted. "
            "Mutating or multi-statement SQL is rejected."
        )

    try:
        conn = await _get_connection()
    except RuntimeError:
        raise

    try:
        # Apply row limit by wrapping the query
        limited_query = f"SELECT * FROM ({query.strip().rstrip(';')}) LIMIT ?"

        try:
            async with conn.execute(limited_query, (row_limit,)) as cursor:
                rows = await cursor.fetchall()
                column_names = [description[0] for description in cursor.description or []]
        except aiosqlite.OperationalError as exc:
            raise RuntimeError(f"SQL execution error: {exc}") from exc

        result_rows = [dict(zip(column_names, tuple(row))) for row in rows]
        row_count = len(result_rows)

        _record_history(query.strip(), row_count)

        return {
            "columns": column_names,
            "rows": result_rows,
            "row_count": row_count,
            "row_limit_applied": row_limit,
            "truncated": row_count == row_limit,
        }
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise RuntimeError(f"Unexpected error executing query: {exc}") from exc
    finally:
        await conn.close()


@mcp.tool
async def get_query_history(limit: int = 20, filter_keyword: str | None = None) -> dict:
    """Retrieve the history of SELECT queries executed in the current server session.

    Returns entries most recent first, optionally filtered by a keyword in the query text.
    """
    if limit <= 0:
        raise ValueError("limit must be a positive integer.")

    history = list(reversed(_query_history))

    if filter_keyword is not None and filter_keyword.strip():
        kw = filter_keyword.strip().lower()
        history = [entry for entry in history if kw in entry["query"].lower()]

    history = history[:limit]

    return {
        "entries": history,
        "count": len(history),
        "total_session_queries": len(_query_history),
    }


@mcp.tool
async def get_table_sample(table_name: str, sample_size: int = 10) -> dict:
    """Return a small sample of rows from a table to help understand its contents."""
    _validate_identifier(table_name, "table_name")

    if sample_size <= 0:
        raise ValueError("sample_size must be a positive integer.")

    if sample_size > MAX_ROW_LIMIT:
        raise ValueError(
            f"sample_size {sample_size} exceeds the maximum allowed value of {MAX_ROW_LIMIT}."
        )

    try:
        conn = await _get_connection()
    except RuntimeError:
        raise

    try:
        if not await _table_exists(conn, table_name):
            raise ValueError(f"Table {table_name!r} not found in the database.")

        async with conn.execute(f"SELECT * FROM {table_name} LIMIT ?", (sample_size,)) as cursor:
            rows = await cursor.fetchall()
            column_names = [description[0] for description in cursor.description or []]

        result_rows = [dict(zip(column_names, tuple(row))) for row in rows]

        return {
            "table_name": table_name,
            "columns": column_names,
            "rows": result_rows,
            "row_count": len(result_rows),
            "sample_size_requested": sample_size,
        }
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to sample table {table_name!r}: {exc}") from exc
    finally:
        await conn.close()


@mcp.tool
async def get_table_row_count(table_name: str) -> dict:
    """Return the total number of rows in a specified table."""
    _validate_identifier(table_name, "table_name")

    try:
        conn = await _get_connection()
    except RuntimeError:
        raise

    try:
        if not await _table_exists(conn, table_name):
            raise ValueError(f"Table {table_name!r} not found in the database.")

        async with conn.execute(f"SELECT COUNT(*) AS row_count FROM {table_name}") as cursor:
            row = await cursor.fetchone()

        count = row["row_count"] if row else 0

        return {"table_name": table_name, "row_count": count}
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to count rows in table {table_name!r}: {exc}") from exc
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("sqlite://overview")
async def database_overview() -> dict:
    """Return table names, row counts, and column summaries for the database."""
    try:
        conn = await _get_connection()
    except RuntimeError:
        return {"error": "Could not connect to the database.", "tables": []}

    try:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cursor:
            table_rows = await cursor.fetchall()

        tables_info = []
        for table_row in table_rows:
            tname = table_row["name"]
            try:
                async with conn.execute(f"SELECT COUNT(*) AS row_count FROM {tname}") as cur:
                    count_row = await cur.fetchone()
                row_count = count_row["row_count"] if count_row else 0

                async with conn.execute(f"PRAGMA table_info({tname})") as cur:
                    col_rows = await cur.fetchall()
                columns = [
                    {"name": c["name"], "type": c["type"], "primary_key": bool(c["pk"])}
                    for c in col_rows
                ]

                tables_info.append(
                    {
                        "table_name": tname,
                        "row_count": row_count,
                        "column_count": len(columns),
                        "columns": columns,
                    }
                )
            except Exception:
                tables_info.append({"table_name": tname, "error": "Could not retrieve details."})

        return {
            "database_path": DATABASE_PATH,
            "table_count": len(tables_info),
            "tables": tables_info,
            "generated_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        return {"error": str(exc), "tables": []}
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt
def explain_query_results(query: str, results_summary: str) -> str:
    """Generate a plain-English explanation of SELECT query results for a non-technical audience."""
    template = (
        "You are a data analyst. A SELECT query was run against a SQLite analytics database. "
        "Explain the results in plain English, highlight any notable trends or outliers, "
        "and summarize the key takeaways for a non-technical audience. "
        f"Query: {query}. Results: {results_summary}."
    )
    return template


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
