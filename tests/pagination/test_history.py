"""Traversal identity, namespace isolation, replay and bounded-history regressions."""

import pytest

from mcpforge.contracts import FailureContract
from mcpforge.pagination import (
    CursorAdapter,
    CursorCodec,
    InvalidCursorError,
    OffsetAdapter,
    PageTokenAdapter,
    PaginationError,
    TraversalHistory,
    traverse,
)
from mcpforge.pagination.harness import MutatingUpstream

ADAPTERS = [CursorAdapter, OffsetAdapter, PageTokenAdapter]
CONTRACT = FailureContract(retryable=True, partial_result_allowed=True)
ROWS = [{"id": n, "order": n} for n in range(1, 8)]


def configured(cls, source, codec, **kwargs):
    return cls(source, codec=codec, source_id="collection", order_key="order", **kwargs)


@pytest.mark.parametrize("cls", ADAPTERS)
@pytest.mark.parametrize("mismatch", ["collection", "query"])
def test_cursor_rejects_another_collection_or_query_with_same_codec(cls, mismatch):
    codec = CursorCodec(b"shared-session")
    source = MutatingUpstream([{"id": n, "order": n} for n in [10, 20, 30]])
    first = cls(
        source, codec=codec, source_id="A", query={"tenant": "a"}, page_size=2, order_key="order"
    )
    cursor = first.fetch_page(first.initial_state).to_mcp(first)["nextCursor"]
    other = MutatingUpstream([{"id": n, "order": n} for n in [1, 2, 3, 40]])
    with pytest.raises(InvalidCursorError) as raised:
        cls(
            other,
            codec=codec,
            source_id="B" if mismatch == "collection" else "A",
            query={"tenant": "b" if mismatch == "query" else "a"},
            page_size=2,
            order_key="order",
            resume_cursor=cursor,
        )
    assert raised.value.code == -32602
    assert other.requests == []


@pytest.mark.parametrize("cls", ADAPTERS)
def test_query_digest_is_canonical_and_traversal_id_is_authenticated(cls):
    source = MutatingUpstream(ROWS)
    codec = CursorCodec(b"session")
    adapter = configured(cls, source, codec, page_size=2, query={"b": [2], "a": {"x": 1}})
    page = adapter.fetch_page(adapter.initial_state)
    cursor = page.to_mcp(adapter)["nextCursor"]
    envelope = codec.decode(cursor)
    assert envelope["source"]["collection"] == "collection"
    assert len(envelope["source"]["query"]) == 64
    assert "traversal_id" in envelope
    resumed = configured(
        cls, source, codec, page_size=2, query={"a": {"x": 1}, "b": [2]}, resume_cursor=cursor
    )
    assert resumed.traversal_id == adapter.traversal_id
    assert page.items + traverse(resumed, CONTRACT, 20).items == ROWS


@pytest.mark.parametrize("cls", ADAPTERS)
@pytest.mark.parametrize("mode", ["single-call", "resumed-calls", "mcp-pages"])
@pytest.mark.parametrize("page_size", [1, 2])
def test_duplicate_id_at_later_order_is_never_emitted(cls, mode, page_size):
    rows = [{"id": 1, "order": 1}, {"id": 2, "order": 2}, {"id": 3, "order": 3}]
    source = MutatingUpstream([*rows, {"id": 1, "order": 4}])
    codec = CursorCodec(b"session")
    adapter = configured(cls, source, codec, page_size=page_size)
    collected = []
    if mode == "single-call":
        result = traverse(adapter, CONTRACT, 20)
        collected = result.items
        assert result.outcome.status == "incomplete"
        assert result.outcome.failure.kind == "page_shifted"
    else:
        for _ in range(5):
            if mode == "mcp-pages":
                try:
                    response = adapter.fetch_page(adapter.initial_state).to_mcp(adapter)
                except PaginationError as exc:
                    assert exc.kind == "page_shifted"
                    break
                collected.extend(response["items"])
                cursor = response["nextCursor"]
            else:
                result = traverse(adapter, CONTRACT, 1)
                collected.extend(result.items)
                assert result.outcome.failure.kind == "page_shifted"
                if result.resume_cursor is None:
                    break
                cursor = result.resume_cursor
            adapter = configured(cls, source, codec, page_size=page_size, resume_cursor=cursor)
        else:
            pytest.fail("duplicate was never rejected")
    # With size two, reject the entire final page containing id 3 and the duplicate.
    assert collected == rows[: (3 if page_size == 1 else 2)]


@pytest.mark.parametrize("cls", ADAPTERS)
def test_history_is_shared_by_in_process_continuations_and_mcp_pages(cls):
    source = MutatingUpstream([*ROWS[:3], {"id": 1, "order": 4}])
    adapter = configured(cls, source, CursorCodec(b"session"), page_size=1)
    state = adapter.initial_state
    for expected in ROWS[:3]:
        page = adapter.fetch_page(state)
        assert page.items == [expected]
        state = adapter.next_state(page)
    with pytest.raises(PaginationError, match="duplicate id"):
        adapter.fetch_page(state)


