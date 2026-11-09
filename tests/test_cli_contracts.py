"""Additive contract CLI commands preserve and verify the contract surfaces."""

import importlib
import json

from click.testing import CliRunner

from mcpforge.cli import cli


def test_root_help_keeps_existing_commands_and_adds_contracts():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for command in (
        "generate",
        "validate",
        "update",
        "demo",
        "version",
        "list",
        "inspect",
        "doctor",
        "init",
        "contracts",
    ):
        assert command in result.output


def test_contracts_help_lists_new_commands():
    result = CliRunner().invoke(cli, ["contracts", "--help"])
    assert result.exit_code == 0
    commands = result.output.split("Commands:\n", 1)[1]
    assert {line.split()[0] for line in commands.splitlines() if line.strip()} == {
        "pagination-docs",
        "failure-docs",
        "fixtures",
    }


def test_pagination_docs_check_passes():
    result = CliRunner().invoke(cli, ["contracts", "pagination-docs", "--check"])
    assert result.exit_code == 0, result.output
    assert "pagination docs match" in result.output


def test_pagination_docs_out_generates_then_detects_stale_files(tmp_path):
    runner = CliRunner()
    out = tmp_path / "pagination-docs"
    generated = runner.invoke(cli, ["contracts", "pagination-docs", "--path", str(out)])
    assert generated.exit_code == 0, generated.output
    checked = runner.invoke(cli, ["contracts", "pagination-docs", "--path", str(out), "--check"])
    assert checked.exit_code == 0, checked.output
    target = out / "cursor.md"
    original = target.read_text()
    target.write_text(original + "\nstale\n")
    stale = runner.invoke(cli, ["contracts", "pagination-docs", "--path", str(out), "--check"])
    assert stale.exit_code != 0
    assert "pagination docs differ" in stale.output


def test_failure_docs_check_passes():
    result = CliRunner().invoke(cli, ["contracts", "failure-docs", "--check"])
    assert result.exit_code == 0, result.output
    assert "failure docs match" in result.output


def test_failure_docs_stale_check_does_not_write(tmp_path):
    target = tmp_path / "FAILURE-SEMANTICS.md"
    real_docs = importlib.import_module("mcpforge.failure.docs")
    real_target = real_docs.Path(__file__).resolve().parents[1] / "docs" / "FAILURE-SEMANTICS.md"
    stale_content = real_target.read_text().replace('"status": "failed"', '"status": "stale"', 1)
    target.write_text(stale_content)
    result = CliRunner().invoke(
        cli, ["contracts", "failure-docs", "--path", str(target), "--check"]
    )
    assert result.exit_code != 0
    assert target.read_text() == stale_content


def test_missing_default_docs_check_reports_error_without_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for command in ("pagination-docs", "failure-docs"):
        result = CliRunner().invoke(cli, ["contracts", command, "--check"])
        assert result.exit_code != 0
        assert "docs" in result.output
        assert "Traceback" not in result.output
    assert not (tmp_path / "docs").exists()


def test_fixtures_json_summary_and_mismatch_exit(monkeypatch):
    fixture_runtime = importlib.import_module("mcpforge.failure.fixtures")
    pagination_datasets = importlib.import_module("mcpforge.pagination.datasets")
    monkeypatch.setattr(fixture_runtime, "SERVER_TYPES", ("python-single",))
    monkeypatch.setattr(fixture_runtime, "load_upstreams", lambda: [{"name": "synthetic"}])
    monkeypatch.setattr(fixture_runtime, "run_fixture", lambda *args: {"status": "complete"})
    monkeypatch.setattr(fixture_runtime, "assert_expected", lambda *args: None)
    monkeypatch.setattr(pagination_datasets, "load_datasets", lambda: [])

    success = CliRunner().invoke(cli, ["contracts", "fixtures", "--json"])
    assert success.exit_code == 0, success.output
    summary = json.loads(success.output)
    assert summary["pagination"] == {"matched": 0, "total": 0}
    assert summary["failure"] == {
        "matched": 1,
        "total": 1,
        "server_types": ["python-single"],
    }

    monkeypatch.setattr(
        fixture_runtime,
        "assert_expected",
        lambda *args: (_ for _ in ()).throw(AssertionError("synthetic mismatch")),
    )
    mismatch = CliRunner().invoke(cli, ["contracts", "fixtures", "--json"])
    assert mismatch.exit_code != 0
    assert "synthetic mismatch" in mismatch.output
