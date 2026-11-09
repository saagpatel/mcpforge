"""Adapter definitions, upstream protocol handling, and conservative offset recovery."""

from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from mcpforge.contracts import FailureContract
from mcpforge.pagination import CursorCodec, traverse
from mcpforge.pagination.harness import MutatingUpstream
from mcpforge.pagination.patterns import DEFINITIONS, CursorAdapter, OffsetAdapter, PageTokenAdapter
from mcpforge.pagination.patterns.cursor import CursorBatch
from mcpforge.pagination.patterns.offset import OffsetBatch
from mcpforge.pagination.patterns.page_token import TokenBatch

CONTRACT = FailureContract(retryable=True, partial_result_allowed=True)
ROWS = [{"id": n, "order": n} for n in range(8)]


def test_adapter_declarative_definitions_are_single_source():
    assert {definition.pattern for definition in DEFINITIONS} == {"cursor", "offset", "page_token"}
    for cls in (CursorAdapter, OffsetAdapter, PageTokenAdapter):
        adapter = cls(MutatingUpstream([]), codec=CursorCodec(b"demo"))
        assert adapter.pattern == adapter.definition.pattern
        assert adapter.definition in DEFINITIONS
        assert all(adapter.definition.model_dump().values())
        with pytest.raises((ValidationError, FrozenInstanceError)):
            adapter.definition.pattern = "offset"


def test_adapter_offset_patterns_request_overlap_and_reanchor():
    source = MutatingUpstream(
        ROWS, [{"after_page": 1, "op": "insert", "item": {"id": -1, "order": -1}}]
    )
    result = traverse(source.adapter("offset", 3), CONTRACT, 20)
    assert result.outcome.status == "complete"
    assert result.items == ROWS
    assert [(r["offset"], r["limit"]) for r in source.requests] == [(0, 3), (2, 4), (5, 4)]


def test_adapter_offset_patterns_anchor_at_end_makes_progress():
    source = MutatingUpstream(
        ROWS[:3], [{"after_page": 1, "op": "insert", "item": {"id": -1, "order": -1}}]
    )
    result = traverse(source.adapter("offset", 1), CONTRACT, 20)
    assert result.outcome.status == "complete"
    assert result.items == ROWS[:3]


class BadSource:
    """A sorted source that wrongly repeats an identity at a later order key."""

    def __init__(self, mode):
        self.mode = mode
        self.calls = 0

    def rows(self):
        self.calls += 1
        if self.calls == 1:
            return [{"id": 1, "order": 1}]
        if self.mode == "duplicate":
            return [{"id": 1, "order": 2}]
        if self.mode == "within-page":
            return [{"id": 2, "order": 2}, {"id": 2, "order": 3}]
        if self.mode == "missing-key":
            return [{}]
        if self.mode == "incomparable-key":
            return [{"id": 2, "order": []}]
        if self.mode == "nonfinite-key":
            return [{"id": 2, "order": float("nan")}]
        return [{"id": 2, "order": 0}]

    def fetch_cursor(self, after, limit, generation):
        return CursorBatch(self.rows(), self.calls == 1, 0)

    def fetch_offset(self, offset, limit):
        rows = self.rows()
        return OffsetBatch(
            ([{"id": 1, "order": 1}] if self.calls > 1 else []) + rows, self.calls == 1
        )

    def fetch_token(self, token, limit):
        return TokenBatch(self.rows(), "next" if self.calls == 1 else None, 0)


@pytest.mark.parametrize("cls", [CursorAdapter, OffsetAdapter, PageTokenAdapter])
@pytest.mark.parametrize(
    "mode",
    [
        "duplicate",
        "within-page",
        "regression",
        "missing-key",
        "incomparable-key",
        "nonfinite-key",
    ],
)
def test_adapter_incomplete_rejects_duplicates_and_regressions(cls, mode):
    result = traverse(
        cls(BadSource(mode), codec=CursorCodec(b"demo"), order_key="order"), CONTRACT, 10
    )
    assert result.outcome.status == "incomplete"
    assert result.outcome.failure.kind == "page_shifted"
    assert result.items == [{"id": 1, "order": 1}]


def test_adapter_patterns_float_order_keys_survive_cursor_round_trip():
    source = MutatingUpstream([{"id": n, "order": n / 10} for n in range(4)])
    adapter = source.adapter("cursor", 2)
    first = adapter.fetch_page(adapter.initial_state)
    resumed = source.adapter("cursor", 2, resume_cursor=first.to_mcp(adapter)["nextCursor"])
    assert first.items + traverse(resumed, CONTRACT, 10).items == source.items


@pytest.mark.parametrize("page_size", [1, 2])
def test_adapter_cursor_rejects_duplicate_at_keyset_boundary(page_size):
    source = MutatingUpstream([{"id": 1, "order": 1}, {"id": 1, "order": 1}])
    result = traverse(source.adapter("cursor", page_size), CONTRACT, 10)
    assert result.outcome.status == "failed"
    assert result.outcome.failure.kind == "page_shifted"
    assert result.items == []


def test_adapter_cursor_validates_lookahead_without_emitting_it():
    source = MutatingUpstream(ROWS[:3])
    adapter = source.adapter("cursor", 2)
    page = adapter.fetch_page(adapter.initial_state)
    assert source.requests[0]["limit"] == 3
    assert page.items == ROWS[:2]
    assert page.continuation["after"] == [1, 1]
    resumed = source.adapter("cursor", 2, resume_cursor=page.to_mcp(adapter)["nextCursor"])
    assert traverse(resumed, CONTRACT, 10).items == ROWS[2:3]


@pytest.mark.parametrize("pattern", ["cursor", "offset", "page_token"])
def test_adapter_patterns_support_custom_identity_and_order_keys(pattern):
    rows = [{"uid": str(n), "rank": n // 2} for n in range(8)]
    source = MutatingUpstream(rows, id_key="uid", order_key="rank")
    result = traverse(source.adapter(pattern, 2), CONTRACT, 10)
    assert result.outcome.status == "complete"
    assert result.items == rows


@pytest.mark.parametrize("size", [0, -1, True, 1.5])
def test_adapter_invalid_page_size(size):
    with pytest.raises(ValueError):
        MutatingUpstream([]).adapter("cursor", size)
