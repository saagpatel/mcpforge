"""Tests for the TypeScript validator."""

from mcpforge.validator_ts import _parse_vitest_counts


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


def test_parse_vitest_counts_falls_back_for_compact_output() -> None:
    assert _parse_vitest_counts("2 passed\n1 failed") == (3, 1)
