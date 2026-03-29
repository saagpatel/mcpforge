# Database Query MCP Server

Read-only SQLite database access for Claude Desktop and other MCP clients.

## Tools

- `query_database(sql)` — Execute a SELECT query (non-SELECT queries are rejected)
- `list_tables()` — List all tables in the database
- `describe_table(table_name)` — Get column info for a table

## Setup

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_PATH` | No (default: `database.db`) | Path to the SQLite database file |

Only SELECT queries are permitted. Table names are validated against `^[a-zA-Z_][a-zA-Z0-9_]*$`.

## Run

```bash
DATABASE_PATH=/path/to/db.sqlite uv sync && uv run server.py
```

## Test

```bash
uv run pytest -v
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "database-query-server": {
      "command": "uv",
      "args": ["run", "server.py"],
      "env": {"DATABASE_PATH": "/path/to/your/database.db"}
    }
  }
}
```
