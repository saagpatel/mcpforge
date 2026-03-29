"""Tests for the Slack Notifier MCP server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import server as srv
from fastmcp import Client

_TEST_TOKEN = "fake-slack-bot-token-for-testing"


@pytest.fixture(autouse=True)
def set_slack_token(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", _TEST_TOKEN)


def _make_mock_client(json_data: dict, status_code: int = 200):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = json_data
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


async def test_send_message_success():
    slack_response = {"ok": True, "ts": "1234567890.123456"}
    with patch("httpx.AsyncClient", return_value=_make_mock_client(slack_response)):
        async with Client(srv.mcp) as client:
            result = await client.call_tool(
                "send_message", {"channel": "general", "text": "Hello!"}
            )
    assert result.data["ok"] is True
    assert result.data["channel"] == "general"


async def test_send_message_no_token(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    async with Client(srv.mcp) as client:
        with pytest.raises(Exception, match="SLACK_BOT_TOKEN"):
            await client.call_tool("send_message", {"channel": "general", "text": "Hi"})


async def test_list_channels_success():
    slack_response = {
        "ok": True,
        "channels": [
            {"id": "C001", "name": "general"},
            {"id": "C002", "name": "random"},
        ],
    }
    with patch("httpx.AsyncClient", return_value=_make_mock_client(slack_response)):
        async with Client(srv.mcp) as client:
            result = await client.call_tool("list_channels", {})
    assert len(result.data["channels"]) == 2
    assert result.data["channels"][0]["name"] == "general"


async def test_get_channel_history_success():
    slack_response = {
        "ok": True,
        "messages": [
            {"text": "Hello", "ts": "1234567890.000001"},
            {"text": "World", "ts": "1234567890.000002"},
        ],
    }
    with patch("httpx.AsyncClient", return_value=_make_mock_client(slack_response)):
        async with Client(srv.mcp) as client:
            result = await client.call_tool(
                "get_channel_history", {"channel": "general", "limit": 5}
            )
    assert len(result.data["messages"]) == 2


async def test_get_channel_history_invalid_limit():
    async with Client(srv.mcp) as client:
        with pytest.raises(Exception, match="between 1 and 100"):
            await client.call_tool(
                "get_channel_history", {"channel": "general", "limit": 0}
            )
