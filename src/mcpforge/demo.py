"""Built-in offline demo: generate a weather MCP server from a recording.

``mcpforge demo`` runs the real generation pipeline against a hand-authored
cassette (a recorded plan plus the server and test source), so a new user can
watch mcpforge plan, generate, and validate a complete server before they have
an API key. The generated weather server integrates a real API
(OpenWeatherMap) but its test suite is fully mocked, so validation passes
offline.
"""

from importlib.resources import files

from mcpforge.models import ServerPlan, ToolDef, ToolParam
from mcpforge.replay_client import ReplayClient

WEATHER_DEMO_DESCRIPTION = (
    "A weather server that returns the current conditions and a multi-day "
    "forecast for any city using the OpenWeatherMap API."
)


def build_weather_plan() -> ServerPlan:
    """The recorded plan for the demo weather server (matches the cassette code)."""
    return ServerPlan(
        name="Weather Server",
        description=(
            "Fetches current weather and multi-day forecasts for any city from "
            "the OpenWeatherMap API."
        ),
        tools=[
            ToolDef(
                name="get_current_weather",
                description="Get current weather for a city.",
                params=[
                    ToolParam(
                        name="city",
                        type="str",
                        description="City name, e.g. 'London' or 'San Francisco'.",
                    ),
                ],
                return_type="dict",
                error_cases=["OPENWEATHER_API_KEY is not set"],
            ),
            ToolDef(
                name="get_forecast",
                description="Get weather forecast for a city (1-5 days).",
                params=[
                    ToolParam(
                        name="city",
                        type="str",
                        description="City name to forecast.",
                    ),
                    ToolParam(
                        name="days",
                        type="int",
                        description="Number of forecast days (1-5).",
                        required=False,
                        default="3",
                    ),
                ],
                return_type="dict",
                error_cases=["days must be between 1 and 5", "OPENWEATHER_API_KEY is not set"],
            ),
        ],
        env_vars=["OPENWEATHER_API_KEY"],
        external_packages=["httpx"],
        transport="streamable-http",
    )


def _load_cassette_source(name: str) -> str:
    """Read a recorded source file packaged under demo_assets/."""
    return files("mcpforge").joinpath("demo_assets", name).read_text(encoding="utf-8")


def load_demo_client() -> ReplayClient:
    """Build a ReplayClient that drives the recorded weather-server generation."""
    server_code = _load_cassette_source("server.py")
    test_code = _load_cassette_source("test_server.py")
    return ReplayClient(build_weather_plan(), [server_code, test_code])
