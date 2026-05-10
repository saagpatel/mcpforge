"""Regression checks for committed generated fixture examples."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def test_v03_fixtures_include_runtime_docs_and_configs() -> None:
    """High-value v0.3 fixtures keep generated setup files checked in."""
    for name in [
        "v03-rest-api-server",
        "v03-filesystem-server",
        "v03-database-server",
        "v03-typescript-todo-server",
    ]:
        root = EXAMPLES / name
        assert (root / ".env.example").exists(), name
        assert (root / "README.md").exists(), name
        assert (root / "config.json").exists(), name

    for name in ["v03-rest-api-server", "v03-filesystem-server", "v03-database-server"]:
        assert (EXAMPLES / name / "fastmcp.json").exists(), name


def test_v03_fixtures_do_not_commit_dependency_artifacts() -> None:
    """Generated fixtures should not check in local installs or lock churn."""
    forbidden = {"node_modules", ".venv", "uv.lock", "package-lock.json"}
    found = [
        path
        for path in EXAMPLES.glob("v03-*")
        for child in path.rglob("*")
        if child.name in forbidden
    ]
    assert found == []


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
