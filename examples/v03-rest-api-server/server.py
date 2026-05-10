"""MCP server for managing customer support tickets, notes, service status, and triage workflows."""

import os

import httpx
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Environment variable validation
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("SUPPORT_API_BASE_URL")
if not BASE_URL:
    raise RuntimeError("Required environment variable SUPPORT_API_BASE_URL is not set.")

API_TOKEN = os.environ.get("SUPPORT_API_TOKEN")
if not API_TOKEN:
    raise RuntimeError("Required environment variable SUPPORT_API_TOKEN is not set.")

_timeout_raw = os.environ.get("SUPPORT_API_TIMEOUT_SECONDS", "30")
try:
    TIMEOUT_SECONDS = float(_timeout_raw)
except ValueError:
    raise RuntimeError(f"SUPPORT_API_TIMEOUT_SECONDS must be a number, got: {_timeout_raw!r}")

# ---------------------------------------------------------------------------
# Shared HTTP helpers
# ---------------------------------------------------------------------------


def _auth_headers() -> dict[str, str]:
    """Return authorization headers using the configured API token."""
    return {"Authorization": f"Bearer {API_TOKEN}", "Accept": "application/json"}


def _client() -> httpx.AsyncClient:
    """Create a pre-configured async HTTP client."""
    return httpx.AsyncClient(
        base_url=BASE_URL.rstrip("/"),
        headers=_auth_headers(),
        timeout=TIMEOUT_SECONDS,
    )


async def _handle_response(response: httpx.Response) -> dict:
    """Raise a descriptive RuntimeError for non-2xx responses, otherwise return JSON."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        if status == 401:
            raise RuntimeError("Authentication failure: check SUPPORT_API_TOKEN.") from exc
        if status == 404:
            raise ValueError(f"Resource not found (HTTP 404): {detail}") from exc
        raise RuntimeError(f"Upstream API error (HTTP {status}): {detail}") from exc
    return response.json()


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP("Customer Support API")

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

VALID_STATUSES = {"open", "closed", "pending"}


@mcp.tool
async def list_tickets(
    status: str | None = None,
    assignee: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """List all support tickets, optionally filtered by status or assignee.

    Returns a paginated dict containing ticket records and pagination metadata.
    Raises ValueError for invalid status values and RuntimeError for API errors.
    """
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status {status!r}. Must be one of: {sorted(VALID_STATUSES)}")
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    params: dict[str, str | int] = {"page": page, "page_size": page_size}
    if status is not None:
        params["status"] = status
    if assignee is not None:
        params["assignee"] = assignee

    try:
        async with _client() as client:
            response = await client.get("/tickets", params=params)
    except httpx.TimeoutException as exc:
        raise RuntimeError("API request timed out while listing tickets.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Network error while listing tickets: {exc}") from exc

    return await _handle_response(response)


@mcp.tool
async def get_ticket(ticket_id: str) -> dict:
    """Fetch a single support ticket by its unique ID, including all metadata and current status.

    Raises ValueError if the ticket is not found or the ID format is invalid.
    Raises RuntimeError for network or upstream API errors.
    """
    if not ticket_id or not ticket_id.strip():
        raise ValueError("ticket_id must not be empty.")

    try:
        async with _client() as client:
            response = await client.get(f"/tickets/{ticket_id.strip()}")
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"API request timed out while fetching ticket {ticket_id!r}.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Network error while fetching ticket {ticket_id!r}: {exc}") from exc

    return await _handle_response(response)


@mcp.tool
async def create_note(
    ticket_id: str,
    body: str,
    author: str | None = None,
    internal: bool = True,
) -> dict:
    """Add a note to an existing support ticket by ticket ID.

    The note body must be non-empty. If author is None, the API token owner is used.
    Set internal=False to make the note visible to the customer.
    Raises ValueError for missing/invalid inputs and RuntimeError for API errors.
    """
    if not ticket_id or not ticket_id.strip():
        raise ValueError("ticket_id must not be empty.")
    if not body or not body.strip():
        raise ValueError("body must not be empty.")

    payload: dict[str, str | bool] = {
        "body": body.strip(),
        "internal": internal,
    }
    if author is not None:
        payload["author"] = author

    try:
        async with _client() as client:
            response = await client.post(
                f"/tickets/{ticket_id.strip()}/notes",
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            f"API request timed out while creating note on ticket {ticket_id!r}."
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Network error while creating note on ticket {ticket_id!r}: {exc}"
        ) from exc

    return await _handle_response(response)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("support://service-status")
async def service_status() -> dict:
    """Read the current service status and any active incidents from the support API."""
    try:
        async with _client() as client:
            response = await client.get("/service-status")
    except httpx.TimeoutException as exc:
        raise RuntimeError("API request timed out while fetching service status.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Network error while fetching service status: {exc}") from exc

    return await _handle_response(response)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt
def triage_ticket(ticket_id: str) -> str:
    """Generate a structured triage analysis for a support ticket."""
    return (
        f"You are a senior support engineer. Review the support ticket identified by "
        f"ticket_id={ticket_id!r} and produce a triage report covering: "
        "(1) a one-sentence summary of the customer issue, "
        "(2) suggested priority level (critical, high, medium, or low) with justification, "
        "(3) recommended team or specialist to handle it, and "
        "(4) any immediate next steps the first responder should take. "
        "Be concise and actionable."
    )


@mcp.prompt
def draft_customer_reply(ticket_id: str, resolution_summary: str) -> str:
    """Draft an empathetic customer reply from ticket context and resolution."""
    return (
        f"You are a customer support specialist. Using the ticket identified by "
        f"ticket_id={ticket_id!r} and the resolution described as: {resolution_summary!r}, "
        "draft a clear, professional, and empathetic reply to the customer. "
        "The reply should acknowledge their issue, explain what was done or what will happen next, "
        "set realistic expectations, and close with an offer for further assistance. "
        "Avoid technical jargon unless the customer used it first."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
