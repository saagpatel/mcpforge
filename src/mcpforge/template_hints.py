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
    "graphql": (
        "This server queries a GraphQL API. Use the gql library with aiohttp transport: "
        "`from gql import gql, Client` and `from gql.transport.aiohttp import AIOHTTPTransport`. "
        "Read the GraphQL endpoint URL from an env var (GRAPHQL_URL). If authentication is needed, "
        "read the API token from an env var and pass it as an Authorization header. "
        "Check for 'errors' key in the response dict and raise McpError if present."
    ),
    "websocket": (
        "This server communicates over WebSocket. Use the websockets library: "
        "`import websockets`. Read the WebSocket URL from an env var (WS_URL). "
        "Implement reconnection with exponential backoff (max 5 retries, starting at 1s). "
        "Use asyncio.Queue for message buffering. Handle websockets.exceptions.ConnectionClosed "
        "by reconnecting. Each tool should establish, use, and close the connection."
    ),
    "auth-proxy": (
        "This server acts as an authenticated proxy. Read the API base URL and credentials from "
        "env vars. For JWT: use python-jose to validate tokens (`from jose import jwt`). "
        "For API key auth: attach the key as a Bearer token in Authorization header via httpx. "
        "Handle 401 responses by refreshing credentials and retrying once. "
        "Never log or return raw credentials in error messages."
    ),
    "queue-consumer": (
        "This server processes items from a Redis queue. Use redis.asyncio: "
        "`import redis.asyncio as redis`. Read REDIS_URL and QUEUE_NAME from env vars. "
        "Use BLPOP for blocking queue consumption with a timeout. "
        "On repeated failures (3+), move the item to a dead-letter queue (QUEUE_NAME + ':dead'). "
        "Each tool that dequeues items should handle empty queue gracefully (return empty list)."
    ),
}
