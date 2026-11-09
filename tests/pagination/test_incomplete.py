"""Failure resolution, page budgets, and executable restart/resume cursors."""

import pytest

from mcpforge.contracts import FailureContract
from mcpforge.pagination import traverse
from mcpforge.pagination.harness import MutatingUpstream

ROWS = [{"id": n, "order": n} for n in range(9)]
CONTRACT = FailureContract(retryable=True, partial_result_allowed=True)


@pytest.mark.parametrize("pattern", ["cursor", "offset", "page_token"])
def test_incomplete_budget_has_resume_cursor_and_no_silent_truncation(pattern):
    source = MutatingUpstream(ROWS)
    first = traverse(source.adapter(pattern, 3), CONTRACT, 1)
    assert first.outcome.status == "incomplete"
    assert first.outcome.failure.kind == "page_shifted"
    assert first.pages == 1
    assert first.outcome.failure.resume_cursor == first.resume_cursor
    assert first.resume_cursor
    rest = traverse(source.adapter(pattern, 3, resume_cursor=first.resume_cursor), CONTRACT, 10)
    assert rest.outcome.status == "complete"
    assert first.items + rest.items == ROWS


@pytest.mark.parametrize("pattern", ["cursor", "page_token"])
@pytest.mark.parametrize("retryable", [True, False])
def test_incomplete_expiry_is_outcome_and_resume_is_usable(pattern, retryable):
    source = MutatingUpstream(ROWS, [{"after_page": 1, "op": "expire_cursors"}])
    first = traverse(
        source.adapter(pattern, 3),
        FailureContract(retryable=retryable, partial_result_allowed=True),
        20,
    )
    assert first.outcome.status == "incomplete"
    assert first.outcome.failure.kind == "cursor_expired"
    assert first.outcome.failure.retryable == retryable
    assert first.items == ROWS[:3]
    assert first.pages == 1
    assert first.resume_cursor
    resumed = traverse(source.adapter(pattern, 3, resume_cursor=first.resume_cursor), CONTRACT, 20)
    assert resumed.outcome.status == "complete"
    assert resumed.items == (ROWS[3:] if pattern == "cursor" else ROWS)


def test_incomplete_token_version_change_requires_new_traversal():
    source = MutatingUpstream(ROWS, [{"after_page": 1, "op": "bump_version"}])
    first = traverse(source.adapter("page_token", 3), CONTRACT, 20)
    assert first.outcome.failure.kind == "page_shifted"
    assert first.resume_cursor
    restarted = traverse(
        source.adapter("page_token", 3, resume_cursor=first.resume_cursor), CONTRACT, 20
    )
    assert restarted.outcome.status == "complete"
    assert restarted.items == ROWS


def test_incomplete_failed_contract_does_not_leak_partial_items():
    source = MutatingUpstream(ROWS)
    result = traverse(
        source.adapter("cursor", 3),
        FailureContract(retryable=False, partial_result_allowed=False),
        1,
    )
    assert result.outcome.status == "failed"
    assert result.items == []
    assert result.resume_cursor == result.outcome.failure.resume_cursor
    assert not result.outcome.failure.partial_result
    restarted = traverse(
        source.adapter("cursor", 3, resume_cursor=result.resume_cursor), CONTRACT, 20
    )
    assert restarted.outcome.status == "complete"
    assert restarted.items == ROWS


@pytest.mark.parametrize("pattern", ["cursor", "page_token"])
def test_incomplete_failed_expiry_cursor_restarts_all_items(pattern):
    source = MutatingUpstream(ROWS, [{"after_page": 1, "op": "expire_cursors"}])
    first = traverse(
        source.adapter(pattern, 3),
        FailureContract(retryable=True, partial_result_allowed=False),
        20,
    )
    assert first.outcome.status == "failed"
    assert first.items == []
    restarted = traverse(
        source.adapter(pattern, 3, resume_cursor=first.resume_cursor), CONTRACT, 20
    )
    assert restarted.outcome.status == "complete"
    assert restarted.items == ROWS


@pytest.mark.parametrize("budget", [0, -1, True, 1.5])
def test_incomplete_invalid_budget(budget):
    with pytest.raises(ValueError):
        traverse(MutatingUpstream([]).adapter("cursor", 3), CONTRACT, budget)
