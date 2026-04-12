"""mcpforge MCP server — expose generation capabilities as MCP tools."""

import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from mcpforge.api_client import AnthropicClient
from mcpforge.generator import generate_server
from mcpforge.planner import extract_plan
from mcpforge.test_generator import generate_tests
from mcpforge.updater import update_server
from mcpforge.validator import uv_sync, validate_server
from mcpforge.writer import write_server

mcp = FastMCP(
    "mcpforge",
    instructions=(
        "Generate, update, and validate FastMCP 3.x MCP servers. "
        "Use generate() to create a new server from a description, "
        "update() to modify an existing server, validate() to check it, "
        "or plan() to preview the tool plan without generating code."
    ),
)

_DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _resolve_workspace_path(raw_path: str, *, must_exist: bool = False) -> Path:
    """Resolve a path and validate it falls within the configured workspace.

    Reads MCPFORGE_WORKSPACE env var (defaults to cwd). Raises ToolError if the
    resolved path escapes the workspace boundary.
    """
    workspace = Path(os.environ.get("MCPFORGE_WORKSPACE", ".")).resolve()
    resolved = Path(raw_path).resolve()
    if not resolved.is_relative_to(workspace):
        raise ToolError(
            f"Path '{raw_path}' resolves outside workspace '{workspace}'. "
            "Set MCPFORGE_WORKSPACE to expand the allowed directory."
        )
    if must_exist and not resolved.exists():
        raise ToolError(f"Path does not exist: {resolved}")
    return resolved


def _get_client(model: str = _DEFAULT_MODEL) -> AnthropicClient:
    """Create an AnthropicClient, raising McpError if API key is missing."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ToolError("ANTHROPIC_API_KEY environment variable is not set")
    return AnthropicClient(api_key=key, model=model)


@mcp.tool
async def generate(
    description: str,
    transport: str = "streamable-http",
    output_path: str = "",
    model: str = _DEFAULT_MODEL,
) -> dict:
    """Generate a complete FastMCP 3.x server from a plain-English description.

    Returns a dict with keys: path, plan (dict), valid (bool), tests_run (int).
    """
    client = _get_client(model)
    server_plan = await extract_plan(description, client, transport)
    server_code = await generate_server(server_plan, client)
    test_code = await generate_tests(server_plan, server_code, client)

    if output_path:
        out_dir = _resolve_workspace_path(output_path)
    else:
        workspace = Path(os.environ.get("MCPFORGE_WORKSPACE", ".")).resolve()
        out_dir = workspace / server_plan.slug
    write_server(server_plan, server_code, test_code, out_dir)
    await uv_sync(out_dir, plan=server_plan)
    result = await validate_server(out_dir)

    return {
        "path": str(out_dir.resolve()),
        "plan": server_plan.model_dump(),
        "valid": result.is_valid,
        "tests_run": result.tests_run,
    }


@mcp.tool
async def update(
    server_path: str,
    request: str,
    model: str = _DEFAULT_MODEL,
) -> dict:
    """Apply a natural-language modification request to an existing MCP server.

    Returns a dict with keys: path, valid (bool), tests_run (int).
    """
    client = _get_client(model)
    out_dir = _resolve_workspace_path(server_path, must_exist=True)
    server_code, test_code = await update_server(out_dir, request, client)
    (out_dir / "server.py").write_text(server_code, encoding="utf-8")
    (out_dir / "test_server.py").write_text(test_code, encoding="utf-8")
    await uv_sync(out_dir)
    result = await validate_server(out_dir)
    return {
        "path": str(out_dir.resolve()),
        "valid": result.is_valid,
        "tests_run": result.tests_run,
    }


@mcp.tool
async def validate(server_path: str) -> dict:
    """Validate an existing MCP server. Returns detailed validation results."""
    out_dir = _resolve_workspace_path(server_path, must_exist=True)
    result = await validate_server(out_dir)
    return {
        "valid": result.is_valid,
        "syntax_ok": result.syntax_ok,
        "import_ok": result.import_ok,
        "lint_errors": result.lint_errors,
        "tests_run": result.tests_run,
        "tests_failed": result.tests_failed,
    }


@mcp.tool
async def plan(
    description: str,
    transport: str = "streamable-http",
    model: str = _DEFAULT_MODEL,
) -> dict:
    """Extract the structured server plan without generating code.

    Returns a dict with keys: name, slug, description, tools (list), transport.
    """
    client = _get_client(model)
    server_plan = await extract_plan(description, client, transport)
    return {
        "name": server_plan.name,
        "slug": server_plan.slug,
        "description": server_plan.description,
        "tools": [
            {"name": t.name, "description": t.description, "params": len(t.params)}
            for t in server_plan.tools
        ],
        "transport": server_plan.transport,
    }


if __name__ == "__main__":
    mcp.run()
