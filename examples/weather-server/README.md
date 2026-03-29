# Weather Server MCP Server

Provides current weather and forecast data via the OpenWeatherMap API.

## Tools

- `get_current_weather(city)` — Get current weather for a city
- `get_forecast(city, days?)` — Get weather forecast (1-5 days)

## Setup

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENWEATHER_API_KEY` | Yes | Your OpenWeatherMap API key |

## Run

```bash
OPENWEATHER_API_KEY=your-key uv sync && uv run server.py
```

## Test

```bash
uv run pytest -v
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "weather-server": {
      "command": "uv",
      "args": ["run", "server.py"],
      "env": {"OPENWEATHER_API_KEY": "your-key-here"}
    }
  }
}
```
