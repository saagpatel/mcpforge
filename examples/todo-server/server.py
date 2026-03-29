"""In-memory TODO manager MCP server."""

from fastmcp import FastMCP
from fastmcp.exceptions import McpError

mcp = FastMCP("Todo Manager")

_todos: dict[str, dict] = {}
_next_id: int = 1


@mcp.tool
async def create_todo(title: str, description: str = "") -> dict:
    """Create a new todo item."""
    global _next_id
    if not title.strip():
        raise McpError("Title cannot be empty")
    todo_id = str(_next_id)
    _next_id += 1
    todo = {"id": todo_id, "title": title, "description": description, "done": False}
    _todos[todo_id] = todo
    return todo


@mcp.tool
async def get_todo(todo_id: str) -> dict:
    """Get a todo item by ID."""
    if todo_id not in _todos:
        raise McpError(f"Todo {todo_id!r} not found")
    return _todos[todo_id]


@mcp.tool
async def list_todos() -> list[dict]:
    """List all todo items."""
    return list(_todos.values())


@mcp.tool
async def update_todo(
    todo_id: str,
    title: str | None = None,
    description: str | None = None,
    done: bool | None = None,
) -> dict:
    """Update a todo item."""
    if todo_id not in _todos:
        raise McpError(f"Todo {todo_id!r} not found")
    todo = _todos[todo_id]
    if title is not None:
        todo["title"] = title
    if description is not None:
        todo["description"] = description
    if done is not None:
        todo["done"] = done
    return todo


@mcp.tool
async def delete_todo(todo_id: str) -> dict:
    """Delete a todo item."""
    if todo_id not in _todos:
        raise McpError(f"Todo {todo_id!r} not found")
    todo = _todos.pop(todo_id)
    return {"deleted": True, "id": todo_id, "title": todo["title"]}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
