"""Tests for mcpforge validator module."""

import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

from mcpforge.models import PromptDef, ResourceDef, ServerPlan, ToolDef
from mcpforge.validator import (
    check_import,
    check_lint,
    check_packages,
    check_plan_conformance,
    check_syntax,
    run_tests,
    uv_sync,
    validate_server,
)

# Module-level test code constants
VALID_SERVER = 'from fastmcp import FastMCP\n\nmcp = FastMCP("Test")\n'
SYNTAX_ERROR = "from fastmcp import FastMCP\nmcp = FastMCP('Test'\n"  # unclosed paren
LINT_ERROR = "import os\nfrom fastmcp import FastMCP\n\nmcp = FastMCP('Test')\n"  # unused import


def make_plan(external_packages: list[str] | None = None) -> ServerPlan:
    return ServerPlan(
        name="Test",
        description="Test",
        tools=[],
        external_packages=external_packages or [],
    )


class FakeProcess:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        timeout: bool = False,
    ):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timeout = timeout
        self.kill = MagicMock()
        self.wait = AsyncMock()

    async def communicate(self):
        if self.timeout:
            raise TimeoutError()
        return self.stdout, self.stderr


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
        completed = subprocess.CompletedProcess(args=["ruff"], returncode=0, stdout="", stderr="")
        with patch("mcpforge.validator.subprocess.run", return_value=completed):
            result = check_lint(f)
        assert isinstance(result, list)

    def test_clean_code_returns_empty_list(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(VALID_SERVER)
        completed = subprocess.CompletedProcess(args=["ruff"], returncode=0, stdout="", stderr="")
        with patch("mcpforge.validator.subprocess.run", return_value=completed):
            result = check_lint(f)
        assert result == []

    def test_detects_unused_import(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(LINT_ERROR)
        completed = subprocess.CompletedProcess(
            args=["ruff"],
            returncode=1,
            stdout='[{"code":"F401","message":"unused import","location":{"row":1}}]',
            stderr="",
        )
        with patch("mcpforge.validator.subprocess.run", return_value=completed):
            result = check_lint(f)
        assert len(result) > 0
        assert any("F401" in e for e in result)

    def test_error_includes_line_number(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(LINT_ERROR)
        completed = subprocess.CompletedProcess(
            args=["ruff"],
            returncode=1,
            stdout='[{"code":"F401","message":"unused import","location":{"row":1}}]',
            stderr="",
        )
        with patch("mcpforge.validator.subprocess.run", return_value=completed):
            result = check_lint(f)
        assert len(result) > 0
        assert any("line" in e for e in result)

    def test_timeout_returns_error_message(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(VALID_SERVER)
        with patch(
            "mcpforge.validator.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["ruff"], timeout=30),
        ):
            result = check_lint(f)
        assert result == ["Lint check timed out after 30 seconds"]

    def test_malformed_json_returns_raw_stdout(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(VALID_SERVER)
        completed = subprocess.CompletedProcess(
            args=["ruff"],
            returncode=1,
            stdout="ruff emitted non-json output",
            stderr="ignored when stdout exists",
        )
        with patch("mcpforge.validator.subprocess.run", return_value=completed):
            result = check_lint(f)
        assert result == ["ruff emitted non-json output"]

    def test_malformed_json_falls_back_to_stderr(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text(VALID_SERVER)
        completed = subprocess.CompletedProcess(
            args=["ruff"],
            returncode=1,
            stdout="",
            stderr="ruff crashed before json",
        )
        with patch("mcpforge.validator.subprocess.run", return_value=completed):
            result = check_lint(f)
        assert result == ["ruff crashed before json"]


class TestCheckPackages:
    def test_rejects_external_packages_not_on_allowlist(self):
        error = check_packages(make_plan(["requests", "sketchy-pkg"]))

        assert error is not None
        assert "Package allowlist violation" in error
        assert "sketchy-pkg" in error
        assert "requests" not in error

    def test_allows_known_external_packages_case_insensitively(self):
        assert check_packages(make_plan(["Requests", "HTTPX"])) is None


class TestUvSync:
    async def test_calls_uv_sync_in_output_dir(self, tmp_path):
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"", b""))
        proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await uv_sync(tmp_path)
        mock_exec.assert_called_once()
        args = mock_exec.call_args.args
        assert args[0] == "uv"
        assert args[1] == "sync"
        assert mock_exec.call_args.kwargs["cwd"] == tmp_path.resolve()

    async def test_timeout_kills_process(self, tmp_path):
        proc = FakeProcess(timeout=True)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await uv_sync(tmp_path)
        assert result == "Dependency installation timed out after 120 seconds"
        proc.kill.assert_called_once()
        proc.wait.assert_called_once()

    async def test_does_not_raise_on_failure(self, tmp_path):
        proc = FakeProcess(returncode=1, stderr=b"dependency solver failed")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await uv_sync(tmp_path)
        assert result == "Dependency installation failed: dependency solver failed"

    async def test_returns_none_on_success(self, tmp_path):
        proc = FakeProcess(returncode=0, stdout=b"ok", stderr=b"")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await uv_sync(tmp_path)
        assert result is None

    async def test_allowlist_violation_blocks_subprocess(self, tmp_path):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            result = await uv_sync(tmp_path, make_plan(["malware-toolkit"]))

        assert result is not None
        assert "Package allowlist violation" in result
        assert "malware-toolkit" in result
        mock_exec.assert_not_called()


class TestCheckImport:
    async def test_subprocess_success_returns_true(self, tmp_path):
        proc = FakeProcess(returncode=0)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            ok, error = await check_import(tmp_path)

        assert ok is True
        assert error == ""

    async def test_subprocess_failure_returns_stderr(self, tmp_path):
        proc = FakeProcess(returncode=1, stderr=b"ModuleNotFoundError: fastmcp")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            ok, error = await check_import(tmp_path)

        assert ok is False
        assert error == "ModuleNotFoundError: fastmcp"

    async def test_timeout_kills_process_and_returns_message(self, tmp_path):
        proc = FakeProcess(timeout=True)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            ok, error = await check_import(tmp_path)

        assert ok is False
        assert error == "Import check timed out after 30 seconds"
        proc.kill.assert_called_once()
        proc.wait.assert_called_once()


class TestRunTests:
    async def test_parses_passed_and_failed_counts(self, tmp_path):
        output = b"test_a PASSED\ntest_b FAILED\n=== 3 passed, 2 failed in 0.04s ==="
        proc = FakeProcess(returncode=1, stdout=output)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            passed, tests_run, tests_failed, test_output = await run_tests(tmp_path)

        assert passed is False
        assert tests_run == 5
        assert tests_failed == 2
        assert "3 passed, 2 failed" in test_output

    async def test_timeout_kills_process_and_returns_message(self, tmp_path):
        proc = FakeProcess(timeout=True)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            passed, tests_run, tests_failed, output = await run_tests(tmp_path)

        assert passed is False
        assert tests_run == 0
        assert tests_failed == 0
        assert output == "Tests timed out after 120 seconds"
        proc.kill.assert_called_once()
        proc.wait.assert_called_once()


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
            patch("mcpforge.validator.check_lint", return_value=[]),
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
            patch("mcpforge.validator.check_lint", return_value=[]),
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
            patch("mcpforge.validator.check_lint", return_value=["F401: unused import (line 1)"]),
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
        with (
            patch("mcpforge.validator.check_lint", return_value=[]),
            patch("mcpforge.validator.check_import", mock_import),
        ):
            result = await validate_server(tmp_path)
        assert any("ImportError" in e for e in result.errors)

    async def test_test_failures_dont_invalidate(self, tmp_path):
        (tmp_path / "server.py").write_text(VALID_SERVER)
        mock_import = AsyncMock(return_value=(True, ""))
        mock_tests = AsyncMock(return_value=(False, 5, 2, "2 failed, 3 passed"))
        with (
            patch("mcpforge.validator.check_lint", return_value=[]),
            patch("mcpforge.validator.check_import", mock_import),
            patch("mcpforge.validator.run_tests", mock_tests),
        ):
            result = await validate_server(tmp_path)
        assert result.is_valid is True
        assert result.tests_ok is False
        assert result.tests_failed == 2
        assert result.tests_passed is False

    async def test_syntax_error_message_in_errors(self, tmp_path):
        (tmp_path / "server.py").write_text(SYNTAX_ERROR)
        result = await validate_server(tmp_path)
        assert len(result.errors) > 0
        assert any("SyntaxError" in e for e in result.errors)

    async def test_strict_mode_halts_on_lint_errors(self, tmp_path):
        (tmp_path / "server.py").write_text(LINT_ERROR)
        mock_import = AsyncMock(return_value=(True, ""))
        with (
            patch("mcpforge.validator.check_lint", return_value=["F401: unused import (line 1)"]),
            patch("mcpforge.validator.check_import", mock_import),
        ):
            result = await validate_server(tmp_path, strict=True)
        assert result.syntax_ok is True
        assert result.import_ok is False  # halted before import
        assert len(result.lint_errors) > 0
        mock_import.assert_not_called()

    async def test_dangerous_security_finding_blocks_execution(self, tmp_path):
        (tmp_path / "server.py").write_text(
            "from fastmcp import FastMCP\n"
            "mcp = FastMCP('Test')\n"
            "def unsafe():\n"
            "    eval('1 + 1')\n"
        )
        mock_import = AsyncMock(return_value=(True, ""))
        with (
            patch("mcpforge.validator.check_lint") as mock_lint,
            patch("mcpforge.validator.check_import", mock_import),
        ):
            result = await validate_server(tmp_path)

        assert result.syntax_ok is True
        assert result.import_ok is False
        assert result.is_valid is False
        assert result.lint_errors == []
        assert any("DANGEROUS: call to 'eval()'" in error for error in result.errors)
        mock_lint.assert_not_called()
        mock_import.assert_not_called()

    async def test_skip_execution_returns_after_lint(self, tmp_path):
        (tmp_path / "server.py").write_text(VALID_SERVER)
        mock_import = AsyncMock(return_value=(True, ""))
        with (
            patch("mcpforge.validator.check_lint", return_value=["W123: warning (line 1)"]),
            patch("mcpforge.validator.check_import", mock_import),
        ):
            result = await validate_server(tmp_path, skip_execution=True)

        assert result.syntax_ok is True
        assert result.import_ok is False
        assert result.lint_errors == ["W123: warning (line 1)"]
        assert result.errors == ["W123: warning (line 1)"]
        assert result.tests_run == 0
        assert result.tests_passed is False
        mock_import.assert_not_called()

    async def test_tests_result_propagates_to_validation_result(self, tmp_path):
        (tmp_path / "server.py").write_text(VALID_SERVER)
        mock_import = AsyncMock(return_value=(True, ""))
        mock_tests = AsyncMock(return_value=(False, 4, 1, "1 failed, 3 passed"))
        with (
            patch("mcpforge.validator.check_lint", return_value=[]),
            patch("mcpforge.validator.check_import", mock_import),
            patch("mcpforge.validator.run_tests", mock_tests),
        ):
            result = await validate_server(tmp_path)

        assert result.syntax_ok is True
        assert result.import_ok is True
        assert result.tests_passed is False
        assert result.tests_run == 4
        assert result.tests_failed == 1
        assert result.test_output == "1 failed, 3 passed"
        assert result.errors == []


class TestCheckPlanConformance:
    def _plan_with_tools(self, *names: str) -> ServerPlan:
        return ServerPlan(
            name="Test",
            description="Test",
            tools=[ToolDef(name=n, description=f"Tool {n}", params=[]) for n in names],
        )

    def test_matching_tools_no_warnings(self):
        code = """
from fastmcp import FastMCP
mcp = FastMCP("Test")

@mcp.tool
async def create_todo():
    pass

@mcp.tool
async def list_todos():
    pass
"""
        plan = self._plan_with_tools("create_todo", "list_todos")
        assert check_plan_conformance(code, plan) == []

    def test_missing_tool_reported(self):
        code = """
from fastmcp import FastMCP
mcp = FastMCP("Test")

@mcp.tool
async def create_todo():
    pass
"""
        plan = self._plan_with_tools("create_todo", "delete_todo")
        warnings = check_plan_conformance(code, plan)
        assert len(warnings) == 1
        assert "missing tools" in warnings[0]
        assert "delete_todo" in warnings[0]

    def test_extra_tool_reported(self):
        code = """
from fastmcp import FastMCP
mcp = FastMCP("Test")

@mcp.tool
async def create_todo():
    pass

@mcp.tool
async def bonus_tool():
    pass
"""
        plan = self._plan_with_tools("create_todo")
        warnings = check_plan_conformance(code, plan)
        assert len(warnings) == 1
        assert "extra tools" in warnings[0]
        assert "bonus_tool" in warnings[0]

    def test_missing_resource_and_prompt_reported(self):
        code = """
from fastmcp import FastMCP
mcp = FastMCP("Test")

@mcp.tool
async def create_todo():
    pass
"""
        plan = ServerPlan(
            name="Test",
            description="Test",
            tools=[ToolDef(name="create_todo", description="Create", params=[])],
            resources=[
                ResourceDef(
                    uri_pattern="data://config",
                    name="config_resource",
                    description="Config",
                )
            ],
            prompts=[PromptDef(name="summarize", description="Summarize")],
        )
        warnings = check_plan_conformance(code, plan)
        assert any("missing resources" in warning for warning in warnings)
        assert any("missing prompts" in warning for warning in warnings)

    def test_matching_resource_and_prompt_no_warnings(self):
        code = """
from fastmcp import FastMCP
mcp = FastMCP("Test")

@mcp.resource("data://config")
async def config_resource():
    return "config"

@mcp.prompt
async def summarize():
    return "summary"
"""
        plan = ServerPlan(
            name="Test",
            description="Test",
            tools=[],
            resources=[
                ResourceDef(
                    uri_pattern="data://config",
                    name="config_resource",
                    description="Config",
                )
            ],
            prompts=[PromptDef(name="summarize", description="Summarize")],
        )
        assert check_plan_conformance(code, plan) == []

    def test_syntax_error_returns_empty(self):
        plan = self._plan_with_tools("create_todo")
        assert check_plan_conformance("def broken(", plan) == []
