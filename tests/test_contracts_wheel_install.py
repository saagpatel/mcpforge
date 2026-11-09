"""Exercise contract documentation commands from an installed wheel."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


@pytest.mark.examples_install
def test_contract_docs_from_isolated_wheel(tmp_path: Path):
    dist = tmp_path / "dist"
    constraints = tmp_path / "constraints.txt"
    venv = tmp_path / "venv"
    work = tmp_path / "work"
    work.mkdir()
    run("uv", "build", "--wheel", "--out-dir", str(dist))
    run(
        "uv",
        "export",
        "--locked",
        "--no-dev",
        "--no-emit-project",
        "--no-hashes",
        "--output-file",
        str(constraints),
    )
    run("uv", "venv", str(venv), "--python", sys.executable)
    wheel = next(dist.glob("*.whl"))
    install = [
        "uv",
        "pip",
        "install",
        "--python",
        str(venv / "bin/python"),
        "--constraint",
        str(constraints),
        str(wheel),
    ]
    try:
        run(*install, "--offline")
    except subprocess.CalledProcessError:
        run(*install)  # One retry permits a cold dependency cache.

    executable = str(venv / "bin/mcpforge")
    for command in ("pagination-docs", "failure-docs"):
        missing = subprocess.run(
            [executable, "contracts", command, "--check"],
            cwd=work,
            text=True,
            capture_output=True,
        )
        assert missing.returncode != 0
        assert "docs" in missing.stderr
        assert "Traceback" not in missing.stderr
        run(executable, "contracts", command, cwd=work)
        run(executable, "contracts", command, "--check", cwd=work)
        custom = work / "custom" / ("pages" if command == "pagination-docs" else "failure.md")
        run(executable, "contracts", command, "--path", str(custom), cwd=work)
        run(executable, "contracts", command, "--path", str(custom), "--check", cwd=work)
    for pattern in ("cursor", "offset", "page_token"):
        output = work / pattern
        run(
            executable,
            "contracts",
            "pagination-example",
            pattern,
            "--output",
            str(output),
            cwd=work,
        )
        assert (output / "src" / f"pagination_{pattern}" / "server.py").is_file()
        assert (
            output / "src" / f"pagination_{pattern}" / "_vendor/pagination/adapter.py"
        ).is_file()
