"""Tests for the Hosted Auth Tickets API MCP server."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import server
from fastmcp import Client
from server import mcp

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    """Ensure required environment variables are set for every test."""
    monkeypatch.setenv("HOSTED_AUTH_API_KEY", "test-api-key-123")
    monkeypatch.setenv("BASE_URL", "https://api.example.test")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "30")


def _make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    """Build a mock httpx.Response."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.text = str(json_data)
    return mock_resp


# ---------------------------------------------------------------------------
# get_ticket tests
# ---------------------------------------------------------------------------


async def test_get_ticket_success():
    """Happy path: get a ticket without history."""
    expected = {"id": "TKT-001", "title": "Login broken", "status": "open"}

    with patch.object(
        server, "_request_with_retry", new=AsyncMock(return_value=expected)
    ) as mock_retry:
        async with Client(mcp) as client:
            result = await client.call_tool("get_ticket", {"ticket_id": "TKT-001"})

        mock_retry.assert_awaited_once_with(
            "GET",
            "https://api.example.test/tickets/TKT-001",
            headers={"X-API-Key": "test-api-key-123"},
            params=None,
        )

    assert result.data == expected


async def test_get_ticket_with_include_history_true():
    """Happy path: get a ticket with include_history=True passes query param."""
    expected = {
        "id": "TKT-002",
        "title": "Slow load",
        "status": "closed",
        "history": [{"status": "open"}, {"status": "closed"}],
    }

    with patch.object(
        server, "_request_with_retry", new=AsyncMock(return_value=expected)
    ) as mock_retry:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_ticket", {"ticket_id": "TKT-002", "include_history": True}
            )

        mock_retry.assert_awaited_once_with(
            "GET",
            "https://api.example.test/tickets/TKT-002",
            headers={"X-API-Key": "test-api-key-123"},
            params={"include_history": True},
        )

    assert result.data == expected


async def test_get_ticket_with_include_history_false():
    """Happy path: get a ticket with include_history=False passes query param."""
    expected = {"id": "TKT-003", "title": "Crash on save", "status": "open"}

    with patch.object(
        server, "_request_with_retry", new=AsyncMock(return_value=expected)
    ) as mock_retry:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_ticket", {"ticket_id": "TKT-003", "include_history": False}
            )

        mock_retry.assert_awaited_once_with(
            "GET",
            "https://api.example.test/tickets/TKT-003",
            headers={"X-API-Key": "test-api-key-123"},
            params={"include_history": False},
        )

    assert result.data == expected


async def test_get_ticket_sends_api_key_header():
    """Verify the X-API-Key header is populated from the env var."""
    expected = {"id": "TKT-004", "status": "open"}

    captured_headers = {}

    async def capture(*args, headers=None, params=None, json=None):
        captured_headers.update(headers or {})
        return expected

    with patch.object(server, "_request_with_retry", new=capture):
        async with Client(mcp) as client:
            result = await client.call_tool("get_ticket", {"ticket_id": "TKT-004"})

    assert captured_headers["X-API-Key"] == "test-api-key-123"
    assert result.data == expected


async def test_get_ticket_empty_ticket_id_raises():
    """Error path: empty ticket_id should raise an exception."""
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("get_ticket", {"ticket_id": "   "})


async def test_get_ticket_missing_api_key_raises(monkeypatch):
    """Error path: missing HOSTED_AUTH_API_KEY should raise RuntimeError."""
    monkeypatch.delenv("HOSTED_AUTH_API_KEY", raising=False)

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="HOSTED_AUTH_API_KEY"):
            await client.call_tool("get_ticket", {"ticket_id": "TKT-001"})


async def test_get_ticket_upstream_500_raises():
    """Error path: upstream 5xx causes RuntimeError after retries."""
    with patch.object(
        server,
        "_request_with_retry",
        new=AsyncMock(side_effect=RuntimeError("Upstream returned 500: Internal Server Error")),
    ):
        async with Client(mcp) as client:
            with pytest.raises(Exception, match="500"):
                await client.call_tool("get_ticket", {"ticket_id": "TKT-999"})


async def test_get_ticket_upstream_404_raises():
    """Error path: upstream 404 causes RuntimeError."""
    with patch.object(
        server,
        "_request_with_retry",
        new=AsyncMock(side_effect=RuntimeError("Upstream returned 404: Not Found")),
    ):
        async with Client(mcp) as client:
            with pytest.raises(Exception, match="404"):
                await client.call_tool("get_ticket", {"ticket_id": "MISSING"})