@pytest.mark.parametrize("cls", ADAPTERS)
def test_missing_history_on_restart_fails_before_fetching(cls):
    source = MutatingUpstream(ROWS)
    adapter = configured(cls, source, CursorCodec(b"session"), page_size=2)
    cursor = adapter.fetch_page(adapter.initial_state).to_mcp(adapter)["nextCursor"]
    resumed = configured(cls, source, CursorCodec(b"session"), page_size=2, resume_cursor=cursor)
    count = len(source.requests)
    result = traverse(resumed, CONTRACT, 20)
    assert result.items == []
    assert result.outcome.status == "failed"
    assert result.outcome.failure.kind == "page_shifted"
    assert "history unavailable" in result.outcome.failure.detail
    assert result.resume_cursor is None
    assert len(source.requests) == count


@pytest.mark.parametrize("cls", ADAPTERS)
def test_history_can_be_explicitly_shared_by_reconstructed_codecs(cls):
    history = TraversalHistory()
    source = MutatingUpstream(ROWS)
    adapter = configured(cls, source, CursorCodec(b"session", history=history), page_size=2)
    page = adapter.fetch_page(adapter.initial_state)
    resumed = configured(
        cls,
        source,
        CursorCodec(b"session", history=history),
        page_size=2,
        resume_cursor=page.to_mcp(adapter)["nextCursor"],
    )
    assert page.items + traverse(resumed, CONTRACT, 20).items == ROWS


@pytest.mark.parametrize("cls", ADAPTERS)
def test_lru_evicts_untouched_traversal_and_never_recreates_it(cls):
    source = MutatingUpstream(ROWS)
    codec = CursorCodec(b"session", history=TraversalHistory(max_traversals=2))
    first = configured(cls, source, codec, page_size=1)
    first_page = first.fetch_page(first.initial_state)
    second = configured(cls, source, codec, page_size=1)
    second_cursor = second.fetch_page(second.initial_state).to_mcp(second)["nextCursor"]
    # Touch first after second; creation of third must evict second.
    first_next = first.fetch_page(first_page.continuation)
    third = configured(cls, source, codec, page_size=1)
    third.fetch_page(third.initial_state)
    evicted = configured(cls, source, codec, page_size=1, resume_cursor=second_cursor)
    with pytest.raises(PaginationError, match="history unavailable"):
        evicted.fetch_page(evicted.initial_state)
    assert first.fetch_page(first_next.continuation).items == ROWS[2:3]


@pytest.mark.parametrize("cls", ADAPTERS)
def test_id_bound_rejects_whole_page_and_invalidates_history(cls):
    source = MutatingUpstream(ROWS)
    codec = CursorCodec(b"session", history=TraversalHistory(max_ids_per_traversal=3))
    adapter = configured(cls, source, codec, page_size=2)
    result = traverse(adapter, CONTRACT, 20)
    assert result.items == ROWS[:2]
    assert result.outcome.status == "incomplete"
    assert result.outcome.failure.kind == "page_shifted"
    assert "history unavailable" in result.outcome.failure.detail
    assert "bound exceeded" in result.outcome.failure.detail
    assert result.resume_cursor is None
    # A failed insertion cannot leave a smaller, silently usable history behind.
    with pytest.raises(PaginationError, match="history unavailable"):
        adapter.fetch_page(adapter.initial_state)


@pytest.mark.parametrize("cls", ADAPTERS)
def test_exact_id_bound_allows_completion_and_new_traversal_is_independent(cls):
    source = MutatingUpstream(ROWS[:3])
    codec = CursorCodec(b"session", history=TraversalHistory(max_ids_per_traversal=3))
    for _ in range(2):
        result = traverse(configured(cls, source, codec, page_size=2), CONTRACT, 20)
        assert result.outcome.status == "complete"
        assert result.items == ROWS[:3]


@pytest.mark.parametrize("cls", ADAPTERS)
def test_consumed_cursor_cannot_fork_or_replay_even_after_completion(cls):
    source = MutatingUpstream(ROWS[:4])
    codec = CursorCodec(b"session")
    adapter = configured(cls, source, codec, page_size=2)
    cursor = adapter.fetch_page(adapter.initial_state).to_mcp(adapter)["nextCursor"]
    forks = [configured(cls, source, codec, page_size=2, resume_cursor=cursor) for _ in range(2)]
    assert traverse(forks[0], CONTRACT, 20).outcome.status == "complete"
    count = len(source.requests)
    result = traverse(forks[1], CONTRACT, 20)
    assert result.items == []
    assert result.outcome.failure.kind == "page_shifted"
    assert "already consumed" in result.outcome.failure.detail
    assert len(source.requests) == count


