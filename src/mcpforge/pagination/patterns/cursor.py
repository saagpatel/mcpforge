"""Keyset pagination using the last (order key, identity) pair."""

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from mcpforge.pagination.adapter import (
    AdapterBase,
    AdapterDefinition,
    Item,
    Page,
    PaginationError,
    State,
    UpstreamCursorExpired,
)


class CursorState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
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
        cursor_validity_rule="Authenticated session cursor; upstream generation must remain valid.",
        ordering_guarantee="Ascending (order_key, id_key); keys must be immutable and comparable.",
        resume_behaviour="Resume after the last key in the current generation, even after expiry.",
        incompleteness_detection="Expired generation, duplicate ids, or nonascending items.",
    )
    state_model = CursorState

    def __init__(self, source: CursorSource, **kwargs: Any):
        super().__init__(**kwargs)
        self.source = source

    def fetch_page(self, state: State) -> Page:
        state = self.validate_state(state)
        after = tuple(state["after"]) if state["after"] is not None else None
        try:
            batch = self.source.fetch_cursor(after, self.page_size, state["generation"])
        except UpstreamCursorExpired as exc:
            raise PaginationError(
                "cursor_expired", str(exc), {**state, "generation": None}
            ) from exc
        self.validate_items(batch.items, after)
        continuation = None
        if batch.has_more:
            if not batch.items:
                raise PaginationError("page_shifted", "empty keyset page claims more items", state)
            continuation = {
                "after": list(self.item_key(batch.items[-1])),
                "generation": batch.generation,
            }
        return Page(batch.items, continuation)
