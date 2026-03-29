"""Sample natural language descriptions used across tests and examples."""

TODO_DESCRIPTION = (
    "A server that manages TODO items. "
    "Users can create todos with a title and optional description, "
    "list all todos (with optional completion filter), "
    "get a single todo by ID, update a todo's title or completion status, "
    "and delete todos."
)

WEATHER_DESCRIPTION = (
    "A weather information server that fetches current conditions and forecasts. "
    "Users can get current weather by city name or coordinates, "
    "get a 7-day forecast, and search for city names. "
    "Requires an OPENWEATHER_API_KEY environment variable."
)

FILE_READER_DESCRIPTION = (
    "A local file reader server that allows reading text files from a configured directory. "
    "Users can list files in the directory, read a file by name, "
    "search file contents for a pattern, and get file metadata (size, modified time). "
    "The root directory is configured via a FILES_ROOT environment variable."
)
