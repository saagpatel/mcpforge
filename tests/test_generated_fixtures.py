"""Regression checks for committed generated fixture examples."""

from pathlib import Path

from mcpforge.inspection import inspect_server

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def test_v03_fixtures_include_runtime_docs_and_configs() -> None:
    """High-value v0.3 fixtures keep generated setup files checked in."""
    for name in [
        "v03-rest-api-server",
        "v03-authenticated-openapi-server",
        "v03-filesystem-server",
        "v03-database-server",
        "v03-typescript-todo-server",
    ]:
        root = EXAMPLES / name
        assert (root / ".env.example").exists(), name
        assert (root / "README.md").exists(), name
        assert (root / "config.json").exists(), name

    for name in [
        "v03-rest-api-server",
        "v03-authenticated-openapi-server",
        "v03-filesystem-server",
        "v03-database-server",
    ]:
        assert (EXAMPLES / name / "fastmcp.json").exists(), name


def test_v03_fixtures_do_not_commit_dependency_artifacts() -> None:
    """Generated fixtures should not check in local installs or lock churn."""
    import subprocess

    forbidden = {"node_modules", ".venv", "uv.lock", "package-lock.json"}
    violations: list[str] = []
    for v03_dir in EXAMPLES.glob("v03-*"):
        result = subprocess.run(
            ["git", "ls-files", str(v03_dir)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        tracked_names = {Path(p).name for p in result.stdout.splitlines()}
        committed = tracked_names & forbidden
        if committed:
            violations.append(f"{v03_dir.name}: {committed}")
    assert violations == [], f"Committed dependency artifacts: {violations}"


def test_filesystem_resource_returns_serialized_content() -> None:
    """FastMCP resources must return text/bytes/resource content, not bare dicts."""
    server_py = (EXAMPLES / "v03-filesystem-server" / "server.py").read_text(encoding="utf-8")
    assert "async def workspace_summary() -> str:" in server_py
    assert "json.dumps" in server_py


def test_typescript_fixture_uses_supported_stdio_transport() -> None:
    """The TypeScript SDK fixture stays on the supported stdio transport path."""
    server_ts = (EXAMPLES / "v03-typescript-todo-server" / "src" / "server.ts").read_text(
        encoding="utf-8"
    )
    assert "StdioServerTransport" in server_ts
    assert "StreamableHTTPServerTransport" not in server_ts


def test_authenticated_openapi_fixture_preserves_auth_and_request_shape() -> None:
    """The authenticated OpenAPI fixture demonstrates header auth and param partitioning."""
    root = EXAMPLES / "v03-authenticated-openapi-server"
    server_py = (root / "server.py").read_text(encoding="utf-8")
    env_example = (root / ".env.example").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert "HOSTED_AUTH_API_KEY" in env_example
    assert "MCPFORGE_SERVER_API_KEY" in env_example
    assert '"X-API-Key": api_key' in server_py
    assert "params=query_params or None" in server_py
    assert "json=body" in server_py
    assert "Auth credential env var: `HOSTED_AUTH_API_KEY`" in readme
    assert "## Remote MCP Readiness" in readme
    assert inspect_server(root)["remote_mcp"]["ready"] is True
