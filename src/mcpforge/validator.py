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

from mcpforge.models import KNOWN_PACKAGES, ServerPlan, ValidationResult
from mcpforge.sandbox import sandboxed_command
from mcpforge.security import ALLOWED_IMPORTS, check_security

# Combined package allowlist: stdlib/common imports + known safe third-party packages.
# Union of ALLOWED_IMPORTS (used for import scanning) and KNOWN_PACKAGES (pip names).
_ALLOWED_PACKAGES: frozenset[str] = frozenset(
    {p.lower() for p in ALLOWED_IMPORTS} | {p.lower() for p in KNOWN_PACKAGES}
)

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
    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", str(file_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return ["Lint check timed out after 30 seconds"]
    if result.returncode == 0:
        return []
    try:
        violations = json.loads(result.stdout)
        return [f"{v['code']}: {v['message']} (line {v['location']['row']})" for v in violations]
    except (json.JSONDecodeError, KeyError):
        raw = (result.stdout or result.stderr).strip()
        return [raw] if raw else []


def check_packages(plan: ServerPlan) -> str | None:
    """Validate that all external packages in the plan are on the allowlist.

    Returns an error message string listing rejected packages, or None if all allowed.
    """
    rejected = [
        pkg for pkg in plan.external_packages
        if pkg.lower() not in _ALLOWED_PACKAGES
    ]
    if rejected:
        return (
            f"Package allowlist violation — refusing uv sync. "
            f"Rejected packages: {', '.join(rejected)}. "
            f"Add them to KNOWN_PACKAGES in models.py after manual review."
        )
    return None


async def uv_sync(output_dir: Path, plan: ServerPlan | None = None) -> str | None:
    """Run uv sync in the output directory to install dependencies.

    When a plan is provided, validates all external packages against the allowlist
    before running uv sync. Returns an error message string on failure or None on success.
    """
    if plan is not None:
        pkg_err = check_packages(plan)
        if pkg_err:
            logger.warning("uv sync blocked by package allowlist: %s", pkg_err)
            return pkg_err

    proc = await asyncio.create_subprocess_exec(
        "uv",
        "sync",
        cwd=output_dir.resolve(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
        if proc.returncode != 0:
            msg = stderr.decode(errors="replace").strip()
            logger.warning("uv sync failed in %s: %s", output_dir, msg)
            return f"Dependency installation failed: {msg}"
        return None
    except TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("uv sync timed out after 120 seconds in %s", output_dir)
        return "Dependency installation timed out after 120 seconds"


async def check_import(output_dir: Path) -> tuple[bool, str]:
    """Attempt to import the generated server module using uv run.

    The command is wrapped with sandbox-exec on macOS to restrict
    network access and filesystem writes outside the output directory.
    """
    base_cmd = ["uv", "run", "python", "-c", "from server import mcp"]
    cmd = sandboxed_command(base_cmd, output_dir)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
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

    The command is wrapped with sandbox-exec on macOS to restrict
    network access and filesystem writes outside the output directory.

    Returns:
        (passed, tests_run, tests_failed, output)
    """
    base_cmd = ["uv", "run", "pytest", "test_server.py", "-v", "--tb=short"]
    cmd = sandboxed_command(base_cmd, output_dir)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
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


def check_plan_conformance(code: str, plan: ServerPlan) -> list[str]:
    """Verify generated code contains tool functions matching the plan.

    Returns a list of warning strings for missing or extra tools.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # Syntax checking is handled elsewhere

    # Find all async functions decorated with @mcp.tool
    generated_tools: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            is_mcp_tool = (
                isinstance(decorator, ast.Attribute)
                and isinstance(decorator.value, ast.Name)
                and decorator.value.id == "mcp"
                and decorator.attr == "tool"
            )
            if is_mcp_tool:
                generated_tools.add(node.name)

    planned_tools = {t.name for t in plan.tools}
    warnings: list[str] = []

    missing = planned_tools - generated_tools
    if missing:
        warnings.append(f"Plan-to-code: missing tools: {', '.join(sorted(missing))}")

    extra = generated_tools - planned_tools
    if extra:
        warnings.append(f"Plan-to-code: extra tools not in plan: {', '.join(sorted(extra))}")

    return warnings


async def validate_server(
    output_dir: Path,
    *,
    skip_execution: bool = False,
    strict: bool = False,
) -> ValidationResult:
    """Run all validation layers on a generated server directory.

    When skip_execution=True, only runs syntax check, security scan, and lint.
    When strict=True, lint errors halt validation (no import check or tests).
    """
    server_py = output_dir / "server.py"
    code = server_py.read_text(encoding="utf-8")
    errors: list[str] = []

    # Layer 1: Syntax
    syntax_ok, syntax_errors = check_syntax(code)
    if not syntax_ok:
        errors.extend(syntax_errors)
        return ValidationResult(syntax_ok=False, errors=errors)

    # Layer 1.5: Security scan (block execution on dangerous patterns)
    security_findings = check_security(code)
    dangerous = [f for f in security_findings if f.startswith("DANGEROUS:")]
    errors.extend(security_findings)
    if dangerous:
        return ValidationResult(
            syntax_ok=True,
            lint_errors=[],
            import_ok=False,
            errors=errors,
        )

    # Layer 2: Lint (continue to import even with lint errors, unless strict)
    lint_errors = check_lint(server_py)
    errors.extend(lint_errors)

    if strict and lint_errors:
        return ValidationResult(
            syntax_ok=True,
            lint_errors=lint_errors,
            import_ok=False,
            errors=errors,
        )

    # Early return when execution is disabled (--no-execute)
    if skip_execution:
        return ValidationResult(
            syntax_ok=True,
            lint_errors=lint_errors,
            import_ok=False,
            errors=errors,
        )

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
