"""The published examples are regenerated from the runtime."""

from pathlib import Path

from mcpforge.failure.docs import (
    failure_readme_section,
    marked_example,
    render_examples,
    replace_marked_examples,
)

ROOT = Path(__file__).resolve().parents[2]


def test_docs_examples_match_runtime_output_byte_for_byte():
    docs = ROOT / "docs" / "FAILURE-SEMANTICS.md"
    actual = docs.read_text(encoding="utf-8")
    assert replace_marked_examples(actual) == actual
    examples = render_examples()
    assert examples
    assert all(marked_example(name, output) in actual for name, output in examples.items())


def test_generated_readme_section_uses_runtime_examples():
    section = failure_readme_section()
    examples = render_examples()
    assert all(marked_example(name, output) in section for name, output in examples.items())
