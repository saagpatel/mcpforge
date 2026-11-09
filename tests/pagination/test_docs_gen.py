"""Pagination documents are generated from the live adapters and harness."""

import json
import re
from pathlib import Path

from mcpforge.contracts import FailureContract
from mcpforge.pagination.datasets import load_datasets
from mcpforge.pagination.docs_gen import DOCS_DIR, render_docs, write_docs
from mcpforge.pagination.harness import MutatingUpstream
from mcpforge.pagination.patterns import DEFINITIONS
from mcpforge.pagination.traverse import traverse


def test_committed_docs_match_generator(tmp_path: Path):
    write_docs(tmp_path)
    for name, content in render_docs().items():
        assert (tmp_path / name).read_bytes() == content.encode("utf-8")
        assert (DOCS_DIR / name).read_bytes() == content.encode("utf-8")


def test_document_guarantees_match_adapter_behaviour():
    docs = render_docs()
    by_pattern = {d.pattern: d for d in DEFINITIONS}
    for pattern, definition in by_pattern.items():
        document = docs[f"{pattern}.md"]
        for guarantee in (
            definition.cursor_validity_rule,
            definition.ordering_guarantee,
            definition.resume_behaviour,
            definition.incompleteness_detection,
            definition.contract_defaults,
        ):
            assert guarantee in document
        for category, expected_status in (
            ("stable", "complete"),
            ("recovery", "complete"),
            ("incomplete", "incomplete"),
        ):
            name = f"{pattern}-{category}"
            match = re.search(
                rf"<!-- pagination-example:{name}:start -->\n```json\n(.*?)\n```",
                document,
                re.DOTALL,
            )
            assert match is not None
            assert json.loads(match.group(1))["outcome"]["status"] == expected_status

    offset = next(d for d in load_datasets() if d.id == "12-offset-delete-before-cursor")
    result = traverse(
        MutatingUpstream(offset.items, offset.mutations).adapter("offset", offset.page_size),
        FailureContract(retryable=True, partial_result_allowed=True),
        100,
    )
    assert result.outcome.status == "incomplete"
    assert result.outcome.failure.kind == "page_shifted"
    assert "observable overlap boundary" in docs["offset.md"]


def test_index_explains_protocol_and_tool_claims():
    index = render_docs()["README.md"]
    assert "resources/list" in index
    assert "tools/call" not in index or "tool calls do not" in index
    assert "FAILURE-SEMANTICS.md" in index
    assert "overlap boundary" in index
