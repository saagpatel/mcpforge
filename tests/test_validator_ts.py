"""Tests for the TypeScript validator."""

from unittest.mock import AsyncMock, MagicMock, patch

from mcpforge.validator_ts import (
    _parse_vitest_counts,
    check_types,
    npm_install,
    run_tests_ts,
    validate_server_ts,
)


def _mock_process(
    stdout: bytes = b"",
    stderr: bytes = b"",
    returncode: int = 0,
    *,
    timeout: bool = False,
) -> AsyncMock:
    proc = AsyncMock()
    proc.communicate = (
        AsyncMock(side_effect=TimeoutError())
        if timeout
        else AsyncMock(return_value=(stdout, stderr))
    )
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    proc.returncode = returncode
    return proc


def test_parse_vitest_counts_uses_tests_summary_not_file_summary() -> None:
    output = """
 RUN  v2.1.9 /tmp/example

 ✓ src/server.test.ts (2 tests) 1ms

 Test Files  1 passed (1)
      Tests  2 passed (2)
"""

    assert _parse_vitest_counts(output) == (2, 0)


def test_parse_vitest_counts_handles_failed_and_passed_tests() -> None:
    output = """
 Test Files  1 failed (1)
      Tests  1 failed | 2 passed (3)
"""

    assert _parse_vitest_counts(output) == (3, 1)


def test_parse_vitest_counts_sums_summary_without_total() -> None:
    output = """
 Test Files  1 passed (1)
      Tests  1 failed | 2 passed | 1 skipped
"""

    assert _parse_vitest_counts(output) == (4, 1)


def test_parse_vitest_counts_falls_back_for_compact_output() -> None:
    assert _parse_vitest_counts("2 passed\n1 failed") == (3, 1)


class TestNpmInstall:
    async def test_runs_npm_install_in_output_dir(self, tmp_path):
        proc = _mock_process()

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await npm_install(tmp_path)

        mock_exec.assert_called_once()
        assert mock_exec.call_args.args[:2] == ("npm", "install")
        assert mock_exec.call_args.kwargs["cwd"] == tmp_path.resolve()
        proc.kill.assert_not_called()
        proc.wait.assert_not_called()

    async def test_timeout_kills_and_waits_for_process(self, tmp_path):
        proc = _mock_process(timeout=True)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await npm_install(tmp_path)

        proc.kill.assert_called_once()
        proc.wait.assert_called_once()


class TestCheckTypes:
    async def test_success_returns_ok_without_errors(self, tmp_path):
        proc = _mock_process(stdout=b"typecheck clean\n")

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            ok, errors = await check_types(tmp_path)

        assert ok is True
        assert errors == []
        assert mock_exec.call_args.args[:3] == ("npx", "tsc", "--noEmit")
        assert mock_exec.call_args.kwargs["cwd"] == tmp_path.resolve()

    async def test_nonzero_return_parses_nonempty_output_lines(self, tmp_path):
        proc = _mock_process(
            stdout=(
                b"\nserver.ts(1,7): error TS2322: Type 'string' is not assignable."
                b"\n\nAnother error\n"
            ),
            returncode=2,
        )

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            ok, errors = await check_types(tmp_path)

        assert ok is False
        assert errors == [
            "server.ts(1,7): error TS2322: Type 'string' is not assignable.",
            "Another error",
        ]

    async def test_timeout_kills_waits_and_returns_error(self, tmp_path):
        proc = _mock_process(timeout=True)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            ok, errors = await check_types(tmp_path)

        assert ok is False
        assert errors == ["tsc --noEmit timed out after 60 seconds"]
        proc.kill.assert_called_once()
        proc.wait.assert_called_once()


class TestRunTestsTs:
    async def test_success_returns_counts_and_output(self, tmp_path):
        output = "      Tests  2 passed (2)\n"
        proc = _mock_process(stdout=output.encode())

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            passed, tests_run, tests_failed, test_output = await run_tests_ts(tmp_path)

        assert passed is True
        assert tests_run == 2
        assert tests_failed == 0
        assert test_output == output
        assert mock_exec.call_args.args[:3] == ("npx", "vitest", "run")
        assert mock_exec.call_args.kwargs["cwd"] == tmp_path.resolve()

    async def test_failed_tests_return_failure_counts_and_output(self, tmp_path):
        output = "      Tests  1 failed | 2 passed (3)\n"
        proc = _mock_process(stdout=output.encode(), returncode=1)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            passed, tests_run, tests_failed, test_output = await run_tests_ts(tmp_path)

        assert passed is False
        assert tests_run == 3
        assert tests_failed == 1
        assert test_output == output

    async def test_timeout_kills_waits_and_returns_timeout_result(self, tmp_path):
        proc = _mock_process(timeout=True)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            passed, tests_run, tests_failed, test_output = await run_tests_ts(tmp_path)

        assert passed is False
        assert tests_run == 0
        assert tests_failed == 0
        assert test_output == "Tests timed out after 120 seconds"
        proc.kill.assert_called_once()
        proc.wait.assert_called_once()


class TestValidateServerTs:
    async def test_returns_early_when_type_check_fails(self, tmp_path):
        npm_proc = _mock_process()
        tsc_proc = _mock_process(
            stdout=b"server.ts(1,1): error TS1005: ';' expected\n",
            returncode=2,
        )

        with patch("asyncio.create_subprocess_exec", side_effect=[npm_proc, tsc_proc]) as mock_exec:
            result = await validate_server_ts(tmp_path)

        assert result.syntax_ok is False
        assert result.import_ok is False
        assert result.lint_errors == ["server.ts(1,1): error TS1005: ';' expected"]
        assert result.errors == ["server.ts(1,1): error TS1005: ';' expected"]
        assert result.tests_passed is False
        assert result.tests_ok is True
        assert mock_exec.call_count == 2

    async def test_successful_type_check_runs_tests_and_returns_success(self, tmp_path):
        npm_proc = _mock_process()
        tsc_proc = _mock_process()
        vitest_output = "      Tests  2 passed (2)\n"
        vitest_proc = _mock_process(stdout=vitest_output.encode())

        with patch("asyncio.create_subprocess_exec", side_effect=[npm_proc, tsc_proc, vitest_proc]):
            result = await validate_server_ts(tmp_path)

        assert result.syntax_ok is True
        assert result.import_ok is True
        assert result.lint_errors == []
        assert result.tests_passed is True
        assert result.tests_ok is True
        assert result.tests_run == 2
        assert result.tests_failed == 0
        assert result.test_output == vitest_output
        assert result.errors == []

    async def test_failed_test_run_preserves_validation_success_and_test_failure(self, tmp_path):
        npm_proc = _mock_process()
        tsc_proc = _mock_process()
        vitest_output = "      Tests  1 failed | 2 passed (3)\n"
        vitest_proc = _mock_process(stdout=vitest_output.encode(), returncode=1)

        with patch("asyncio.create_subprocess_exec", side_effect=[npm_proc, tsc_proc, vitest_proc]):
            result = await validate_server_ts(tmp_path)

        assert result.syntax_ok is True
        assert result.import_ok is True
        assert result.lint_errors == []
        assert result.tests_passed is False
        assert result.tests_ok is False
        assert result.tests_run == 3
        assert result.tests_failed == 1
        assert result.test_output == vitest_output
        assert result.errors == []
