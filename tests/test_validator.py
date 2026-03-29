"""Tests for mcpforge validator module."""

from unittest.mock import AsyncMock, patch

from mcpforge.validator import check_lint, check_syntax, validate_server

# Module-level test code constants
VALID_SERVER = 'from fastmcp import FastMCP\n\nmcp = FastMCP("Test")\n'
SYNTAX_ERROR = "from fastmcp import FastMCP\nmcp = FastMCP('Test'\n"  # unclosed paren
LINT_ERROR = "import os\nfrom fastmcp import FastMCP\n\nmcp = FastMCP('Test')\n"  # unused import


class TestCheckSyntax:
    def test_valid_code_returns_true(self):
        ok, errors = check_syntax(VALID_SERVER)
        assert ok is True
        assert errors == []

    def test_syntax_error_returns_false(self):
        ok, errors = check_syntax(SYNTAX_ERROR)
        assert ok is False
        assert len(errors) == 1
        assert "SyntaxError" in errors[0]

    def test_syntax_error_includes_line_number(self):
        ok, errors = check_syntax(SYNTAX_ERROR)
        assert not ok
        assert any(c.isdigit() for c in errors[0])

    def test_empty_string_is_valid(self):
        ok, errors = check_syntax("")
        assert ok is True
        assert errors == []

    def test_valid_complex_code(self):
        code = """
import asyncio
from typing import Optional

async def main() -> None:
    x: Optional[int] = None
    match x:
        case None:
            pass
        case int(n):
            print(n)
"""
        ok, errors = check_syntax(code)
        assert ok is True


class TestCheckLint:
    def test_returns_list(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(VALID_SERVER)
        result = check_lint(f)
        assert isinstance(result, list)

    def test_clean_code_returns_empty_list(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(VALID_SERVER)
        result = check_lint(f)
        assert result == []

    def test_detects_unused_import(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(LINT_ERROR)
        result = check_lint(f)
        assert len(result) > 0
        assert any("F401" in e for e in result)

    def test_error_includes_line_number(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(LINT_ERROR)
        result = check_lint(f)
        assert len(result) > 0
        assert any("line" in e for e in result)


class TestValidateServer:
    async def test_syntax_error_returns_early(self, tmp_path):
        (tmp_path / "server.py").write_text(SYNTAX_ERROR)
        mock_check_import = AsyncMock(return_value=(True, ""))
        with patch("mcpforge.validator.check_import", mock_check_import):
            result = await validate_server(tmp_path)
        assert result.syntax_ok is False
        assert result.is_valid is False
        mock_check_import.assert_not_called()

    async def test_valid_server_fully_checked(self, tmp_path):
        (tmp_path / "server.py").write_text(VALID_SERVER)
        mock_import = AsyncMock(return_value=(True, ""))
        mock_tests = AsyncMock(return_value=(True, 3, 0, "3 passed"))
        with (
            patch("mcpforge.validator.check_import", mock_import),
            patch("mcpforge.validator.run_tests", mock_tests),
        ):
            result = await validate_server(tmp_path)
        assert result.syntax_ok is True
        assert result.import_ok is True
        assert result.is_valid is True
        assert result.tests_run == 3

    async def test_import_failure_returns_early(self, tmp_path):
        (tmp_path / "server.py").write_text(VALID_SERVER)
        mock_import = AsyncMock(return_value=(False, "ModuleNotFoundError: fastmcp"))
        mock_tests = AsyncMock(return_value=(True, 0, 0, ""))
        with (
            patch("mcpforge.validator.check_import", mock_import),
            patch("mcpforge.validator.run_tests", mock_tests),
        ):
            result = await validate_server(tmp_path)
        assert result.import_ok is False
        assert result.is_valid is False
        mock_tests.assert_not_called()

    async def test_lint_errors_continue_to_import_check(self, tmp_path):
        (tmp_path / "server.py").write_text(LINT_ERROR)
        mock_import = AsyncMock(return_value=(True, ""))
        mock_tests = AsyncMock(return_value=(True, 0, 0, ""))
        with (
            patch("mcpforge.validator.check_import", mock_import),
            patch("mcpforge.validator.run_tests", mock_tests),
        ):
            result = await validate_server(tmp_path)
        assert result.syntax_ok is True
        mock_import.assert_called_once()
        assert result.is_valid is False

    async def test_import_error_in_errors_list(self, tmp_path):
        (tmp_path / "server.py").write_text(VALID_SERVER)
        mock_import = AsyncMock(return_value=(False, "ImportError: no module named fastmcp"))
        with patch("mcpforge.validator.check_import", mock_import):
            result = await validate_server(tmp_path)
        assert any("ImportError" in e for e in result.errors)

    async def test_test_failures_dont_invalidate(self, tmp_path):
        (tmp_path / "server.py").write_text(VALID_SERVER)
        mock_import = AsyncMock(return_value=(True, ""))
        mock_tests = AsyncMock(return_value=(False, 5, 2, "2 failed, 3 passed"))
        with (
            patch("mcpforge.validator.check_import", mock_import),
            patch("mcpforge.validator.run_tests", mock_tests),
        ):
            result = await validate_server(tmp_path)
        assert result.is_valid is True
        assert result.tests_failed == 2
        assert result.tests_passed is False

    async def test_syntax_error_message_in_errors(self, tmp_path):
        (tmp_path / "server.py").write_text(SYNTAX_ERROR)
        result = await validate_server(tmp_path)
        assert len(result.errors) > 0
        assert any("SyntaxError" in e for e in result.errors)
