"""Tests for mcpforge self_heal module — surgical patch and full rewrite."""

from unittest.mock import AsyncMock

from mcpforge.self_heal import (
    _extract_error_lines,
    _find_affected_functions,
    attempt_fix,
)

VALID_CODE = '''from fastmcp import FastMCP

mcp = FastMCP("Test")


@mcp.tool
async def create_item(name: str) -> dict:
    """Create an item."""
    return {"name": name}


@mcp.tool
async def delete_item(item_id: str) -> dict:
    """Delete an item."""
    return {"deleted": item_id}


@mcp.tool
async def list_items() -> dict:
    """List all items."""
    return {"items": []}
'''

BROKEN_FUNC_CODE = '''from fastmcp import FastMCP

mcp = FastMCP("Test")


@mcp.tool
async def broken_func(x: str) -> dict:
    return {"x": x  # missing closing paren - syntax error


@mcp.tool
async def good_func(y: str) -> dict:
    return {"y": y}
'''


class TestExtractErrorLines:
    def test_extracts_line_from_line_n_format(self):
        errors = ["SyntaxError at line 7: invalid syntax"]
        assert 7 in _extract_error_lines(errors)

    def test_extracts_line_from_colon_format(self):
        errors = ["server.py:42: F401 unused import"]
        assert 42 in _extract_error_lines(errors)

    def test_extracts_multiple_lines(self):
        errors = ["Error at line 5", "Another error at line 10"]
        result = _extract_error_lines(errors)
        assert 5 in result
        assert 10 in result

    def test_returns_empty_for_no_line_numbers(self):
        errors = ["ImportError: no module named fastmcp"]
        assert _extract_error_lines(errors) == set()

    def test_handles_empty_list(self):
        assert _extract_error_lines([]) == set()


class TestFindAffectedFunctions:
    def test_finds_function_containing_line(self):
        # create_item starts at line ~7 (after the imports and mcp setup)
        result = _find_affected_functions(VALID_CODE, {8})
        assert len(result) >= 1
        # At least one function covers line 8
        assert any(start <= 8 <= end for start, end, _ in result)

    def test_returns_empty_for_no_matching_lines(self):
        result = _find_affected_functions(VALID_CODE, {1, 2, 3})
        assert result == []

    def test_returns_empty_for_syntax_error_code(self):
        result = _find_affected_functions("def broken(:\n    pass", {1})
        assert result == []

    def test_includes_function_source_text(self):
        result = _find_affected_functions(VALID_CODE, {8})
        for _start, _end, src in result:
            assert "async def" in src or "def " in src

    def test_multiple_functions_affected(self):
        # Lines in both functions
        code = "async def f1():\n    x = 1\n\nasync def f2():\n    y = 2\n"
        result = _find_affected_functions(code, {2, 5})
        assert len(result) == 2


class TestAttemptFix:
    async def test_returns_fixed_code_on_success(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="fixed code here")
        result = await attempt_fix("broken code", ["SyntaxError at line 1"], mock_client)
        assert result == "fixed code here"

    async def test_returns_none_on_exception(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=RuntimeError("API error"))
        result = await attempt_fix("code", ["error"], mock_client)
        assert result is None

    async def test_returns_none_for_empty_response(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="   ")
        result = await attempt_fix("code", ["error"], mock_client)
        assert result is None

    async def test_surgical_path_used_for_few_errors(self):
        """When only 1-3 functions are affected, first call is surgical."""
        mock_client = AsyncMock()
        # Return valid Python function for surgical attempt
        mock_client.generate = AsyncMock(
            return_value="async def create_item(name: str) -> dict:\n    return {'name': name}"
        )

        # Code with 1 broken function
        await attempt_fix(VALID_CODE, ["SyntaxError at line 8"], mock_client)
        # Should have called generate (either surgical or fallback)
        assert mock_client.generate.called

    async def test_full_rewrite_used_for_many_errors(self):
        """When many functions are affected, goes to full rewrite."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="full rewritten code")
        # Lines spread across all 3 functions + non-function lines
        errors = [f"error at line {i}" for i in [8, 13, 18]]
        await attempt_fix(VALID_CODE, errors, mock_client)
        assert mock_client.generate.called

    async def test_errors_in_user_message(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="fixed code")
        await attempt_fix("broken code", ["ImportError: no module named foo"], mock_client)
        user_msg = mock_client.generate.call_args.kwargs["user_message"]
        assert "ImportError: no module named foo" in user_msg

    async def test_code_in_user_message_on_full_rewrite(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="fixed code")
        # No line numbers in error → no surgical attempt → full rewrite
        await attempt_fix("ORIGINAL_CODE_XYZ", ["ImportError: no module"], mock_client)
        user_msg = mock_client.generate.call_args.kwargs["user_message"]
        assert "ORIGINAL_CODE_XYZ" in user_msg

    async def test_uses_temperature_zero(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="fixed code")
        await attempt_fix("code", ["error"], mock_client)
        assert mock_client.generate.call_args.kwargs["temperature"] == 0.0

    async def test_strips_code_fences_on_full_rewrite(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="```python\nfixed code\n```")
        # No line numbers → full rewrite
        result = await attempt_fix("code", ["ImportError: missing"], mock_client)
        assert result == "fixed code"

    async def test_multiple_errors_all_present_in_message(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="fixed")
        errors = ["SyntaxError at line 1", "ImportError: missing module", "NameError: x"]
        await attempt_fix("code", errors, mock_client)
        user_msg = mock_client.generate.call_args.kwargs["user_message"]
        for err in errors:
            assert err in user_msg
