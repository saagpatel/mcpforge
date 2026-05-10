"""MCP server for hosted auth ticket operations (get ticket, create ticket note)."""

import asyncio
import os

import httpx
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("BASE_URL", "https://api.example.test").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))


def _get_downstream_api_key() -> str:
    """Return the downstream API key or raise a clear RuntimeError."""
    key = os.environ.get("HOSTED_AUTH_API_KEY")
    if not key:
        raise RuntimeError(
            "HOSTED_AUTH_API_KEY environment variable is not set. "
            "Configure it with the API key for the upstream tickets service."
        )
    return key


def _mcpforge_api_key_placeholder() -> str | None:
    """
    Read the MCP server's own API key used to authenticate *inbound* requests.

    For HTTP deployments, enforce this key in your reverse-proxy or load-balancer
    by requiring the header  Authorization: Bearer <MCPFORGE_SERVER_API_KEY>.
    FastMCP itself does not automatically reject unauthenticated callers; add
    middleware or a gateway rule to do so.

    Returns None when the variable is absent (unauthenticated / open access).
    """
    return os.environ.get("MCPFORGE_SERVER_API_KEY")


# ---------------------------------------------------------------------------
# Retry helper (for retry_safe operations)
# ---------------------------------------------------------------------------

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds


async def _request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    json: dict | None = None,
) -> dict:
    """Perform an HTTP request, retrying on 429 / 5xx with exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                )
        except httpx.RequestError as exc:
            raise RuntimeError(f"HTTP request failed: {exc}") from exc

        if response.status_code not in _RETRY_STATUSES:
            break

        last_exc = RuntimeError(f"Upstream returned {response.status_code}: {response.text[:200]}")
        if attempt < _MAX_RETRIES - 1:
            await asyncio.sleep(_BACKOFF_BASE * (2**attempt))
    else:
        raise last_exc  # type: ignore[misc]

    if response.status_code >= 400:
        raise RuntimeError(f"Upstream returned {response.status_code}: {response.text[:200]}")

    return response.json()


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP("Hosted Auth Tickets API")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
async def get_ticket(
    ticket_id: str,
    include_history: bool | None = None,
) -> dict:
    """Get a ticket by its identifier, optionally including its status history."""
    if not ticket_id.strip():
        raise ValueError("ticket_id must not be empty")

    api_key = _get_downstream_api_key()
    url = f"{BASE_URL}/tickets/{ticket_id}"

    query_params: dict = {}
    if include_history is not None:
        query_params["include_history"] = include_history

    headers = {"X-API-Key": api_key}

    try:
        return await _request_with_retry(
            "GET",
            url,
            headers=headers,
            params=query_params or None,
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Unexpected error fetching ticket: {exc}") from exc


@mcp.tool
async def create_ticket_note(
    ticket_id: str,
    body: dict,
) -> dict:
    """Create a note on an existing ticket identified by ticket_id."""
    if not ticket_id.strip():
        raise ValueError("ticket_id must not be empty")
    if not body:
        raise ValueError("body must not be empty")

    api_key = _get_downstream_api_key()
    url = f"{BASE_URL}/tickets/{ticket_id}/notes"
    headers = {"X-API-Key": api_key}

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=body)
    except httpx.RequestError as exc:
        raise RuntimeError(f"HTTP request failed: {exc}") from exc

    if response.status_code >= 400:
        raise RuntimeError(f"Upstream returned {response.status_code}: {response.text[:200]}")

    return response.json()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Warn early if the inbound MCP server API key is not configured.
    _inbound_key = _mcpforge_api_key_placeholder()
    if not _inbound_key:
        import warnings

        warnings.warn(
            "MCPFORGE_SERVER_API_KEY is not set. The MCP server is running without "
            "inbound authentication. Set this variable and enforce it at your "
            "reverse-proxy or gateway layer.",
            stacklevel=1,
        )

    mcp.run(transport="streamable-http")
