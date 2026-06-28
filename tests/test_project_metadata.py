"""Project-level metadata and public-doc smoke tests."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path


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
