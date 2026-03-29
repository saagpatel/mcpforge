"""Validator: multi-layer validation of a generated MCP server.

Phase 1 implementation.
"""

from pathlib import Path

from mcpforge.models import ValidationResult


async def validate_server(output_dir: Path) -> ValidationResult:
    """Run all validation layers on a generated server directory.

    Runs in order: AST syntax check → ruff lint → import check → pytest.

    Args:
        output_dir: Path to the generated server directory containing server.py
                    and test_server.py.

    Returns:
        ValidationResult with results from each layer.
    """
    raise NotImplementedError("validator.validate_server is implemented in Phase 1")


def check_syntax(code: str) -> tuple[bool, list[str]]:
    """Check Python source code for syntax errors using ast.parse.

    Returns:
        (ok, errors) where errors is empty on success.
    """
    raise NotImplementedError("validator.check_syntax is implemented in Phase 1")


def check_lint(file_path: Path) -> list[str]:
    """Run ruff on a file and return any lint error messages.

    Returns:
        List of ruff error strings. Empty list means clean.
    """
    raise NotImplementedError("validator.check_lint is implemented in Phase 1")


def check_import(server_path: Path) -> tuple[bool, str]:
    """Attempt to import the generated server module in a subprocess.

    Returns:
        (ok, error_message) where error_message is empty on success.
    """
    raise NotImplementedError("validator.check_import is implemented in Phase 1")


def run_tests(test_path: Path) -> tuple[bool, int, int, str]:
    """Run pytest on the generated test file.

    Returns:
        (passed, tests_run, tests_failed, output)
    """
    raise NotImplementedError("validator.run_tests is implemented in Phase 1")
