"""Offset pagination with an overlap boundary and conservative re-anchoring."""

from dataclasses import dataclass
from typing import Any, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mcpforge.pagination.adapter import (
    AdapterBase,
    AdapterDefinition,
    Item,
    Page,
    PaginationError,
    State,
)
from mcpforge.pagination.cursor_codec import InvalidCursorError


class OffsetState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    offset: int = Field(default=0, ge=0)
    last_item: Item | None = None

    @model_validator(mode="after")
    def boundary_required(self) -> Self:
        if (self.offset == 0) != (self.last_item is None):
            raise ValueError("nonzero offsets require a boundary item")
        return self


@dataclass
class OffsetBatch:
    items: list[Item]
    has_more: bool


class OffsetSource(Protocol):
    def fetch_offset(self, offset: int, limit: int) -> OffsetBatch: ...


class OffsetAdapter(AdapterBase):
    definition = AdapterDefinition(
        pattern="offset",
        cursor_validity_rule="Authenticated session cursor with an unchanged overlap boundary.",
        ordering_guarantee="Ascending immutable (order_key, id_key), verified on every page.",
        resume_behaviour="Restart traversal if the overlap boundary cannot be found.",
        incompleteness_detection=(
            "Fetch offset-1 with limit+1; locate the unchanged last item and discard overlap. "
            "Missing or changed boundary, duplicate ids, or order regression means page_shifted."
        ),
    )
    state_model = OffsetState

    def __init__(self, source: OffsetSource, **kwargs: Any):
        super().__init__(**kwargs)
        self.source = source

    def validate_state(self, state: State) -> State:
        state = super().validate_state(state)
        if state["last_item"] is not None:
            try:
                self.validate_items([state["last_item"]])
            except PaginationError as exc:
                raise InvalidCursorError("invalid offset boundary item") from exc
        return state

    def fetch_page(self, state: State) -> Page:
        state = self.validate_state(state)
        overlap = state["last_item"] is not None
        start = state["offset"] - int(overlap)
        batch = self.source.fetch_offset(start, self.page_size + int(overlap))
        self.validate_items(batch.items)
        items = batch.items
        if overlap:
            boundary = state["last_item"]
            matches = [
                i for i, item in enumerate(items) if item[self.id_key] == boundary[self.id_key]
            ]
            if len(matches) != 1 or items[matches[0]] != boundary:
                raise PaginationError("page_shifted", "offset boundary cannot be safely located")
            anchor = matches[0]
            items = items[anchor + 1 :]
        if batch.has_more and not items:
            # A boundary at the end advances the physical offset without emitting items.
            if not overlap or matches[0] != len(batch.items) - 1:
                raise PaginationError("page_shifted", "empty offset page claims more items")
        continuation = None
        if batch.has_more:
            continuation = {
                "offset": start + len(batch.items),
                "last_item": items[-1] if items else state["last_item"],
            }
        return Page(items, continuation)
