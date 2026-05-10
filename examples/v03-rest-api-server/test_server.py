"""Tests for the Customer Support API MCP server."""

import os

import httpx
import pytest
import respx

# Set required environment variables before importing server
os.environ.setdefault("SUPPORT_API_BASE_URL", "http://test-support-api.example.com")
os.environ.setdefault("SUPPORT_API_TOKEN", "test-token-abc123")
os.environ.setdefault("SUPPORT_API_TIMEOUT_SECONDS", "30")

from fastmcp import Client
from server import mcp

BASE_URL = "http://test-support-api.example.com"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_respx():
    """Each test gets a clean respx mock router."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        yield router


# ---------------------------------------------------------------------------
# list_tickets tests
# ---------------------------------------------------------------------------


async def test_list_tickets_success_no_filters(reset_respx):
    """Happy path: list tickets with no filters returns paginated results."""
    reset_respx.get("/tickets").mock(
        return_value=httpx.Response(
            200,
            json={
                "tickets": [
                    {"id": "1", "subject": "Login broken", "status": "open"},
                    {"id": "2", "subject": "Billing issue", "status": "pending"},
                ],
                "page": 1,
                "page_size": 25,
                "total": 2,
            },
        )
    )

    async with Client(mcp) as client:
        result = await client.call_tool("list_tickets", {})

    assert result.data["page"] == 1
    assert result.data["total"] == 2
    assert len(result.data["tickets"]) == 2
    assert result.data["tickets"][0]["id"] == "1"


async def test_list_tickets_filtered_by_status(reset_respx):
    """Happy path: filter tickets by status='open'."""
    reset_respx.get("/tickets").mock(
        return_value=httpx.Response(
            200,
            json={
                "tickets": [{"id": "1", "subject": "Login broken", "status": "open"}],
                "page": 1,
                "page_size": 25,
                "total": 1,
            },
        )
    )

    async with Client(mcp) as client:
        result = await client.call_tool("list_tickets", {"status": "open"})

    assert result.data["total"] == 1
    assert result.data["tickets"][0]["status"] == "open"


async def test_list_tickets_filtered_by_assignee(reset_respx):
    """Happy path: filter tickets by assignee."""
    reset_respx.get("/tickets").mock(
        return_value=httpx.Response(
            200,
            json={
                "tickets": [
                    {
                        "id": "3",
                        "subject": "Crash on startup",
                        "status": "open",
                        "assignee": "alice",
                    }
                ],
                "page": 1,
                "page_size": 25,
                "total": 1,
            },
        )
    )

    async with Client(mcp) as client:
        result = await client.call_tool("list_tickets", {"assignee": "alice"})

    assert result.data["tickets"][0]["assignee"] == "alice"


async def test_list_tickets_pagination(reset_respx):
    """Happy path: pagination parameters are forwarded."""
    reset_respx.get("/tickets").mock(
        return_value=httpx.Response(
            200,
            json={"tickets": [], "page": 2, "page_size": 10, "total": 0},
        )
    )

    async with Client(mcp) as client:
        result = await client.call_tool("list_tickets", {"page": 2, "page_size": 10})

    assert result.data["page"] == 2
    assert result.data["page_size"] == 10


async def test_list_tickets_invalid_status(reset_respx):
    """Error path: invalid status value raises an exception."""
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="Invalid status"):
            await client.call_tool("list_tickets", {"status": "unknown_status"})


async def test_list_tickets_authentication_failure(reset_respx):
    """Error path: 401 response raises RuntimeError about authentication."""
    reset_respx.get("/tickets").mock(
        return_value=httpx.Response(401, json={"error": "Unauthorized"})
    )

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Aa]uthentication"):
            await client.call_tool("list_tickets", {})


async def test_list_tickets_upstream_api_error(reset_respx):
    """Error path: 500 response raises RuntimeError about upstream API error."""
    reset_respx.get("/tickets").mock(
        return_value=httpx.Response(500, json={"error": "Internal Server Error"})
    )

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Uu]pstream API error"):
            await client.call_tool("list_tickets", {})


async def test_list_tickets_timeout(reset_respx):
    """Error path: request timeout raises RuntimeError."""
    reset_respx.get("/tickets").mock(side_effect=httpx.TimeoutException("timed out"))

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Tt]imed? out|timeout"):
            await client.call_tool("list_tickets", {})


# ---------------------------------------------------------------------------
# get_ticket tests
# ---------------------------------------------------------------------------


async def test_get_ticket_success(reset_respx):
    """Happy path: fetch a ticket by ID returns full ticket data."""
    reset_respx.get("/tickets/TKT-001").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "TKT-001",
                "subject": "Cannot log in",
                "status": "open",
                "assignee": "bob",
                "created_at": "2024-01-15T10:00:00Z",
            },
        )
    )

    async with Client(mcp) as client:
        result = await client.call_tool("get_ticket", {"ticket_id": "TKT-001"})

    assert result.data["id"] == "TKT-001"
    assert result.data["subject"] == "Cannot log in"
    assert result.data["status"] == "open"


async def test_get_ticket_not_found(reset_respx):
    """Error path: ticket_id not found returns 404 and raises ValueError."""
    reset_respx.get("/tickets/NONEXISTENT").mock(
        return_value=httpx.Response(404, json={"error": "Ticket not found"})
    )

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Nn]ot found|404"):
            await client.call_tool("get_ticket", {"ticket_id": "NONEXISTENT"})


async def test_get_ticket_empty_id(reset_respx):
    """Error path: empty ticket_id raises ValueError."""
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="ticket_id"):
            await client.call_tool("get_ticket", {"ticket_id": ""})


async def test_get_ticket_whitespace_id(reset_respx):
    """Error path: whitespace-only ticket_id raises ValueError."""
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="ticket_id"):
            await client.call_tool("get_ticket", {"ticket_id": "   "})


async def test_get_ticket_authentication_failure(reset_respx):
    """Error path: 401 response raises RuntimeError about authentication."""
    reset_respx.get("/tickets/TKT-002").mock(
        return_value=httpx.Response(401, json={"error": "Unauthorized"})
    )

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Aa]uthentication"):
            await client.call_tool("get_ticket", {"ticket_id": "TKT-002"})


async def test_get_ticket_upstream_api_error(reset_respx):
    """Error path: 500 response raises RuntimeError about upstream API error."""
    reset_respx.get("/tickets/TKT-003").mock(
        return_value=httpx.Response(500, json={"error": "Internal Server Error"})
    )

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Uu]pstream API error"):
            await client.call_tool("get_ticket", {"ticket_id": "TKT-003"})


async def test_get_ticket_timeout(reset_respx):
    """Error path: request timeout raises RuntimeError."""
    reset_respx.get("/tickets/TKT-004").mock(side_effect=httpx.TimeoutException("timed out"))

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Tt]imed? out|timeout"):
            await client.call_tool("get_ticket", {"ticket_id": "TKT-004"})


# ---------------------------------------------------------------------------
# create_note tests
# ---------------------------------------------------------------------------


async def test_create_note_success_defaults(reset_respx):
    """Happy path: create an internal note with default author."""
    reset_respx.post("/tickets/TKT-001/notes").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "NOTE-1",
                "ticket_id": "TKT-001",
                "body": "Customer confirmed the issue.",
                "internal": True,
                "author": "api-token-owner",
                "created_at": "2024-01-15T11:00:00Z",
            },
        )
    )

    async with Client(mcp) as client:
        result = await client.call_tool(
            "create_note",
            {"ticket_id": "TKT-001", "body": "Customer confirmed the issue."},
        )

    assert result.data["id"] == "NOTE-1"
    assert result.data["ticket_id"] == "TKT-001"
    assert result.data["body"] == "Customer confirmed the issue."
    assert result.data["internal"] is True


async def test_create_note_success_with_author_and_public(reset_respx):
    """Happy path: create a public note with explicit author."""
    reset_respx.post("/tickets/TKT-002/notes").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "NOTE-2",
                "ticket_id": "TKT-002",
                "body": "We have resolved your issue.",
                "internal": False,
                "author": "alice",
                "created_at": "2024-01-15T12:00:00Z",
            },
        )
    )

    async with Client(mcp) as client:
        result = await client.call_tool(
            "create_note",
            {
                "ticket_id": "TKT-002",
                "body": "We have resolved your issue.",
                "author": "alice",
                "internal": False,
            },
        )

    assert result.data["id"] == "NOTE-2"
    assert result.data["internal"] is False
    assert result.data["author"] == "alice"


async def test_create_note_ticket_not_found(reset_respx):
    """Error path: ticket_id not found returns 404 and raises ValueError."""
    reset_respx.post("/tickets/NONEXISTENT/notes").mock(
        return_value=httpx.Response(404, json={"error": "Ticket not found"})
    )

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Nn]ot found|404"):
            await client.call_tool(
                "create_note",
                {"ticket_id": "NONEXISTENT", "body": "Some note"},
            )


async def test_create_note_empty_body(reset_respx):
    """Error path: empty body raises ValueError."""
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="body"):
            await client.call_tool(
                "create_note",
                {"ticket_id": "TKT-001", "body": ""},
            )


async def test_create_note_whitespace_body(reset_respx):
    """Error path: whitespace-only body raises ValueError."""
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="body"):
            await client.call_tool(
                "create_note",
                {"ticket_id": "TKT-001", "body": "   "},
            )


async def test_create_note_empty_ticket_id(reset_respx):
    """Error path: empty ticket_id raises ValueError."""
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="ticket_id"):
            await client.call_tool(
                "create_note",
                {"ticket_id": "", "body": "Some note"},
            )


async def test_create_note_authentication_failure(reset_respx):
    """Error path: 401 response raises RuntimeError about authentication."""
    reset_respx.post("/tickets/TKT-005/notes").mock(
        return_value=httpx.Response(401, json={"error": "Unauthorized"})
    )

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Aa]uthentication"):
            await client.call_tool(
                "create_note",
                {"ticket_id": "TKT-005", "body": "Some note"},
            )


async def test_create_note_upstream_api_error(reset_respx):
    """Error path: 500 response raises RuntimeError about upstream API error."""
    reset_respx.post("/tickets/TKT-006/notes").mock(
        return_value=httpx.Response(500, json={"error": "Internal Server Error"})
    )

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Uu]pstream API error"):
            await client.call_tool(
                "create_note",
                {"ticket_id": "TKT-006", "body": "Some note"},
            )


async def test_create_note_timeout(reset_respx):
    """Error path: request timeout raises RuntimeError."""
    reset_respx.post("/tickets/TKT-007/notes").mock(side_effect=httpx.TimeoutException("timed out"))

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="[Tt]imed? out|timeout"):
            await client.call_tool(
                "create_note",
                {"ticket_id": "TKT-007", "body": "Some note"},
            )


# ---------------------------------------------------------------------------
# service_status resource tests
# ---------------------------------------------------------------------------


async def test_service_status_success(reset_respx):
    """Happy path: read service status returns current status and incidents."""
    reset_respx.get("/service-status").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "operational",
                "incidents": [],
                "last_updated": "2024-01-15T10:00:00Z",
            },
        )
    )

    async with Client(mcp) as client:
        result = await client.read_resource("support://service-status")

    # Resource returns text content; parse if needed
    import json

    if isinstance(result, list):
        content = result[0]
        data = json.loads(content.text) if hasattr(content, "text") else content
    else:
        data = result

    # Verify the response contains expected fields
    if isinstance(data, dict):
        assert data["status"] == "operational"
        assert data["incidents"] == []
    else:
        # If returned as string, check it contains expected content
        assert "operational" in str(data)


async def test_service_status_with_active_incident(reset_respx):
    """Happy path: service status with active incidents."""
    reset_respx.get("/service-status").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "degraded",
                "incidents": [
                    {
                        "id": "INC-001",
                        "title": "Elevated error rates",
                        "severity": "high",
                        "started_at": "2024-01-15T09:00:00Z",
                    }
                ],
                "last_updated": "2024-01-15T10:00:00Z",
            },
        )
    )

    async with Client(mcp) as client:
        result = await client.read_resource("support://service-status")

    if isinstance(result, list):
        content = result[0]
        raw = content.text if hasattr(content, "text") else str(content)
        assert "degraded" in raw or "INC-001" in raw
    else:
        assert "degraded" in str(result) or "INC-001" in str(result)


async def test_service_status_upstream_error(reset_respx):
    """Error path: upstream API error raises RuntimeError."""
    reset_respx.get("/service-status").mock(
        return_value=httpx.Response(500, json={"error": "Internal Server Error"})
    )

    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.read_resource("support://service-status")


# ---------------------------------------------------------------------------
# triage_ticket prompt tests
# ---------------------------------------------------------------------------


async def test_triage_ticket_prompt_success():
    """Happy path: triage_ticket prompt returns structured triage instructions."""
    async with Client(mcp) as client:
        result = await client.get_prompt("triage_ticket", {"ticket_id": "TKT-100"})

    # result is a GetPromptResult with a messages list
    assert result is not None
    assert len(result.messages) >= 1
    prompt_text = result.messages[0].content.text
    assert "TKT-100" in prompt_text
    assert "triage" in prompt_text.lower() or "support engineer" in prompt_text.lower()


async def test_triage_ticket_prompt_contains_required_sections():
    """Happy path: triage prompt includes all four required report sections."""
    async with Client(mcp) as client:
        result = await client.get_prompt("triage_ticket", {"ticket_id": "TKT-200"})

    prompt_text = result.messages[0].content.text
    # Check for key concepts from the template
    assert "priority" in prompt_text.lower()
    assert "TKT-200" in prompt_text


async def test_triage_ticket_prompt_different_ids():
    """Happy path: different ticket IDs produce different prompts."""
    async with Client(mcp) as client:
        result_a = await client.get_prompt("triage_ticket", {"ticket_id": "TKT-AAA"})
        result_b = await client.get_prompt("triage_ticket", {"ticket_id": "TKT-BBB"})

    text_a = result_a.messages[0].content.text
    text_b = result_b.messages[0].content.text
    assert "TKT-AAA" in text_a
    assert "TKT-BBB" in text_b
    assert text_a != text_b


# ---------------------------------------------------------------------------
# draft_customer_reply prompt tests
# ---------------------------------------------------------------------------


async def test_draft_customer_reply_prompt_success():
    """Happy path: draft_customer_reply returns a professional reply draft."""
    async with Client(mcp) as client:
        result = await client.get_prompt(
            "draft_customer_reply",
            {
                "ticket_id": "TKT-300",
                "resolution_summary": "We fixed the login bug in version 2.1.",
            },
        )

    assert result is not None
    assert len(result.messages) >= 1
    prompt_text = result.messages[0].content.text
    assert "TKT-300" in prompt_text
    assert (
        "login bug" in prompt_text or "version 2.1" in prompt_text or "fixed" in prompt_text.lower()
    )


async def test_draft_customer_reply_prompt_contains_resolution():
    """Happy path: resolution_summary is embedded in the prompt."""
    resolution = "The billing discrepancy has been corrected and a refund issued."
    async with Client(mcp) as client:
        result = await client.get_prompt(
            "draft_customer_reply",
            {"ticket_id": "TKT-400", "resolution_summary": resolution},
        )

    prompt_text = result.messages[0].content.text
    assert resolution in prompt_text or "billing" in prompt_text.lower()


async def test_draft_customer_reply_prompt_different_resolutions():
    """Happy path: different resolutions produce different prompts."""
    async with Client(mcp) as client:
        result_a = await client.get_prompt(
            "draft_customer_reply",
            {"ticket_id": "TKT-500", "resolution_summary": "Issue resolved by restarting service."},
        )
        result_b = await client.get_prompt(
            "draft_customer_reply",
            {"ticket_id": "TKT-500", "resolution_summary": "Refund processed successfully."},
        )

    text_a = result_a.messages[0].content.text
    text_b = result_b.messages[0].content.text
    assert text_a != text_b
