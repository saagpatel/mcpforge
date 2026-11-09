"""Generate pattern documentation from adapter definitions and real traversals."""

from __future__ import annotations

import json
from pathlib import Path

from mcpforge.contracts import FailureContract
from mcpforge.pagination.datasets import load_datasets
from mcpforge.pagination.harness import MutatingUpstream
from mcpforge.pagination.patterns import DEFINITIONS
from mcpforge.pagination.traverse import traverse

ROOT = Path(__file__).parents[3]
DOCS_DIR = ROOT / "docs" / "pagination"
CONTRACT = FailureContract(retryable=True, partial_result_allowed=True)


def _scenario(pattern: str, category: str):
    datasets = [dataset for dataset in load_datasets() if dataset.pattern == pattern]
    if category == "stable":
        selected = next(d for d in datasets if d.id.endswith("-stable"))
    elif category == "recovery":
        selected = next(
            d for d in datasets if d.mutations and d.expect == "complete" and "insert" in d.id
        )
    else:
        selected = next(d for d in datasets if d.expect != "complete")
    source = MutatingUpstream(selected.items, selected.mutations)
    result = traverse(source.adapter(pattern, selected.page_size), CONTRACT, 100)
    return selected, result


def _outcome_json(result) -> str:
    payload = {
        "items": result.items,
        "outcome": result.outcome.model_dump(mode="json", exclude_none=False),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _marked_example(name: str, rendered: str) -> str:
    return (
        f"<!-- pagination-example:{name}:start -->\n"
        f"```json\n{rendered}\n```\n"
        f"<!-- pagination-example:{name}:end -->"
    )


def render_pattern_doc(definition) -> str:
    """Render one pattern reference and examples from the mutating harness."""
    rows = [
        f"# {definition.pattern} pagination",
        "",
        "## Adapter contract",
        "",
        f"- Cursor validity: {definition.cursor_validity_rule}",
        f"- Ordering guarantee: {definition.ordering_guarantee}",
        f"- Resume behaviour: {definition.resume_behaviour}",
        f"- Incompleteness detection: {definition.incompleteness_detection}",
        f"- Contract defaults: {definition.contract_defaults}",
        "",
        "## Observed behaviour",
        "",
    ]
    for category, title in (
        ("stable", "Stable traversal"),
        ("recovery", "Mutation that recovers"),
        ("incomplete", "Mutation that ends incomplete"),
    ):
        dataset, result = _scenario(definition.pattern, category)
        name = f"{definition.pattern}-{category}"
        rows.extend(
            [
                f"### {title} (`{dataset.id}`)",
                "",
                _marked_example(name, _outcome_json(result)),
                "",
            ]
        )
    return "\n".join(rows).rstrip() + "\n"


def render_docs() -> dict[str, str]:
    """Return all pattern documents and the index as relative path/content."""
    docs = {f"{d.pattern}.md": render_pattern_doc(d) for d in DEFINITIONS}
    links = "\n".join(f"- [{d.pattern}]({d.pattern}.md)" for d in DEFINITIONS)
    docs["README.md"] = (
        "# Pagination contracts\n\n"
        "Pagination incompleteness is a case of the shared failure contract; see "
        "[Failure Semantics](../FAILURE-SEMANTICS.md).\n\n"
        "The protocol-level claims below apply to MCP list methods: `resources/list`, "
        "`tools/list`, `prompts/list`, and `resources/templates/list`. Tool-level claims "
        "describe upstream traversal performed by `list_records`; tool calls do not "
        "inherit MCP list-method pagination semantics.\n\n"
        "The example servers use FastMCP's native `resources/list` pagination and "
        "wrap its continuation state in the pagination HMAC cursor codec. Their "
        "`list_records` tools traverse the bundled synthetic upstream and return an "
        "outcome envelope; absence of `nextCursor` marks tool traversal exhaustion.\n\n"
        "Installed-server protocol conformance tests cover `resources/list`; these "
        "examples make no conformance claim for the other list methods.\n\n"
        "Offset shift detection is bounded: it is guaranteed only when the change "
        "affects an overlap boundary the adapter can observe.\n\n"
        "## Pattern references\n\n"
        f"{links}\n"
    )
    return docs


def write_docs(output_dir: str | Path = DOCS_DIR) -> list[Path]:
    """Write all generated documents and return their paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in render_docs().items():
        path = out / name
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(path)
    return written