async def test_get_ticket_network_error_raises():
    """Error path: network-level error is surfaced as RuntimeError."""
    with patch.object(
        server,
        "_request_with_retry",
        new=AsyncMock(side_effect=RuntimeError("HTTP request failed: connection refused")),
    ):
        async with Client(mcp) as client:
            with pytest.raises(Exception, match="HTTP request failed"):
                await client.call_tool("get_ticket", {"ticket_id": "TKT-001"})


async def test_get_ticket_uses_base_url_from_env(monkeypatch):
    """Verify BASE_URL env var is respected in the constructed URL."""
    monkeypatch.setenv("BASE_URL", "https://custom.tickets.test")
    # Reload the module-level BASE_URL by patching it directly on the server module
    monkeypatch.setattr(server, "BASE_URL", "https://custom.tickets.test")

    expected = {"id": "TKT-005", "status": "open"}
    captured_url = {}

    async def capture(method, url, *, headers=None, params=None, json=None):
        captured_url["url"] = url
        return expected

    with patch.object(server, "_request_with_retry", new=capture):
        async with Client(mcp) as client:
            await client.call_tool("get_ticket", {"ticket_id": "TKT-005"})

    assert captured_url["url"] == "https://custom.tickets.test/tickets/TKT-005"


# ---------------------------------------------------------------------------
# _request_with_retry integration tests (retry logic)
# ---------------------------------------------------------------------------


async def test_request_with_retry_retries_on_429():
    """Verify retry helper retries on 429 and eventually raises."""
    call_count = 0

    def make_resp(status):
        r = MagicMock(spec=httpx.Response)
        r.status_code = status
        r.text = "Too Many Requests"
        r.json.return_value = {}
        return r

    async def fake_request(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return make_resp(429)

    mock_client_instance = AsyncMock()
    mock_client_instance.request = fake_request
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("server.asyncio.sleep", new=AsyncMock()),
        patch("server.httpx.AsyncClient", return_value=mock_client_instance),
    ):
        with pytest.raises(RuntimeError, match="429"):
            await server._request_with_retry("GET", "https://api.example.test/tickets/X")

    assert call_count == server._MAX_RETRIES


async def test_request_with_retry_succeeds_after_one_retry():
    """Verify retry helper succeeds on second attempt after a 503."""
    attempt = 0
    expected_data = {"id": "TKT-OK"}

    def make_resp(status, data=None):
        r = MagicMock(spec=httpx.Response)
        r.status_code = status
        r.text = str(data or "")
        r.json.return_value = data or {}
        return r

    async def fake_request(*args, **kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            return make_resp(503)
        return make_resp(200, expected_data)

    mock_client_instance = AsyncMock()
    mock_client_instance.request = fake_request
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("server.asyncio.sleep", new=AsyncMock()),
        patch("server.httpx.AsyncClient", return_value=mock_client_instance),
    ):
        result = await server._request_with_retry(
            "GET",
            "https://api.example.test/tickets/TKT-OK",
            headers={"X-API-Key": "k"},
        )

    assert result == expected_data
    assert attempt == 2


async def test_request_with_retry_raises_on_request_error():
    """Verify network errors are wrapped in RuntimeError."""

    async def fake_request(*args, **kwargs):
        raise httpx.RequestError("connection refused")

    mock_client_instance = AsyncMock()
    mock_client_instance.request = fake_request
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("server.httpx.AsyncClient", return_value=mock_client_instance):
        with pytest.raises(RuntimeError, match="HTTP request failed"):
            await server._request_with_retry("GET", "https://api.example.test/tickets/X")


# ---------------------------------------------------------------------------
# create_ticket_note tests
# ---------------------------------------------------------------------------


async def test_create_ticket_note_success():
    """Happy path: create a note on an existing ticket."""
    expected = {"id": "NOTE-001", "ticket_id": "TKT-001", "content": "Investigating now."}

    mock_resp = _make_mock_response(201, expected)

    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(return_value=mock_resp)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("server.httpx.AsyncClient", return_value=mock_client_instance):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "create_ticket_note",
                {"ticket_id": "TKT-001", "body": {"content": "Investigating now."}},
            )

    assert result.data == expected
    mock_client_instance.post.assert_awaited_once_with(
        "https://api.example.test/tickets/TKT-001/notes",
        headers={"X-API-Key": "test-api-key-123"},
        json={"content": "Investigating now."},
    )


