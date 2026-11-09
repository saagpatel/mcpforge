"""Public adapter contract and shared page/state primitives."""

import hashlib
import json
import re
from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mcpforge.pagination.cursor_codec import CursorCodec, InvalidCursorError
from mcpforge.pagination.history import HistoryError

Pattern = Literal["cursor", "offset", "page_token"]
PaginationKind = Literal["cursor_expired", "page_shifted"]
Item = dict[str, Any]
State = dict[str, Any]
HISTORY_RULE = (
    "Session history defaults to 128 traversals (LRU) and 10,000 emitted ids per traversal; "
    "configure TraversalHistory and share it via CursorCodec across calls. Missing history "
    "after eviction/restart or an exceeded id bound fails explicitly with page_shifted "
    "and history unavailable; start a new traversal rather than append a restart. "
    "Consumed positions cannot be replayed."
)


class AdapterState(BaseModel):
    """Last ordering boundary, authenticated with the upstream position."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    boundary: list[int | float | str] | None = Field(default=None, min_length=2, max_length=2)


class AdapterDefinition(BaseModel):
    """Single source of adapter semantics for future generated documentation."""

    model_config = ConfigDict(frozen=True)
    pattern: Pattern
    cursor_validity_rule: str
    ordering_guarantee: str
    resume_behaviour: str
    incompleteness_detection: str


@dataclass
class Page:
    """One validated page; absent continuation means the last page."""

    items: list[Item]
    continuation: State | None = None

    def to_mcp(self, adapter: "PaginationAdapter") -> dict[str, Any]:
        result: dict[str, Any] = {"items": self.items}
        if self.continuation is not None:
            result["nextCursor"] = adapter.encode_state(self.continuation)
        return result


class PaginationError(Exception):
    """An upstream pagination failure, resolved by the traversal contract."""

    def __init__(self, kind: PaginationKind, detail: str, resume_state: State | None = None):
        super().__init__(detail)
        self.kind = kind
        self.resume_state = resume_state


class UpstreamCursorExpired(Exception):
    """Sources raise this for a well-formed cursor that is no longer valid."""


class PaginationAdapter(Protocol):
    @property
    def pattern(self) -> Pattern: ...

    definition: AdapterDefinition
    id_key: str
    order_key: str
    initial_state: State

    def fetch_page(self, state: State) -> Page: ...
    def next_state(self, page: Page) -> State | None: ...
    def encode_state(self, state: State) -> str: ...


class AdapterBase:
    """Source/query-bound cursors and atomic page acceptance on every public path.

    Callers must supply a stable collection id and all effective query parameters
    (including tenant/filter scope), and retain the codec/history across calls.
    """

    definition: AdapterDefinition
    state_model: type[BaseModel]

    @property
    def pattern(self) -> Pattern:
        return self.definition.pattern

    def __init__(
        self,
        *,
        codec: CursorCodec,
        source_id: str,
        query: dict[str, Any] | None = None,
        page_size: int = 50,
        id_key: str = "id",
        order_key: str = "id",
        resume_cursor: str | None = None,
    ):
        if type(page_size) is not int or page_size < 1:
            raise ValueError("page_size must be a positive integer")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source_id must be a nonempty stable collection identifier")
        query = query if query is not None else {}
        try:
            encoded_query = json.dumps(
                query, sort_keys=True, allow_nan=False, separators=(",", ":")
            )
            if not isinstance(query, dict) or json.loads(encoded_query) != query:
                raise ValueError("query must contain JSON objects with string keys")
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("query must be a JSON-compatible parameter object") from exc
        self.codec = codec
        self.history = codec.history
        self.source_namespace = {
            "collection": source_id,
            "query": hashlib.sha256(encoded_query.encode("utf-8")).hexdigest(),
        }
        self.page_size = page_size
        self.id_key = id_key
        self.order_key = order_key
        self.initial_state = self.validate_state({})
        if resume_cursor is not None:
            envelope = codec.decode(resume_cursor)
            if (
                set(envelope) != {"pattern", "position", "configuration", "source", "traversal_id"}
                or envelope["pattern"] != self.pattern
                or envelope["configuration"] != [page_size, id_key, order_key]
                or envelope["source"] != self.source_namespace
                or not isinstance(envelope["traversal_id"], str)
                or re.fullmatch(r"[0-9a-f]{32}", envelope["traversal_id"]) is None
            ):
                raise InvalidCursorError("cursor belongs to another source, query or configuration")
            self.initial_state = self.validate_state(envelope["position"])
            self.traversal_id = envelope["traversal_id"]
        else:
            self.traversal_id = self.history.create(self.initial_state)

    def validate_state(self, state: State) -> State:
        try:
            return self.state_model.model_validate(state).model_dump(mode="json")
        except ValidationError as exc:
            raise InvalidCursorError("invalid adapter state") from exc

    def encode_state(self, state: State) -> str:
        # An explicit restart must not inherit the previous traversal's ids.
        position = self.validate_state(state)
        traversal_id = self.history.create(position) if not state else self.traversal_id
        return self.codec.encode(
            {
                "pattern": self.pattern,
                "position": position,
                "configuration": [self.page_size, self.id_key, self.order_key],
                "source": self.source_namespace,
                "traversal_id": traversal_id,
            }
        )

    def fetch_page(self, state: State) -> Page:
        state = self.validate_state(state)
        try:
            self.history.check(self.traversal_id, state)
            try:
                page = self._fetch_page(state)
            except PaginationError as exc:
                if exc.resume_state:
                    replacement = self.validate_state(exc.resume_state)
                    self.history.reposition(self.traversal_id, state, replacement)
                raise
            boundary = tuple(state["boundary"]) if state["boundary"] is not None else None
            self.validate_items(page.items, boundary)
            continuation = (
                self.validate_state(page.continuation) if page.continuation is not None else None
            )
            if continuation == state:
                raise PaginationError("page_shifted", "adapter state made no progress")
            self.history.accept(
                self.traversal_id,
                state,
                {item[self.id_key] for item in page.items},
                continuation,
            )
            page.continuation = continuation
            return page
        except HistoryError as exc:
            raise PaginationError("page_shifted", str(exc)) from exc

    def _fetch_page(self, state: State) -> Page:
        raise NotImplementedError

    def next_state(self, page: Page) -> State | None:
        return page.continuation

    def item_key(self, item: Item) -> tuple[Any, Any]:
        return item[self.order_key], item[self.id_key]

    def validate_items(self, items: list[Item], after: tuple[Any, Any] | None = None) -> None:
        """Validate raw source pages, including overlap that may be discarded."""
        seen: set[Any] = set()
        previous = after
        try:
            for item in items:
                key = self.item_key(item)
                identity = item[self.id_key]
                if any(type(value) not in (int, float, str) for value in key):
                    raise PaginationError("page_shifted", "identity and order keys must be scalars")
                if any(isinstance(value, float) and not isfinite(value) for value in key):
                    raise PaginationError("page_shifted", "nonfinite ordering key")
                if identity in seen or (previous is not None and key <= previous):
                    raise PaginationError(
                        "page_shifted", "duplicate id or nonascending source page"
                    )
                seen.add(identity)
                previous = key
        except (KeyError, TypeError) as exc:
            raise PaginationError("page_shifted", "invalid identity or ordering keys") from exc
