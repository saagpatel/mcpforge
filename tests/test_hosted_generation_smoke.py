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

from mcpforge.cli import cli

ROOT = Path(__file__).resolve().parents[1]
AUTH_OPENAPI_SPEC = ROOT / "tests" / "fixtures" / "openapi-auth-tickets.json"


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
