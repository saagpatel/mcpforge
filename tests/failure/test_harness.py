"""All failure modes are exercised by the three generated server handlers."""

import asyncio
import importlib.util
import json
import shutil
import subprocess
import sys

import pytest
from fastmcp import Client

from mcpforge.contracts import FailureContract
from mcpforge.failure.codegen import generate_server
from mcpforge.failure.fixtures import load_upstreams, run_all_fixtures
from mcpforge.models import ServerPlan, ToolDef

SERVER_TYPES = ("python-single", "python-multi", "typescript")


def test_harness_node_is_required_for_typescript():
    if shutil.which("node") is None:
        pytest.fail("Node.js 22.6+ is required to run the TypeScript failure harness")


@pytest.mark.parametrize("server_type", SERVER_TYPES)
def test_harness_matches_expected_for_all_upstreams(server_type):
    outcomes = run_all_fixtures(server_type)
    assert len(outcomes) == 15
    assert {name: result for name, result in outcomes.items()} == {
        upstream["name"]: upstream["expect"] for upstream in load_upstreams()
    }


@pytest.mark.parametrize("mode", ("timeout", "malformed", "cancellation"))
def test_harness_mode_cases(mode):
    from mcpforge.failure.fixtures import run_python_fixture

    for upstream in load_upstreams():
        if upstream["mode"] == mode:
            assert run_python_fixture(upstream) == upstream["expect"]


def test_consistency_across_server_types():
    normalized = {server_type: run_all_fixtures(server_type) for server_type in SERVER_TYPES}
    assert normalized["python-single"] == normalized["python-multi"]
    assert normalized["python-single"] == normalized["typescript"]
    serialized = {
        server_type: json.dumps(results, sort_keys=True, separators=(",", ":"))
        for server_type, results in normalized.items()
    }
    assert len(set(serialized.values())) == 1


@pytest.mark.parametrize("server_type", ("python-single", "python-multi"))
def test_generated_python_mcp_tool_error_signalling(tmp_path, server_type):
    plan = ServerPlan(
        name="Tool Result Fixture",
        description="Test MCP outcome signalling.",
        tools=[
            ToolDef(
                name="fixture_tool",
                description="Return fixture output.",
                params=[],
                failure_contract=FailureContract(retryable=True, partial_result_allowed=True),
            )
        ],
    )
    output = generate_server(plan, tmp_path / server_type, server_type)
    sys.path.insert(0, str(output))
    try:
        spec = importlib.util.spec_from_file_location(
            f"generated_{server_type.replace('-', '_')}", output / "server.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        failed_upstream = {
            "response_schema": {"type": "object", "required": ["id"]},
            "script": [{"emit": {"other": 1}}],
        }
        incomplete_upstream = {
            "response_schema": {"type": "object", "required": ["id"]},
            "script": [{"emit": {"id": 1}}, {"emit": {"other": 2}}],
        }

        async def call_tools():
            async with Client(module.mcp) as client:
                incomplete_result = await client.call_tool(
                    "fixture_tool", {"operation": incomplete_upstream}, raise_on_error=False
                )
                failed_result = await client.call_tool(
                    "fixture_tool", {"operation": failed_upstream}, raise_on_error=False
                )
                return incomplete_result, failed_result

        incomplete, failed = asyncio.run(call_tools())
    finally:
        sys.path.remove(str(output))

    assert incomplete.is_error is False
    assert incomplete.structured_content["status"] == "incomplete"
    assert incomplete.structured_content["items"] == [{"id": 1}]
    assert failed.is_error is True
    assert failed.structured_content["status"] == "failed"
    assert failed.structured_content["items"] == []


def test_typescript_mcp_tool_mapping(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js 22.6+ is required to test TypeScript tool result mapping")
    plan = ServerPlan(
        name="Tool Result Fixture",
        description="Test MCP outcome signalling.",
        tools=[
            ToolDef(
                name="fixture_tool",
                description="Return fixture output.",
                params=[],
                failure_contract=FailureContract(retryable=True, partial_result_allowed=True),
            )
        ],
    )
    output = generate_server(plan, tmp_path, "typescript")
    server = output / "server.ts"
    source = (
        f"import {{ MCP_TOOL_HANDLERS }} from {json.dumps(server.as_uri())};\n"
        "const failed = await MCP_TOOL_HANDLERS.fixture_tool({response_schema: "
        "{type:'object',required:['id']},script:[{emit:{other:2}}]});\n"
        "const incomplete = await MCP_TOOL_HANDLERS.fixture_tool({response_schema: "
        "{type:'object',required:['id']},script:[{emit:{id:1}},{emit:{other:2}}]});\n"
        "process.stdout.write(JSON.stringify([failed,incomplete]));\n"
    )
    completed = subprocess.run(
        [node, "--input-type=module", "-e", source],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    failed, incomplete = json.loads(completed.stdout)
    assert failed["isError"] is True
    assert failed["structuredContent"]["status"] == "failed"
    assert json.loads(failed["content"][0]["text"]) == failed["structuredContent"]
    assert incomplete["isError"] is False
    assert incomplete["structuredContent"]["status"] == "incomplete"
