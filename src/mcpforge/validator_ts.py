"""TypeScript validator: type-check and test a generated TS MCP server."""

import asyncio
import logging
import re
from pathlib import Path

from mcpforge.models import ValidationResult

logger = logging.getLogger(__name__)


async def npm_install(output_dir: Path) -> None:
    """Run npm install in output_dir.

    Does not raise on failure — type check will surface errors.
    """
    proc = await asyncio.create_subprocess_exec(
        "npm",
        "install",
        cwd=output_dir.resolve(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=120.0)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("npm install timed out after 120 seconds in %s", output_dir)


async def check_types(output_dir: Path) -> tuple[bool, list[str]]:
    """Run tsc --noEmit to type-check the TypeScript source.

    Returns (ok, error_lines).
    """
    proc = await asyncio.create_subprocess_exec(
        "npx",
        "tsc",
        "--noEmit",
        cwd=output_dir.resolve(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        output = stdout.decode(errors="replace")
        if proc.returncode == 0:
            return True, []
        error_lines = [line for line in output.splitlines() if line.strip()]
        return False, error_lines
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return False, ["tsc --noEmit timed out after 60 seconds"]


async def run_tests_ts(output_dir: Path) -> tuple[bool, int, int, str]:
    """Run vitest in the output directory.

    Returns (all_passed, tests_run, tests_failed, output_text).
    """
    proc = await asyncio.create_subprocess_exec(
        "npx",
        "vitest",
        "run",
        cwd=output_dir.resolve(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120.0)
        output = stdout.decode(errors="replace")
        passed_match = re.search(r"(\d+)\s+passed", output)
        failed_match = re.search(r"(\d+)\s+failed", output)
        tests_passed_count = int(passed_match.group(1)) if passed_match else 0
        tests_failed_count = int(failed_match.group(1)) if failed_match else 0
        tests_run = tests_passed_count + tests_failed_count
        return proc.returncode == 0, tests_run, tests_failed_count, output
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return False, 0, 0, "Tests timed out after 120 seconds"


async def validate_server_ts(output_dir: Path) -> ValidationResult:
    """Orchestrate npm install → tsc → vitest for a generated TS server."""
    errors: list[str] = []

    # Step 1: npm install
    await npm_install(output_dir)

    # Step 2: Type check (covers both syntax and type errors)
    type_ok, tsc_errors = await check_types(output_dir)
    errors.extend(tsc_errors)

    if not type_ok:
        return ValidationResult(
            syntax_ok=False,
            import_ok=False,
            lint_errors=tsc_errors,
            errors=errors,
        )

    # Step 3: Tests
    tests_passed, tests_run, tests_failed, test_output = await run_tests_ts(output_dir)

    return ValidationResult(
        syntax_ok=True,
        import_ok=True,
        lint_errors=[],
        tests_passed=tests_passed,
        tests_run=tests_run,
        tests_failed=tests_failed,
        test_output=test_output,
        errors=errors,
    )
