"""Generate documentation examples from the failure runtime fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from mcpforge.failure.fixtures import load_upstreams, run_python_fixture

EXAMPLE_NAMES = (
    "timeout_before_first",
    "malformed_invalid_json",
    "cancellation_before_data",
    "timeout_after_partial",
)


def render_examples() -> dict[str, str]:
    """Return fixture names mapped to their actual normalized runtime JSON."""
    by_name = {item["name"]: item for item in load_upstreams()}
    missing = set(EXAMPLE_NAMES) - by_name.keys()
    if missing:
        raise ValueError(f"failure documentation fixtures missing: {sorted(missing)}")
    return {
        name: json.dumps(run_python_fixture(by_name[name]), indent=2, sort_keys=True)
        for name in EXAMPLE_NAMES
    }


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
