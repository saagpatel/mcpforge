"""Generate documentation examples from the failure runtime fixtures."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastmcp import Client

from mcpforge.contracts import FailureContract
from mcpforge.failure.codegen import _write_python_single
from mcpforge.failure.fixtures import load_upstreams, run_python_fixture
from mcpforge.models import ServerPlan, ToolDef

EXAMPLE_NAMES = (
    "timeout_before_first",
    "malformed_invalid_json",
    "cancellation_before_data",
    "timeout_after_partial",
)
TOOL_RESULT_NAMES = ("failed_tool_result", "incomplete_tool_result")


def _run_async(coroutine):
    """Run documentation probes whether or not the caller already has a loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()


def _render_tool_results() -> dict[str, str]:
    """Capture serialized FastMCP results from the generated Python server."""
    plan = ServerPlan(
        name="Failure Documentation Fixture",
        description="Generated handlers used to capture MCP result signalling.",
        tools=[
            ToolDef(
                name="fixture_tool",
                description="Run a synthetic failure fixture.",
                params=[],
                failure_contract=FailureContract(retryable=True, partial_result_allowed=True),
            )
        ],
    )
    valid_then_malformed = {
        "response_schema": {"type": "object", "required": ["id"]},
        "script": [{"emit": {"id": 1}}, {"emit": {"other": 2}}],
    }
    malformed_before_data = {
        "response_schema": {"type": "object", "required": ["id"]},
        "script": [{"emit": {"other": 2}}],
    }
    with tempfile.TemporaryDirectory(prefix="mcpforge-failure-docs-") as temporary:
        output = Path(temporary)
        _write_python_single(plan, output)
        spec = importlib.util.spec_from_file_location(
            "mcpforge_failure_docs_server", output / "server.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("could not load generated failure documentation server")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        async def call_tools():
            async with Client(module.mcp) as client:
                failed = await client.call_tool(
                    "fixture_tool", {"upstream": malformed_before_data}, raise_on_error=False
                )
                incomplete = await client.call_tool(
                    "fixture_tool", {"upstream": valid_then_malformed}, raise_on_error=False
                )
            return failed, incomplete

        failed, incomplete = _run_async(call_tools())
        results = {"failed_tool_result": failed, "incomplete_tool_result": incomplete}
        return {
            name: json.dumps(
                {
                    "content": [
                        {"type": block.type, "text": block.text} for block in result.content
                    ],
                    "structuredContent": result.structured_content,
                    "isError": result.is_error,
                },
                indent=2,
                sort_keys=True,
            )
            for name, result in results.items()
        }


def render_examples() -> dict[str, str]:
    """Return normalized runtime and generated MCP-result examples."""
    by_name = {item["name"]: item for item in load_upstreams()}
    missing = set(EXAMPLE_NAMES) - by_name.keys()
    if missing:
        raise ValueError(f"failure documentation fixtures missing: {sorted(missing)}")
    examples = {
        name: json.dumps(run_python_fixture(by_name[name]), indent=2, sort_keys=True)
        for name in EXAMPLE_NAMES
    }
    examples.update(_render_tool_results())
    return examples


def marked_example(name: str, rendered_json: str) -> str:
    """Build a stable marked Markdown block for one example."""
    return (
        f"<!-- failure-example:{name}:start -->\n"
        f"```json\n{rendered_json}\n```\n"
        f"<!-- failure-example:{name}:end -->"
    )


def replace_marked_examples(document: str) -> str:
    """Replace existing marked blocks with fresh runtime output."""
    updated = document
    for name, rendered in render_examples().items():
        block = marked_example(name, rendered)
        start = f"<!-- failure-example:{name}:start -->"
        end = f"<!-- failure-example:{name}:end -->"
        start_at = updated.find(start)
        end_at = updated.find(end, start_at + len(start)) if start_at >= 0 else -1
        if start_at < 0 or end_at < 0:
            raise ValueError(f"documentation is missing marked example {name}")
        updated = updated[:start_at] + block + updated[end_at + len(end) :]
    return updated


def failure_readme_section() -> str:
    """Return the generated README section, including real marked examples."""
    chunks = [
        "## Failure semantics",
        "",
        "Tool handlers return a normalized outcome envelope. The effective per-tool "
        "retry and partial-result permissions are in `failure_contracts.json`.",
        "",
        "MCP tool-result examples below are captured by calling the generated Python "
        "server through FastMCP. Failed envelopes set `isError`; incomplete envelopes "
        "remain normal results and retain their partial items.",
        "",
    ]
    chunks.extend(marked_example(name, rendered) for name, rendered in render_examples().items())
    return "\n".join(chunks) + "\n"


def regenerate_failure_docs(path: str | Path | None = None) -> Path:
    """Refresh marked blocks in the committed failure-semantics document."""
    target = (
        Path(path)
        if path is not None
        else Path(__file__).parents[3] / "docs" / "FAILURE-SEMANTICS.md"
    )
    target.write_text(replace_marked_examples(target.read_text()), encoding="utf-8")
    return target
