"""Generate documentation examples from the failure runtime fixtures."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from mcpforge.failure.fixtures import load_upstreams, run_python_fixture

EXAMPLE_NAMES = (
    "failed_tool_result",
    "incomplete_tool_result",
    "timeout_before_first",
    "malformed_invalid_json",
    "cancellation_before_data",
    "timeout_after_partial",
)


def render_examples() -> dict[str, str]:
    """Return normalized runtime outcomes and FastMCP wire results as JSON."""
    by_name = {item["name"]: item for item in load_upstreams()}
    fixture_names = tuple(
        name
        for name in EXAMPLE_NAMES
        if name
        not in {
            "failed_tool_result",
            "incomplete_tool_result",
        }
    )
    missing = set(fixture_names) - by_name.keys()
    if missing:
        raise ValueError(f"failure documentation fixtures missing: {sorted(missing)}")
    examples = {
        name: json.dumps(run_python_fixture(by_name[name]), indent=2, sort_keys=True)
        for name in fixture_names
    }
    from fastmcp.tools import ToolResult
    from mcp.types import CallToolResult

    def render_tool_result(outcome: dict) -> str:
        result = ToolResult(
            content=outcome,
            structured_content=outcome,
            is_error=outcome["status"] == "failed",
        ).to_mcp_result()
        if isinstance(result, tuple):
            result = CallToolResult(content=result[0], structuredContent=result[1])
        wire_result = result.model_dump(by_alias=True, exclude_none=True)
        return json.dumps(wire_result, indent=2, sort_keys=True)

    failed = json.loads(examples["malformed_invalid_json"])
    incomplete = json.loads(examples["timeout_after_partial"])
    examples["failed_tool_result"] = render_tool_result(failed)
    examples["incomplete_tool_result"] = render_tool_result(incomplete)
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
        "Generated MCP adapters preserve the envelope as structured content, set "
        "`isError` for `failed` outcomes, and leave `incomplete` outcomes as normal "
        "tool results.",
        "",
    ]
    chunks.extend(marked_example(name, rendered) for name, rendered in render_examples().items())
    return "\n".join(chunks) + "\n"


def failure_docs_template() -> str:
    """Load the packaged starting document for a new output path."""
    return files("mcpforge.failure").joinpath("FAILURE-SEMANTICS.md").read_text(encoding="utf-8")


def regenerate_failure_docs(path: str | Path | None = None) -> Path:
    """Refresh marked blocks in the committed failure-semantics document."""
    target = Path(path) if path is not None else Path("docs/FAILURE-SEMANTICS.md")
    current = target.read_text(encoding="utf-8") if target.exists() else failure_docs_template()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(replace_marked_examples(current), encoding="utf-8")
    return target
