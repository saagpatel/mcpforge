"""Generate pagination documentation from adapter definitions and harness runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcpforge.contracts import FailureContract
from mcpforge.pagination.datasets import load_datasets
from mcpforge.pagination.harness import MutatingUpstream
from mcpforge.pagination.patterns import DEFINITIONS
from mcpforge.pagination.traverse import TraversalResult, traverse

DOCS_DIR = Path("docs/pagination")
CONTRACT = FailureContract(retryable=True, partial_result_allowed=True)
_CURSOR_PLACEHOLDER = "<opaque session cursor omitted>"


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


def _outcome_json(result: TraversalResult) -> str:
    """Serialize observed results while making random session cursors reproducible."""
    payload: dict[str, Any] = {
        "items": result.items,
        "outcome": result.outcome.model_dump(mode="json", exclude_none=False),
    }
    if payload["outcome"]["failure"] is not None:
        failure = payload["outcome"]["failure"]
        if failure["resume_cursor"] is not None:
            failure["resume_cursor"] = _CURSOR_PLACEHOLDER
    return json.dumps(payload, indent=2, sort_keys=True)


def _marked_example(name: str, rendered: str) -> str:
    return (
        f"<!-- pagination-example:{name}:start -->\n"
        f"```json\n{rendered}\n```\n"
        f"<!-- pagination-example:{name}:end -->"
    )


def render_pattern_doc(definition) -> str:
    """Render one pattern contract and examples from the mutating harness."""
    rows = [
        f"# {definition.pattern} pagination",
        "",
        "## Adapter contract",
        "",
        f"- Cursor validity: {definition.cursor_validity_rule}",
        f"- Ordering guarantee: {definition.ordering_guarantee}",
        f"- Resume behaviour: {definition.resume_behaviour}",
        f"- Incompleteness detection: {definition.incompleteness_detection}",
        "",
        "## Observed behaviour",
        "",
        "These blocks come from the deterministic synthetic upstream harness. "
        "Opaque session cursors are replaced by a placeholder so regeneration is byte-stable.",
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
    """Return all pattern documents and the index as filename/content pairs."""
    docs = {f"{d.pattern}.md": render_pattern_doc(d) for d in DEFINITIONS}
    links = "\n".join(f"- [{d.pattern}]({d.pattern}.md)" for d in DEFINITIONS)
    docs["README.md"] = (
        "# Pagination contracts\n\n"
        "Pagination incompleteness is part of the shared failure contract; see "
        "[Failure Semantics](../FAILURE-SEMANTICS.md).\n\n"
        "The protocol-level claims here concern MCP list methods: `resources/list`, "
        "`tools/list`, `prompts/list`, and `resources/templates/list`.\n\n"
        "Tool-level claims concern upstream traversal performed by `list_records`; "
        "tool calls do not inherit MCP list-method pagination semantics. The tools "
        "return a shared outcome envelope.\n\n"
        "The adapter authenticates opaque cursors and binds them to a collection, "
        "effective query, configuration, and traversal id. `TraversalHistory` is "
        "process-local and bounded by default to 128 traversals and 10,000 emitted "
        "identities per traversal. LRU eviction, identity-bound exhaustion, or a "
        "process restart that loses history while retaining the signing key makes "
        "continuation fail with `page_shifted`. A fresh process signing key makes an "
        "old cursor invalid and returns JSON-RPC `-32602`. Neither case resumes the "
        "old traversal: begin a new traversal and do not append its results to an "
        "earlier partial result. Retaining the codec key alone does not restore "
        "traversal history.\n\n"
        "Offset shift detection is bounded: it can detect a change when the adapter "
        "observes a missing or changed overlap boundary. Changes outside that "
        "observable boundary are not guaranteed to be detected.\n\n"
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
