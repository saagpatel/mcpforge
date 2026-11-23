"""Project-level metadata and public-doc smoke tests."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from fastmcp import Client

import mcpforge
from mcpforge.mcp_server import mcp


def test_readme_uses_current_mcpaudit_package_and_registry_boundary() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "uvx --from mcp-audits mcp-audit scan" in readme
    assert "mcp-permission-audit" not in readme
    assert "server.json" in readme
    assert "io.github.saagpatel/mcpforge" in readme
    assert "not as proof that generated servers are safe" in readme


def test_registry_metadata_matches_package_version() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    metadata = json.loads(Path("server.json").read_text(encoding="utf-8"))

    assert metadata["name"] == "io.github.saagpatel/mcpforge"
    assert metadata["version"] == project["version"]
    assert metadata["packages"] == [
        {
            "registryType": "pypi",
            "registryBaseUrl": "https://pypi.org",
            "identifier": project["name"],
            "version": project["version"],
            "runtimeHint": "uvx",
            "transport": {"type": "stdio"},
        }
    ]


async def test_runtime_version_matches_package_version() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert mcpforge.__version__ == project["version"]

    async with Client(mcp) as client:
        assert client.initialize_result.serverInfo.version == mcpforge.__version__


async def test_readme_tool_inventory_matches_registration():
    readme = Path("README.md").read_text(encoding="utf-8")
    section = readme.split("## Use as an MCP server\n", 1)[1].split("\n## ", 1)[0]
    rows = {}
    for line in section.splitlines():
        if line.startswith("| `"):
            columns = [column.strip() for column in line.strip("|").split("|")]
            rows[columns[0].strip("`")] = columns
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert set(rows) == {tool.name for tool in tools}
    for tool in tools:
        assert set(re.findall(r"`([a-z_]+)`", rows[tool.name][-1])) == set(
            tool.inputSchema["properties"]
        ), tool.name
    assert "uv sync" in rows["validate"][2] and "npm install" in rows["validate"][2]
    assert "Vitest" in rows["validate"][1] and "pytest" in rows["validate"][1]
    assert "temporary" in rows["doctor"][2]