async def test_create_ticket_note_sends_correct_url_and_headers():
    """Verify URL path and X-API-Key header are correct."""
    expected = {"id": "NOTE-002", "ticket_id": "TKT-007"}

    mock_resp = _make_mock_response(200, expected)

    captured = {}

    async def fake_post(url, *, headers=None, json=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return mock_resp

    mock_client_instance = AsyncMock()
    mock_client_instance.post = fake_post
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("server.httpx.AsyncClient", return_value=mock_client_instance):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "create_ticket_note",
                {"ticket_id": "TKT-007", "body": {"content": "Fixed."}},
            )

    assert captured["url"] == "https://api.example.test/tickets/TKT-007/notes"
    assert captured["headers"]["X-API-Key"] == "test-api-key-123"
    assert captured["json"] == {"content": "Fixed."}
    assert result.data == expected


async def test_create_ticket_note_sends_body_as_json():
    """Verify the body dict is forwarded as JSON."""
    body_payload = {"content": "Needs more info", "author": "agent-42"}
    expected = {"id": "NOTE-003", **body_payload}

    mock_resp = _make_mock_response(201, expected)
    captured_json = {}

    async def fake_post(url, *, headers=None, json=None):
        captured_json.update(json or {})
        return mock_resp

    mock_client_instance = AsyncMock()
    mock_client_instance.post = fake_post
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("server.httpx.AsyncClient", return_value=mock_client_instance):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "create_ticket_note",
                {"ticket_id": "TKT-010", "body": body_payload},
            )

    assert captured_json == body_payload
    assert result.data == expected


async def test_create_ticket_note_empty_ticket_id_raises():
    """Error path: empty ticket_id should raise an exception."""
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "create_ticket_note",
                {"ticket_id": "  ", "body": {"content": "test"}},
            )


async def test_create_ticket_note_empty_body_raises():
    """Error path: empty body dict should raise an exception."""
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool(
                "create_ticket_note",
                {"ticket_id": "TKT-001", "body": {}},
            )


async def test_create_ticket_note_missing_api_key_raises(monkeypatch):
    """Error path: missing HOSTED_AUTH_API_KEY should raise RuntimeError."""
    monkeypatch.delenv("HOSTED_AUTH_API_KEY", raising=False)

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="HOSTED_AUTH_API_KEY"):
            await client.call_tool(
                "create_ticket_note",
                {"ticket_id": "TKT-001", "body": {"content": "test"}},
            )


async def test_create_ticket_note_upstream_400_raises():
    """Error path: upstream 4xx causes RuntimeError."""
    mock_resp = _make_mock_response(400, {"error": "Bad Request"})
    mock_resp.text = "Bad Request"

    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(return_value=mock_resp)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("server.httpx.AsyncClient", return_value=mock_client_instance):
        async with Client(mcp) as client:
            with pytest.raises(Exception, match="400"):
                await client.call_tool(
                    "create_ticket_note",
                    {"ticket_id": "TKT-001", "body": {"content": "test"}},
                )


async def test_create_ticket_note_upstream_500_raises():
    """Error path: upstream 500 causes RuntimeError."""
    mock_resp = _make_mock_response(500, {"error": "Internal Server Error"})
    mock_resp.text = "Internal Server Error"

    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(return_value=mock_resp)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("server.httpx.AsyncClient", return_value=mock_client_instance):
        async with Client(mcp) as client:
            with pytest.raises(Exception, match="500"):
                await client.call_tool(
                    "create_ticket_note",
                    {"ticket_id": "TKT-001", "body": {"content": "test"}},
                )


async def test_create_ticket_note_network_error_raises():
    """Error path: network-level error is surfaced as RuntimeError."""
    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("server.httpx.AsyncClient", return_value=mock_client_instance):
        async with Client(mcp) as client:
            with pytest.raises(Exception, match="HTTP request failed"):
                await client.call_tool(
                    "create_ticket_note",
                    {"ticket_id": "TKT-001", "body": {"content": "test"}},
                )


async def test_create_ticket_note_uses_base_url_from_env(monkeypatch):
    """Verify BASE_URL env var is respected in the constructed URL."""
    monkeypatch.setattr(server, "BASE_URL", "https://staging.tickets.test")

    expected = {"id": "NOTE-STAGING"}
    mock_resp = _make_mock_response(201, expected)
    captured_url = {}

    async def fake_post(url, *, headers=None, json=None):
        captured_url["url"] = url
        return mock_resp

    mock_client_instance = AsyncMock()
    mock_client_instance.post = fake_post
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("server.httpx.AsyncClient", return_value=mock_client_instance):
        async with Client(mcp) as client:
            await client.call_tool(
                "create_ticket_note",
                {"ticket_id": "TKT-STAGING", "body": {"content": "staging note"}},
            )

    assert captured_url["url"] == "https://staging.tickets.test/tickets/TKT-STAGING/notes"
