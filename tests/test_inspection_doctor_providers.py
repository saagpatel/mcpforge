"""Tests for v0.3 inspection, doctor, and provider planning surfaces."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcpforge.doctor import run_doctor
from mcpforge.inspection import inspect_server
from mcpforge.models import ServerPlan
from mcpforge.profiles import apply_generation_profiles
from mcpforge.providers import create_provider_client, provider_capabilities


def test_inspect_python_server_counts_components_and_env(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(
        json.dumps({"mcpServers": {"demo": {"command": "uv"}}}), encoding="utf-8"
    )
    (tmp_path / "fastmcp.json").write_text(
        json.dumps({"deployment": {"transport": "http", "path": "/mcp/"}}), encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# demo\n\n## Remote MCP Readiness\n\n## Security Notes\n", encoding="utf-8"
    )
    (tmp_path / "test_server.py").write_text("def test_ok(): pass", encoding="utf-8")
    (tmp_path / ".env.example").write_text("API_KEY=\n", encoding="utf-8")
    (tmp_path / "server.py").write_text(
        """
from fastmcp import FastMCP
mcp = FastMCP("Demo")

@mcp.tool
async def search_items(query: str) -> dict:
    return {"query": query}

@mcp.resource("data://config")
def config_resource() -> dict:
    return {}

@mcp.prompt
def summarize() -> str:
    return "Summarize."
""",
        encoding="utf-8",
    )

    result = inspect_server(tmp_path)

    assert result["name"] == "demo"
    assert result["language"] == "python"
    assert result["tools"]["names"] == ["search_items"]
    assert result["resources"]["names"] == ["config_resource"]
    assert result["prompts"]["names"] == ["summarize"]
    assert result["env_vars"] == ["API_KEY"]
    assert result["validation_ready"] is True
    assert result["remote_mcp"]["ready"] is True


def test_inspect_typescript_server_counts_tools(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (tmp_path / "config.json").write_text(
        json.dumps({"mcpServers": {"ts-demo": {"command": "npm"}}}), encoding="utf-8"
    )
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
    (src / "server.test.ts").write_text("test('ok', () => {})", encoding="utf-8")
    (src / "server.ts").write_text(
        'server.tool("search_items", "Search", {}, async () => ({ content: [] }));',
        encoding="utf-8",
    )

    result = inspect_server(tmp_path)

    assert result["language"] == "typescript"
    assert result["tools"]["names"] == ["search_items"]
    assert result["validation_ready"] is True
    assert result["remote_mcp"]["ready"] is False


def test_doctor_reports_provider_capabilities(tmp_path: Path) -> None:
    with patch("mcpforge.doctor._command_version") as command_version:
        command_version.side_effect = lambda name, *args: {
            "name": name,
            "ok": name in {"uv", "ruff", "pytest"},
            "path": f"/bin/{name}",
            "version": "test",
            "detail": "",
        }
        result = run_doctor(tmp_path)

    assert result["ok"] is True
    assert result["provider"]["default_provider"] == "anthropic"
    assert any(
        cap["name"] == "openai" and cap["status"] == "gated"
        for cap in result["provider"]["capabilities"]
    )
    assert "openai_api_key" in result


def test_provider_capabilities_and_openai_gate() -> None:
    assert provider_capabilities("anthropic").structured_json is True
    assert provider_capabilities("openai").structured_json is True
    assert provider_capabilities("openai").status == "gated"
    with pytest.raises(ValueError, match="OpenAI provider support is gated"):
        create_provider_client("openai")


def test_openai_provider_can_be_opted_in_for_smokes(monkeypatch) -> None:
    monkeypatch.setenv("MCPFORGE_ENABLE_OPENAI_PROVIDER", "1")
    with patch("mcpforge.providers.OpenAIClient", return_value=MagicMock()) as openai_client:
        create_provider_client("openai")

    openai_client.assert_called_once()


def test_openrouter_provider_is_bring_your_own_not_gated() -> None:
    cap = provider_capabilities("openrouter")
    assert cap.status == "bring-your-own"
    assert cap.structured_json is True
    assert cap.streaming is True


def test_openrouter_defaults_model_when_caller_did_not_override() -> None:
    from mcpforge.api_client import DEFAULT_MODEL
    from mcpforge.openrouter_client import DEFAULT_OPENROUTER_MODEL

    with patch("mcpforge.providers.OpenRouterClient", return_value=MagicMock()) as ctor:
        create_provider_client("openrouter", model=DEFAULT_MODEL)

    ctor.assert_called_once_with(model=DEFAULT_OPENROUTER_MODEL)


def test_openrouter_passes_explicit_model_through() -> None:
    with patch("mcpforge.providers.OpenRouterClient", return_value=MagicMock()) as ctor:
        create_provider_client("openrouter", model="meta-llama/llama-3.3-70b-instruct:free")

    ctor.assert_called_once_with(model="meta-llama/llama-3.3-70b-instruct:free")


def test_apply_generation_profiles_adds_env_and_metadata() -> None:
    plan = ServerPlan(name="Demo", description="Demo", tools=[])

    updated = apply_generation_profiles(
        plan,
        auth_profile="jwt",
        middleware_profiles=("logging", "rate-limit", "logging"),
    )

    assert updated.auth_profile == "jwt"
    assert updated.middleware_profiles == ["logging", "rate-limit"]
    assert "JWT_JWKS_URI" in updated.env_vars
    assert "JWT_ISSUER" in updated.env_vars
    assert "JWT_AUDIENCE" in updated.env_vars
    assert "RATE_LIMIT_RPS" in updated.env_vars
