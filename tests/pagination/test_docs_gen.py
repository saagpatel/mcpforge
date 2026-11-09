"""Pagination documents stay aligned with adapter contracts and harness output."""

import json
import re
from pathlib import Path

from mcpforge.pagination.docs_gen import DOCS_DIR, render_docs, write_docs
from mcpforge.pagination.patterns import DEFINITIONS


def test_committed_docs_match_generator(tmp_path: Path):
    write_docs(tmp_path)
    for name, content in render_docs().items():
        expected = content.encode("utf-8")
        assert (tmp_path / name).read_bytes() == expected
        assert (DOCS_DIR / name).read_bytes() == expected


def test_pattern_docs_include_current_contract_and_observed_results():
    docs = render_docs()
    for definition in DEFINITIONS:
        document = docs[f"{definition.pattern}.md"]
        for guarantee in (
            definition.cursor_validity_rule,
            definition.ordering_guarantee,
            definition.resume_behaviour,
            definition.incompleteness_detection,
        ):
            assert guarantee in document

        for category, status in (
            ("stable", "complete"),
            ("recovery", "complete"),
            ("incomplete", "incomplete"),
        ):
            name = f"{definition.pattern}-{category}"
            match = re.search(
                rf"<!-- pagination-example:{name}:start -->\n```json\n(.*?)\n```",
                document,
                re.DOTALL,
            )
            assert match is not None
            payload = json.loads(match.group(1))
            assert payload["outcome"]["status"] == status
            failure = payload["outcome"]["failure"]
            if failure is not None and failure["resume_cursor"] is not None:
                assert failure["resume_cursor"] == "<opaque session cursor omitted>"


def test_index_documents_claim_boundaries_and_restart_rules():
    index = render_docs()["README.md"]
    assert "resources/list" in index
    assert "tool calls do not inherit MCP list-method pagination semantics" in index
    assert "128 traversals" in index
    assert "10,000 emitted identities per traversal" in index
    assert "process restart that loses history while retaining the signing key" in index
    assert "fresh process signing key" in index
    assert "JSON-RPC `-32602`" in index
    assert "do not append its results to an earlier partial result" in index
    assert "observable boundary" in index
    assert "FAILURE-SEMANTICS.md" in index
