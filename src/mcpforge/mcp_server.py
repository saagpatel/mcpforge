"""mcpforge MCP server — expose generation capabilities as MCP tools."""

import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from mcpforge.api_client import DEFAULT_MODEL, AnthropicClient
from mcpforge.discovery import find_servers
from mcpforge.doctor import run_doctor
from mcpforge.generator import generate_server, generate_server_multi
from mcpforge.generator_ts import generate_server_ts, generate_tests_ts
from mcpforge.inspection import inspect_server
from mcpforge.openapi import load_spec, parse_openapi
from mcpforge.planner import extract_plan
from mcpforge.providers import DEFAULT_PROVIDER, create_provider_client
from mcpforge.template_hints import TEMPLATE_HINTS
from mcpforge.test_generator import generate_tests
from mcpforge.updater import update_server
from mcpforge.validator import uv_sync, validate_server
from mcpforge.validator_ts import validate_server_ts
from mcpforge.writer import write_server, write_server_multi, write_server_ts

mcp = FastMCP(
    "mcpforge",
    instructions=(
        "Generate, update, and validate FastMCP 3.x MCP servers. "
        "Use generate() to create a new server from a description, "
        "update() to modify an existing server, validate() to check it, "
        "or plan() to preview the tool plan without generating code."
    ),
)

_DEFAULT_MODEL = DEFAULT_MODEL


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


def _get_client(model: str = _DEFAULT_MODEL, provider: str = DEFAULT_PROVIDER):
    """Create a provider client, raising ToolError if required configuration is missing."""
    provider = provider.lower()
    if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise ToolError("ANTHROPIC_API_KEY environment variable is not set")
    try:
        if provider == "anthropic":
            return AnthropicClient(model=model)
        return create_provider_client(provider, model=model)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


def _validation_passed(result) -> bool:
    """Return True when structural checks and executed tests are healthy."""
    return result.is_valid and result.tests_ok


@mcp.tool
async def generate(
    description: str,
    transport: str = "streamable-http",
    output_path: str = "",
    model: str = _DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER,
    language: str = "python",
    template: str = "",
    from_openapi: str = "",
    multi_file: bool = False,
    no_execute: bool = False,
    strict: bool = False,
    dry_run: bool = False,
) -> dict:
    """Generate a complete FastMCP 3.x server from a plain-English description.

    Returns a dict with keys: path, plan (dict), valid (bool), tests_run (int).
    """
    if from_openapi:
        spec_path = _resolve_workspace_path(from_openapi, must_exist=True)
        server_plan = parse_openapi(load_spec(spec_path))
    else:
        client = _get_client(model, provider)
        server_plan = await extract_plan(description, client, transport)

    if dry_run:
        return {"plan": server_plan.model_dump(), "dry_run": True}

    if from_openapi:
        client = _get_client(model, provider)

    if output_path:
        out_dir = _resolve_workspace_path(output_path)
    else:
        workspace = Path(os.environ.get("MCPFORGE_WORKSPACE", ".")).resolve()
        out_dir = workspace / server_plan.slug

    template_hint = TEMPLATE_HINTS.get(template, "")
    if language == "typescript":
        server_code = await generate_server_ts(server_plan, client)
        test_code = await generate_tests_ts(server_plan, server_code, client)
        write_server_ts(server_plan, server_code, test_code, out_dir)
        result = await validate_server_ts(out_dir)
    elif multi_file:
        files = await generate_server_multi(server_plan, client, template_hint=template_hint)
        test_code = await generate_tests(server_plan, files.get("server.py", ""), client)
        write_server_multi(server_plan, files, test_code, out_dir)
        if not no_execute:
            await uv_sync(out_dir, plan=server_plan)
        result = await validate_server(out_dir, skip_execution=no_execute, strict=strict)
    else:
        server_code = await generate_server(server_plan, client, template_hint=template_hint)
        test_code = await generate_tests(server_plan, server_code, client)
        write_server(server_plan, server_code, test_code, out_dir)
        if not no_execute:
            await uv_sync(out_dir, plan=server_plan)
        result = await validate_server(out_dir, skip_execution=no_execute, strict=strict)

    return {
        "path": str(out_dir.resolve()),
        "plan": server_plan.model_dump(),
        "valid": _validation_passed(result),
        "structurally_valid": result.is_valid,
        "tests_ok": result.tests_ok,
        "tests_run": result.tests_run,
    }


@mcp.tool
async def update(
    server_path: str,
    request: str,
    model: str = _DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER,
) -> dict:
    """Apply a natural-language modification request to an existing MCP server.

    Returns a dict with keys: path, valid (bool), tests_run (int).
    """
    client = _get_client(model, provider)
    out_dir = _resolve_workspace_path(server_path, must_exist=True)
    server_code, test_code = await update_server(out_dir, request, client)
    (out_dir / "server.py").write_text(server_code, encoding="utf-8")
    (out_dir / "test_server.py").write_text(test_code, encoding="utf-8")
    await uv_sync(out_dir)
    result = await validate_server(out_dir)
    return {
        "path": str(out_dir.resolve()),
        "valid": _validation_passed(result),
        "structurally_valid": result.is_valid,
        "tests_ok": result.tests_ok,
        "tests_run": result.tests_run,
    }


@mcp.tool
async def validate(server_path: str) -> dict:
    """Validate an existing MCP server. Returns detailed validation results."""
    out_dir = _resolve_workspace_path(server_path, must_exist=True)
    if (out_dir / "src" / "server.ts").exists() and not (out_dir / "server.py").exists():
        result = await validate_server_ts(out_dir)
    else:
        result = await validate_server(out_dir)
    return {
        "valid": _validation_passed(result),
        "structurally_valid": result.is_valid,
        "tests_ok": result.tests_ok,
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
    provider: str = DEFAULT_PROVIDER,
) -> dict:
    """Extract the structured server plan without generating code.

    Returns a dict with keys: name, slug, description, tools (list), transport.
    """
    client = _get_client(model, provider)
    server_plan = await extract_plan(description, client, transport)
    return server_plan.model_dump()


@mcp.tool
async def inspect(server_path: str) -> dict:
    """Inspect a generated server without executing it."""
    out_dir = _resolve_workspace_path(server_path, must_exist=True)
    return inspect_server(out_dir)


@mcp.tool
async def doctor(workspace_path: str = "") -> dict:
    """Check local mcpforge prerequisites and provider readiness."""
    if workspace_path:
        workspace = _resolve_workspace_path(workspace_path, must_exist=True)
    else:
        workspace = Path(os.environ.get("MCPFORGE_WORKSPACE", ".")).resolve()
    return run_doctor(workspace)


@mcp.tool
async def list_generated_servers(workspace_path: str = "", recursive: bool = True) -> dict:
    """List generated mcpforge servers in a workspace."""
    if workspace_path:
        workspace = _resolve_workspace_path(workspace_path, must_exist=True)
    else:
        workspace = Path(os.environ.get("MCPFORGE_WORKSPACE", ".")).resolve()
    servers = find_servers(workspace, recursive=recursive)
    return {
        "root": str(workspace),
        "servers": [
            {
                "path": str(server.path),
                "name": server.name,
                "language": server.language,
                "tool_count": server.tool_count,
                "has_tests": server.has_tests,
            }
            for server in servers
        ],
    }


if __name__ == "__main__":
    mcp.run()
