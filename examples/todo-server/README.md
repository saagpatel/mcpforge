# Todo Manager MCP Server

An in-memory todo list manager for Claude Desktop and other MCP clients.

## Tools

- `create_todo(title, description?)` — Create a new todo item
- `get_todo(todo_id)` — Get a todo item by ID
- `list_todos()` — List all todo items
- `update_todo(todo_id, title?, description?, done?)` — Update a todo item
- `delete_todo(todo_id)` — Delete a todo item

## Setup

No external dependencies or env vars required.

## Run

```bash
uv sync
uv run server.py
```

## Test

```bash
uv run pytest -v
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "todo-manager": {
      "command": "uv",
      "args": ["run", "server.py"],
      "env": {}
    }
  }
}
```
