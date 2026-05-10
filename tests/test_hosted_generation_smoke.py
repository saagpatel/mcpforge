"""Opt-in hosted generation smoke test.

This test is intentionally skipped by default so normal local and CI runs do not
make paid API calls. Enable it for release readiness with:

    MCPFORGE_RUN_HOSTED_SMOKE=1 ANTHROPIC_API_KEY=... \
        uv run pytest tests/test_hosted_generation_smoke.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import BaseModel

from mcpforge.cli import cli
from mcpforge.openai_client import OpenAIClient
from mcpforge.planner import extract_plan

ROOT = Path(__file__).resolve().parents[1]
AUTH_OPENAPI_SPEC = ROOT / "tests" / "fixtures" / "openapi-auth-tickets.json"


class OpenAIStructuredSmoke(BaseModel):
    """Small schema used by the OpenAI hosted structured-output smoke."""

    name: str
    count: int
    ready: bool


def _assert_valid_generation(result_output: str) -> None:
    """Assert hosted generation validated successfully without matching INVALID."""
    assert "Status: VALID" in result_output
    assert "Status: INVALID" not in result_output


@pytest.mark.skipif(
    os.environ.get("MCPFORGE_RUN_HOSTED_SMOKE") != "1",
    reason="set MCPFORGE_RUN_HOSTED_SMOKE=1 to run the hosted generation smoke",
)
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY is required for hosted generation smoke",
)
def test_hosted_generate_echo_server(tmp_path: Path) -> None:
    """Generate and validate a tiny server through the real hosted model."""
    output_dir = tmp_path / "hosted-echo-server"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "generate",
            "A tiny echo MCP server with one tool named echo_message that returns "
            "the provided message.",
            "--output",
            str(output_dir),
            "--yes",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert (output_dir / "server.py").exists()
    assert (output_dir / "test_server.py").exists()
    _assert_valid_generation(result.output)


@pytest.mark.skipif(
    os.environ.get("MCPFORGE_RUN_HOSTED_TS_SMOKE") != "1",
    reason="set MCPFORGE_RUN_HOSTED_TS_SMOKE=1 to run the hosted TypeScript smoke",
)
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY is required for hosted TypeScript generation smoke",
)
def test_hosted_generate_typescript_echo_server(tmp_path: Path) -> None:
    """Generate and validate a tiny TypeScript server through the real hosted model."""
    output_dir = tmp_path / "hosted-ts-echo-server"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "generate",
            "A tiny echo MCP server with one tool named echo_message that returns "
            "the provided message.",
            "--language",
            "typescript",
            "--output",
            str(output_dir),
            "--yes",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert (output_dir / "src" / "server.ts").exists()
    assert (output_dir / "src" / "server.test.ts").exists()
    assert (output_dir / "config.json").exists()
    _assert_valid_generation(result.output)


@pytest.mark.skipif(
    os.environ.get("MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE") != "1",
    reason="set MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE=1 to run the hosted OpenAPI auth smoke",
)
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY is required for hosted OpenAPI generation smoke",
)
def test_hosted_generate_openapi_auth_server(tmp_path: Path) -> None:
    """Generate an authenticated OpenAPI server through the real hosted model."""
    output_dir = tmp_path / "hosted-openapi-auth-server"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "generate",
            "Generate a production-ready MCP wrapper for this authenticated ticket API.",
            "--from-openapi",
            str(AUTH_OPENAPI_SPEC),
            "--output",
            str(output_dir),
            "--auth-profile",
            "api-key",
            "--middleware-profile",
            "logging",
            "--middleware-profile",
            "timing",
            "--yes",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    server_code = (output_dir / "server.py").read_text(encoding="utf-8")
    env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
    readme = (output_dir / "README.md").read_text(encoding="utf-8")

    assert (output_dir / "test_server.py").exists()
    assert (output_dir / "fastmcp.json").exists()
    assert "HOSTED_AUTH_API_KEY" in env_example
    assert "BASE_URL" in env_example
    assert "REQUEST_TIMEOUT_SECONDS" in env_example
    assert "HOSTED_AUTH_API_KEY" in server_code
    assert "X-API-Key" in server_code
    assert "REQUEST_TIMEOUT_SECONDS" in server_code
    assert "params=" in server_code
    assert "headers=" in server_code
    assert "json=body" in server_code
    assert "Auth credential env var: `HOSTED_AUTH_API_KEY`" in readme
    _assert_valid_generation(result.output)


@pytest.mark.skipif(
    os.environ.get("MCPFORGE_RUN_HOSTED_OPENAI_SMOKE") != "1",
    reason="set MCPFORGE_RUN_HOSTED_OPENAI_SMOKE=1 to run the hosted OpenAI smoke",
)
@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is required for hosted OpenAI structured-output smoke",
)
async def test_hosted_openai_structured_output_smoke() -> None:
    """Prove OpenAI structured outputs before enabling the full provider path."""
    client = OpenAIClient()

    result = await client.generate_json(
        "Return only the requested structured readiness object.",
        "Return name='openai', count=3, ready=true.",
        OpenAIStructuredSmoke,
        max_tokens=256,
    )

    assert result == OpenAIStructuredSmoke(name="openai", count=3, ready=True)


@pytest.mark.skipif(
    os.environ.get("MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE") != "1",
    reason="set MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE=1 to run OpenAI planning smoke",
)
@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is required for hosted OpenAI planning smoke",
)
async def test_hosted_openai_planning_smoke() -> None:
    """Prove OpenAI can produce a strict mcpforge ServerPlan."""
    client = OpenAIClient()

    plan = await extract_plan(
        "A tiny echo MCP server with one tool named echo_message that returns "
        "the provided message.",
        client,
        "streamable-http",
    )

    assert plan.name
    assert any(tool.name == "echo_message" for tool in plan.tools)


@pytest.mark.skipif(
    os.environ.get("MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE") != "1",
    reason="set MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE=1 to run OpenAI generation smoke",
)
@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is required for hosted OpenAI generation smoke",
)
def test_hosted_openai_generate_echo_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generate and validate a tiny server through OpenAI's opt-in provider path."""
    output_dir = tmp_path / "hosted-openai-echo-server"
    runner = CliRunner()
    monkeypatch.setenv("MCPFORGE_ENABLE_OPENAI_PROVIDER", "1")

    result = runner.invoke(
        cli,
        [
            "generate",
            "A tiny echo MCP server with one tool named echo_message that returns "
            "the provided message.",
            "--provider",
            "openai",
            "--output",
            str(output_dir),
            "--yes",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert (output_dir / "server.py").exists()
    assert (output_dir / "test_server.py").exists()
    _assert_valid_generation(result.output)
