"""Keyset pagination using the last (order key, identity) pair."""

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import Field

from mcpforge.pagination.adapter import (
    HISTORY_RULE,
    AdapterBase,
    AdapterDefinition,
    AdapterState,
    Item,
    Page,
    PaginationError,
    State,
    UpstreamCursorExpired,
)


class CursorState(AdapterState):
    after: list[int | float | str] | None = Field(default=None, min_length=2, max_length=2)
    generation: int | None = Field(default=None, ge=0)


@dataclass
class CursorBatch:
    items: list[Item]
    has_more: bool
    generation: int


class CursorSource(Protocol):
    def fetch_cursor(
        self, after: tuple[Any, Any] | None, limit: int, generation: int | None
    ) -> CursorBatch: ...


class CursorAdapter(AdapterBase):
    definition = AdapterDefinition(
        pattern="cursor",
        cursor_validity_rule=(
            "Authenticated session cursor bound to collection, query, configuration and traversal; "
            "upstream generation must remain valid."
        ),
        ordering_guarantee=(
            "Strict total order on immutable, comparable (order_key, id_key), with unique ids. "
            "The last accepted pair detects regressions; session history detects repeated ids."
        ),
        resume_behaviour="Resume after the last key in the current generation, even after expiry.",
        incompleteness_detection=(
            "Expired generation, duplicate ids, or nonascending items. " + HISTORY_RULE
        ),
    )
    state_model = CursorState

    def __init__(self, source: CursorSource, **kwargs: Any):
        super().__init__(**kwargs)
        self.source = source

    def _fetch_page(self, state: State) -> Page:
        state = self.validate_state(state)
        after = tuple(state["after"]) if state["after"] is not None else None
        try:
            batch = self.source.fetch_cursor(after, self.page_size + 1, state["generation"])
        except UpstreamCursorExpired as exc:
            raise PaginationError(
                "cursor_expired", str(exc), {**state, "generation": None}
            ) from exc
        self.validate_items(batch.items, after)
        # Validate the lookahead before accepting a boundary that a strict-after
        # query could otherwise skip. It is fetched again, never emitted here.
        items = batch.items[: self.page_size]
        continuation = None
        if batch.has_more or len(batch.items) > self.page_size:
            if not items:
                raise PaginationError("page_shifted", "empty keyset page claims more items", state)
            continuation = {
                "after": list(self.item_key(items[-1])),
                "generation": batch.generation,
                "boundary": list(self.item_key(items[-1])),
            }
        return Page(items, continuation)
