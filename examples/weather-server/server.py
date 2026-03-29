"""OpenWeatherMap weather data MCP server."""

import os

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import McpError

mcp = FastMCP("Weather Server")

OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5"


@mcp.tool
async def get_current_weather(city: str) -> dict:
    """Get current weather for a city."""
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key:
        raise McpError("OPENWEATHER_API_KEY environment variable is not set")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{OPENWEATHER_BASE}/weather",
            params={"q": city, "appid": api_key, "units": "metric"},
        )
        response.raise_for_status()
        data = response.json()
    return {
        "city": data["name"],
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "description": data["weather"][0]["description"],
    }


@mcp.tool
async def get_forecast(city: str, days: int = 3) -> dict:
    """Get weather forecast for a city (1-5 days)."""
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key:
        raise McpError("OPENWEATHER_API_KEY environment variable is not set")
    if not 1 <= days <= 5:
        raise McpError("days must be between 1 and 5")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{OPENWEATHER_BASE}/forecast",
            params={"q": city, "cnt": days * 8, "appid": api_key, "units": "metric"},
        )
        response.raise_for_status()
        data = response.json()
    forecasts = [
        {
            "datetime": item["dt_txt"],
            "temperature": item["main"]["temp"],
            "description": item["weather"][0]["description"],
        }
        for item in data["list"]
    ]
    return {"city": data["city"]["name"], "days": days, "forecasts": forecasts}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
