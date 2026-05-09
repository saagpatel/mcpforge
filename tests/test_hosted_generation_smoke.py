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
    assert "VALID" in result.output
