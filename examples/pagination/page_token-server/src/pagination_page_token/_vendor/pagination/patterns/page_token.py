"""Opaque upstream tokens bound to an immutable snapshot version."""

from dataclasses import dataclass
from typing import Any, Protocol, Self

from pydantic import BaseModel, ConfigDict, model_validator

from ..adapter import (
    AdapterBase,
    AdapterDefinition,
    Item,
    Page,
    PaginationError,
    State,
    UpstreamCursorExpired,
)


class TokenState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    token: str | None = None
    version: int | str | None = None

    @model_validator(mode="after")
    def snapshot_required(self) -> Self:
        if (self.token is None) != (self.version is None) or self.token == "":
            raise ValueError("a nonempty token and snapshot version must appear together")
        return self


@dataclass
class TokenBatch:
    items: list[Item]
    next_token: str | None
    version: int | str


class TokenSource(Protocol):
    def fetch_token(self, token: str | None, limit: int) -> TokenBatch: ...


class PageTokenAdapter(AdapterBase):
    definition = AdapterDefinition(
        pattern="page_token",
        cursor_validity_rule="Session cursor; upstream token bound to snapshot version.",
        ordering_guarantee="Snapshot order is ascending immutable (order_key, id_key).",
        resume_behaviour="Expiry/version change starts a NEW traversal; do not append to partials.",
        incompleteness_detection="Expired token, version change, duplicates, or order regression.",
    )
    state_model = TokenState

    def __init__(self, source: TokenSource, **kwargs: Any):
        super().__init__(**kwargs)
        self.source = source

    def fetch_page(self, state: State) -> Page:
        state = self.validate_state(state)
        try:
            batch = self.source.fetch_token(state["token"], self.page_size)
        except UpstreamCursorExpired as exc:
            raise PaginationError("cursor_expired", str(exc), {}) from exc
        if state["version"] is not None and state["version"] != batch.version:
            raise PaginationError("page_shifted", "snapshot version changed", {})
        self.validate_items(batch.items)
        if batch.next_token is not None and (not batch.items or batch.next_token == state["token"]):
            raise PaginationError("page_shifted", "upstream token made no progress", {})
        continuation = (
            {"token": batch.next_token, "version": batch.version}
            if batch.next_token is not None
            else None
        )
        return Page(batch.items, continuation)
