"""Tests for the Weather Server MCP server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import server as srv
from fastmcp import Client


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key-123")


def _make_mock_client(json_data: dict):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = json_data
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


async def test_get_current_weather_success():
    weather_data = {
        "name": "London",
        "main": {"temp": 15.2, "feels_like": 13.0, "humidity": 72},
        "weather": [{"description": "overcast clouds"}],
    }
    with patch("httpx.AsyncClient", return_value=_make_mock_client(weather_data)):
        async with Client(srv.mcp) as client:
            result = await client.call_tool("get_current_weather", {"city": "London"})
    assert result.data["city"] == "London"
    assert result.data["temperature"] == 15.2
    assert result.data["description"] == "overcast clouds"


async def test_get_current_weather_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    async with Client(srv.mcp) as client:
        with pytest.raises(Exception, match="OPENWEATHER_API_KEY"):
            await client.call_tool("get_current_weather", {"city": "London"})


async def test_get_forecast_success():
    forecast_data = {
        "city": {"name": "Paris"},
        "list": [
            {
                "dt_txt": "2025-01-01 12:00:00",
                "main": {"temp": 10.0},
                "weather": [{"description": "light rain"}],
            }
        ],
    }
    with patch("httpx.AsyncClient", return_value=_make_mock_client(forecast_data)):
        async with Client(srv.mcp) as client:
            result = await client.call_tool("get_forecast", {"city": "Paris", "days": 1})
    assert result.data["city"] == "Paris"
    assert len(result.data["forecasts"]) == 1


async def test_get_forecast_invalid_days():
    async with Client(srv.mcp) as client:
        with pytest.raises(Exception, match="between 1 and 5"):
            await client.call_tool("get_forecast", {"city": "Paris", "days": 10})
