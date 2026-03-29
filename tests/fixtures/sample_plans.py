"""Pre-built ServerPlan instances used across tests.

These correspond to the sample descriptions in sample_descriptions.py and
represent expected planner output for use in generator/validator tests.
"""

from mcpforge.models import ServerPlan, ToolDef, ToolParam

TODO_PLAN = ServerPlan(
    name="Todo Manager",
    slug="todo-manager",
    description="An MCP server for managing TODO items with full CRUD operations.",
    version="0.1.0",
    transport="streamable-http",
    tools=[
        ToolDef(
            name="create_todo",
            description="Create a new TODO item with a title and optional description.",
            params=[
                ToolParam(name="title", type="str", description="The TODO item title"),
                ToolParam(
                    name="description",
                    type="str | None",
                    description="Optional longer description",
                    required=False,
                    default="None",
                ),
            ],
            return_type="dict",
            is_async=True,
            error_cases=["title is empty"],
        ),
        ToolDef(
            name="list_todos",
            description="List all TODO items, optionally filtered by completion status.",
            params=[
                ToolParam(
                    name="completed",
                    type="bool | None",
                    description="Filter by completion status, or None for all",
                    required=False,
                    default="None",
                ),
            ],
            return_type="list[dict]",
            is_async=True,
        ),
        ToolDef(
            name="get_todo",
            description="Retrieve a single TODO item by its ID.",
            params=[
                ToolParam(name="todo_id", type="str", description="The unique TODO item ID"),
            ],
            return_type="dict",
            is_async=True,
            error_cases=["todo_id not found"],
        ),
        ToolDef(
            name="update_todo",
            description="Update an existing TODO item by ID.",
            params=[
                ToolParam(name="todo_id", type="str", description="The unique TODO item ID"),
                ToolParam(
                    name="title",
                    type="str | None",
                    description="New title",
                    required=False,
                    default="None",
                ),
                ToolParam(
                    name="completed",
                    type="bool | None",
                    description="New completion status",
                    required=False,
                    default="None",
                ),
            ],
            return_type="dict",
            is_async=True,
            error_cases=["todo_id not found", "no fields to update provided"],
        ),
        ToolDef(
            name="delete_todo",
            description="Delete a TODO item by ID.",
            params=[
                ToolParam(name="todo_id", type="str", description="The unique TODO item ID"),
            ],
            return_type="dict",
            is_async=True,
            error_cases=["todo_id not found"],
        ),
    ],
    env_vars=[],
    external_packages=[],
)

WEATHER_PLAN = ServerPlan(
    name="Weather Service",
    slug="weather-service",
    description="An MCP server for fetching current weather and forecasts via OpenWeatherMap.",
    version="0.1.0",
    transport="streamable-http",
    tools=[
        ToolDef(
            name="get_current_weather",
            description="Get current weather conditions for a city.",
            params=[
                ToolParam(name="city", type="str", description="City name"),
            ],
            return_type="dict",
            is_async=True,
            error_cases=["city not found", "API key missing or invalid"],
        ),
        ToolDef(
            name="get_forecast",
            description="Get a 7-day weather forecast for a city.",
            params=[
                ToolParam(name="city", type="str", description="City name"),
                ToolParam(
                    name="days",
                    type="int",
                    description="Number of forecast days (1-7)",
                    required=False,
                    default="7",
                ),
            ],
            return_type="list[dict]",
            is_async=True,
            error_cases=["city not found", "days must be between 1 and 7"],
        ),
    ],
    env_vars=["OPENWEATHER_API_KEY"],
    external_packages=["httpx"],
)
