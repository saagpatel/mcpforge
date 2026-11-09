"""Generated artifacts are deterministic and independent of a forge install."""

import json

import pytest

from mcpforge.pagination.examples_gen import EXAMPLES_DIR, generate_example, render_example
from mcpforge.pagination.patterns import DEFINITIONS


@pytest.mark.parametrize("definition", DEFINITIONS, ids=lambda d: d.pattern)
def test_examples_regeneration_is_byte_identical(definition, tmp_path):
    generated = generate_example(definition.pattern, tmp_path / "server")
    expected = render_example(definition.pattern)
    committed = EXAMPLES_DIR / f"{definition.pattern}-server"
    actual_paths = {
        p.relative_to(committed).as_posix()
        for p in committed.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts
    }
    assert actual_paths == expected.keys()
    for name in expected:
        assert (generated / name).read_bytes() == (committed / name).read_bytes(), name
    for path in (generated / "src").rglob("*.py"):
        assert "mcpforge" not in path.read_text(), path
    metadata = (generated / "pyproject.toml").read_text()
    assert 'build-backend = "uv_build"' in metadata
    dataset = json.loads(next((generated / "src").rglob("dataset.json")).read_text())
    assert dataset["pattern"] == definition.pattern


def test_unknown_pattern_writes_nothing(tmp_path):
    target = tmp_path / "unknown"
    with pytest.raises(ValueError, match="unsupported"):
        generate_example("unknown", target)
    assert not target.exists()


def test_generator_preserves_existing_unrelated_files(tmp_path):
    foreign = tmp_path / "keep.txt"
    foreign.write_text("keep")
    generate_example("cursor", tmp_path)
    assert foreign.read_text() == "keep"
