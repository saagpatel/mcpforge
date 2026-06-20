"""Tests for the offline demo: replay client, cassette, and the demo command."""

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from mcpforge.cli import _run_generate, cli
from mcpforge.demo import build_weather_plan, load_demo_client
from mcpforge.models import ServerPlan
from mcpforge.replay_client import ReplayClient

_EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "weather-server"


class StructuredSmoke(ServerPlan):
    """A distinct ServerPlan subclass to test response_model type checking."""


class TestReplayClient:
    async def test_generate_returns_recorded_responses_in_order(self):
        client = ReplayClient(build_weather_plan(), ["first", "second"])
        assert await client.generate("s", "u") == "first"
        assert await client.generate("s", "u") == "second"

    async def test_generate_raises_when_recording_exhausted(self):
        client = ReplayClient(build_weather_plan(), ["only"])
        await client.generate("s", "u")
        with pytest.raises(RuntimeError, match="ran out of recorded"):
            await client.generate("s", "u")

    async def test_generate_json_returns_recorded_plan(self):
        plan = build_weather_plan()
        client = ReplayClient(plan, [])
        result = await client.generate_json("s", "u", ServerPlan)
        assert result is plan

    async def test_generate_json_rejects_model_mismatch(self):
        client = ReplayClient(build_weather_plan(), [])
        with pytest.raises(TypeError, match="ReplayClient recorded"):
            await client.generate_json("s", "u", StructuredSmoke)

    async def test_generate_stream_is_not_supported(self):
        client = ReplayClient(build_weather_plan(), [])
        with pytest.raises(NotImplementedError):
            async for _ in client.generate_stream("s", "u"):
                pass


class TestCassette:
    def test_plan_tools_match_recorded_server(self):
        """The recorded plan's tools must match the packaged cassette (conformance)."""
        from mcpforge.demo import _load_cassette_source

        plan = build_weather_plan()
        server_code = _load_cassette_source("server.py")
        for tool in plan.tools:
            assert f"def {tool.name}(" in server_code
        assert plan.slug == "weather-server"
        assert plan.env_vars == ["OPENWEATHER_API_KEY"]

    def test_packaged_cassette_matches_examples(self):
        """The packaged cassette must stay in sync with examples/weather-server."""
        from mcpforge.demo import _load_cassette_source

        for name in ("server.py", "test_server.py"):
            packaged = _load_cassette_source(name)
            source = (_EXAMPLES / name).read_text(encoding="utf-8")
            assert packaged == source, f"demo_assets/{name} drifted from examples/weather-server"

    def test_load_demo_client_serves_server_then_tests(self):
        client = load_demo_client()
        assert isinstance(client, ReplayClient)
        # Responses replay in pipeline order: server code, then tests.
        assert "FastMCP(" in client._generate_responses[0]
        assert "def test_" in client._generate_responses[1]


class TestDemoCommand:
    def test_demo_invokes_pipeline_with_demo_provider(self):
        async def _noop(*args, **kwargs):
            return None

        with patch("mcpforge.cli._run_generate", side_effect=_noop) as mock_run:
            result = CliRunner().invoke(cli, ["demo", "-o", "out-dir"])

        assert result.exit_code == 0, result.output
        # Bind to the real signature so the assertions survive parameter reordering.
        bound = inspect.signature(_run_generate).bind(
            *mock_run.call_args.args, **mock_run.call_args.kwargs
        )
        assert bound.arguments["output"] == "out-dir"
        assert bound.arguments["provider"] == "demo"
        assert bound.arguments["yes"] is True  # no confirmation prompt
