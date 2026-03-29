"""Template hints for guiding server code generation style."""

TEMPLATE_HINTS: dict[str, str] = {
    "rest-api": (
        "This server wraps a REST API. Use async httpx.AsyncClient for all HTTP calls. "
        "Read API keys from environment variables. Handle HTTP errors (4xx, 5xx) by raising "
        "McpError with descriptive messages. Include the base URL as a module-level constant "
        "read from an env var."
    ),
    "database": (
        "This server queries a database. Use aiosqlite for SQLite or asyncpg for PostgreSQL. "
        "Read the connection string from an environment variable. Parameterize ALL queries — "
        "never interpolate user input directly into SQL. Return results as list[dict] with "
        "column names as keys."
    ),
    "filesystem": (
        "This server reads/writes the local filesystem. Read the root directory from an "
        "environment variable (FILES_ROOT or similar). Always resolve paths relative to the "
        "root and verify the resolved path starts with the root (prevents path traversal). "
        "Use pathlib.Path throughout. Return file contents as strings."
    ),
}
