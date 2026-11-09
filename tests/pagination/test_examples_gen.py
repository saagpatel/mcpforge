"""Generated examples remain reproducible and usable through the CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from mcpforge.cli import cli
from mcpforge.pagination.examples_gen import (
    COMMITTED_EXAMPLE_PATTERNS,
    generate_example,
    render_example,
)

EXAMPLES_DIR = Path(__file__).parents[2] / "examples" / "pagination"


@pytest.mark.parametrize("pattern", COMMITTED_EXAMPLE_PATTERNS)
def test_examples_regeneration_is_byte_identical(pattern, tmp_path):
    generated = generate_example(pattern, tmp_path / "server")
    expected = render_example(pattern)
    committed = EXAMPLES_DIR / f"{pattern}-server"
    actual_paths = {
        path.relative_to(committed).as_posix()
        for path in committed.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts
    }
    assert actual_paths == expected.keys()
    for name in expected:
        assert (generated / name).read_bytes() == (committed / name).read_bytes(), name
    for path in (generated / "src").rglob("*.py"):
        assert "mcpforge" not in path.read_text(), path
    metadata = (generated / "pyproject.toml").read_text()
    assert 'build-backend = "uv_build"' in metadata
    assert 'dependencies = ["fastmcp>=' in metadata
    assert "mcpforge" not in metadata
    dataset = json.loads(next((generated / "src").rglob("dataset.json")).read_text())
    assert dataset["pattern"] == pattern


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


@pytest.mark.parametrize("pattern", ["cursor", "offset", "page_token"])
def test_pagination_example_cli_generates_the_selected_project(pattern, tmp_path):
    output = tmp_path / "generated"
    result = CliRunner().invoke(
        cli, ["contracts", "pagination-example", pattern, "--output", str(output)]
    )
    assert result.exit_code == 0, result.output
    assert f"wrote {pattern} pagination example" in result.output
    for name, content in render_example(pattern).items():
        assert (output / name).read_bytes() == content.encode("utf-8")


@pytest.mark.parametrize("pattern", ["offset", "page_token"])
def test_uncommitted_examples_import(pattern, tmp_path):
    output = generate_example(pattern, tmp_path / pattern)
    test_file = str(output / "tests/test_server.py")
    script = (
        "import importlib.util, sys; "
        f"sys.path.insert(0, {str(output / 'src')!r}); "
        f"import pagination_{pattern}.server; "
        f"spec = importlib.util.spec_from_file_location('generated_test', {test_file!r}); "
        "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_cli_refuses_nonempty_directory_unless_forced(tmp_path):
    foreign = tmp_path / "keep.txt"
    foreign.write_text("keep")
    runner = CliRunner()
    args = ["contracts", "pagination-example", "cursor", "--output", str(tmp_path)]
    refused = runner.invoke(cli, args)
    assert refused.exit_code != 0
    assert "not empty" in refused.output
    assert list(tmp_path.iterdir()) == [foreign]
    forced = runner.invoke(cli, [*args, "--force"])
    assert forced.exit_code == 0, forced.output
    assert foreign.read_text() == "keep"