class InterleavedSource(MutatingUpstream):
    """Interleave competing fetches deterministically before either is accepted."""

    hook = None

    def _before_request(self, **request):
        super()._before_request(**request)
        if self.hook is not None:
            hook, self.hook = self.hook, None
            hook()


@pytest.mark.parametrize("cls", ADAPTERS)
def test_competing_resumes_can_only_accept_one_page(cls):
    source = InterleavedSource(ROWS)
    codec = CursorCodec(b"session")
    first = configured(cls, source, codec, page_size=2)
    cursor = first.fetch_page(first.initial_state).to_mcp(first)["nextCursor"]
    winner = configured(cls, source, codec, page_size=2, resume_cursor=cursor)
    loser = configured(cls, source, codec, page_size=2, resume_cursor=cursor)
    accepted = []
    source.hook = lambda: accepted.append(winner.fetch_page(winner.initial_state))
    with pytest.raises(PaginationError, match="already consumed"):
        loser.fetch_page(loser.initial_state)
    assert accepted[0].items == ROWS[2:4]
    assert winner.fetch_page(accepted[0].continuation).items == ROWS[4:6]


@pytest.mark.parametrize("cls", ADAPTERS)
def test_failed_result_restart_mints_fresh_traversal_identity(cls):
    source = MutatingUpstream(ROWS)
    codec = CursorCodec(b"session")
    adapter = configured(cls, source, codec, page_size=2)
    result = traverse(adapter, FailureContract(retryable=True, partial_result_allowed=False), 1)
    assert codec.decode(result.resume_cursor)["traversal_id"] != adapter.traversal_id
    restarted = configured(cls, source, codec, page_size=2, resume_cursor=result.resume_cursor)
    assert traverse(restarted, CONTRACT, 20).items == ROWS


def test_keyset_expiry_refresh_preserves_identity_history():
    source = MutatingUpstream(
        [*ROWS[:3], {"id": 1, "order": 4}], [{"after_page": 1, "op": "expire_cursors"}]
    )
    codec = CursorCodec(b"session")
    adapter = configured(CursorAdapter, source, codec, page_size=1)
    expired = traverse(adapter, CONTRACT, 20)
    assert expired.outcome.failure.kind == "cursor_expired"
    assert expired.items == ROWS[:1]
    assert codec.decode(expired.resume_cursor)["traversal_id"] == adapter.traversal_id
    resumed = configured(
        CursorAdapter, source, codec, page_size=1, resume_cursor=expired.resume_cursor
    )
    result = traverse(resumed, CONTRACT, 20)
    assert result.outcome.failure.kind == "page_shifted"
    assert expired.items + result.items == ROWS[:3]


@pytest.mark.parametrize("bound", [0, -1, True, 1.5])
@pytest.mark.parametrize("name", ["max_traversals", "max_ids_per_traversal"])
def test_history_rejects_invalid_bounds(name, bound):
    with pytest.raises(ValueError, match="positive integers"):
        TraversalHistory(**{name: bound})


@pytest.mark.parametrize("source_id", ["", None, 1])
def test_stable_source_id_is_required(source_id):
    with pytest.raises(ValueError, match="source_id"):
        CursorAdapter(MutatingUpstream([]), codec=CursorCodec(b"session"), source_id=source_id)


@pytest.mark.parametrize("query", [[1], {1: "value"}, {"x": (1, 2)}, {"x": float("nan")}])
def test_query_must_be_unambiguous_json_object(query):
    with pytest.raises(ValueError, match="JSON-compatible"):
        configured(CursorAdapter, MutatingUpstream([]), CursorCodec(b"session"), query=query)


@pytest.mark.parametrize("cls", ADAPTERS)
@pytest.mark.parametrize("field,value", [("traversal_id", ""), ("traversal_id", 1), ("source", {})])
def test_malformed_signed_traversal_binding_is_invalid_params(cls, field, value):
    source = MutatingUpstream(ROWS)
    codec = CursorCodec(b"session")
    first = configured(cls, source, codec, page_size=2)
    envelope = codec.decode(first.fetch_page(first.initial_state).to_mcp(first)["nextCursor"])
    envelope[field] = value
    with pytest.raises(InvalidCursorError) as raised:
        configured(cls, source, codec, page_size=2, resume_cursor=codec.encode(envelope))
    assert raised.value.code == -32602


@pytest.mark.parametrize("cls", ADAPTERS)
def test_definition_documents_history_bounds_restart_and_query_binding(cls):
    assert "128" in cls.definition.incompleteness_detection
    assert "10,000" in cls.definition.incompleteness_detection
    assert "LRU" in cls.definition.incompleteness_detection
    assert "history unavailable" in cls.definition.incompleteness_detection
    assert "restart" in cls.definition.incompleteness_detection
    assert "collection, query" in cls.definition.cursor_validity_rule
