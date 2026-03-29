"""Validator: multi-layer validation of a generated MCP server.

Validation order: AST syntax → ruff lint → import check → pytest.
Stops early on syntax failure (can't lint/import broken AST).
Stops early on import failure (can't run tests if server doesn't import).
Continues through lint errors to import check (lint errors help self-heal prompts).
"""

import ast
import asyncio
import json
import logging
import re
import subprocess
from pathlib import Path

from mcpforge.models import ValidationResult

logger = logging.getLogger(__name__)


def check_syntax(code: str) -> tuple[bool, list[str]]:
    """Check Python source code for syntax errors using ast.parse."""
    try:
        ast.parse(code)
        return True, []
    except SyntaxError as e:
        return False, [f"SyntaxError at line {e.lineno}: {e.msg}"]


def check_lint(file_path: Path) -> list[str]:
    """Run ruff on a file and return lint error messages."""
    result = subprocess.run(
        ["ruff", "check", "--output-format=json", str(file_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return []
    try:
        violations = json.loads(result.stdout)
        return [f"{v['code']}: {v['message']} (line {v['location']['row']})" for v in violations]
    except (json.JSONDecodeError, KeyError):
        raw = (result.stdout or result.stderr).strip()
        return [raw] if raw else []


async def uv_sync(output_dir: Path) -> None:
    """Run uv sync in the output directory to install dependencies.

    Does not raise on failure — import check will surface errors.
    """
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "sync",
        cwd=output_dir.resolve(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=120.0)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("uv sync timed out after 120 seconds in %s", output_dir)


async def check_import(output_dir: Path) -> tuple[bool, str]:
    """Attempt to import the generated server module using uv run."""
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "python",
        "-c",
        "from server import mcp",
        cwd=output_dir.resolve(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        if proc.returncode == 0:
            return True, ""
        return False, stderr.decode(errors="replace").strip()
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return False, "Import check timed out after 30 seconds"


async def run_tests(output_dir: Path) -> tuple[bool, int, int, str]:
    """Run pytest on the generated test_server.py.

    Returns:
        (passed, tests_run, tests_failed, output)
    """
    proc = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        "pytest",
        "test_server.py",
        "-v",
        "--tb=short",
        cwd=output_dir.resolve(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120.0)
        output = stdout.decode(errors="replace")
        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)
        tests_passed_count = int(passed_match.group(1)) if passed_match else 0
        tests_failed_count = int(failed_match.group(1)) if failed_match else 0
        tests_run = tests_passed_count + tests_failed_count
        return proc.returncode == 0, tests_run, tests_failed_count, output
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return False, 0, 0, "Tests timed out after 120 seconds"


async def validate_server(output_dir: Path) -> ValidationResult:
    """Run all validation layers on a generated server directory."""
    server_py = output_dir / "server.py"
    code = server_py.read_text(encoding="utf-8")
    errors: list[str] = []

    # Layer 1: Syntax
    syntax_ok, syntax_errors = check_syntax(code)
    if not syntax_ok:
        errors.extend(syntax_errors)
        return ValidationResult(syntax_ok=False, errors=errors)

    # Layer 2: Lint (continue to import even with lint errors)
    lint_errors = check_lint(server_py)
    errors.extend(lint_errors)

    # Layer 3: Import check
    import_ok, import_error = await check_import(output_dir)
    if not import_ok:
        if import_error:
            errors.append(import_error)
        return ValidationResult(
            syntax_ok=True,
            lint_errors=lint_errors,
            import_ok=False,
            errors=errors,
        )

    # Layer 4: Tests
    tests_passed, tests_run, tests_failed, test_output = await run_tests(output_dir)

    return ValidationResult(
        syntax_ok=True,
        lint_errors=lint_errors,
        import_ok=True,
        tests_passed=tests_passed,
        tests_run=tests_run,
        tests_failed=tests_failed,
        test_output=test_output,
        errors=errors,
    )
