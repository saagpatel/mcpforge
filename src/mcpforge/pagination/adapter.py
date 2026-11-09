"""Public adapter contract and shared page/state primitives."""

from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from mcpforge.pagination.cursor_codec import CursorCodec, InvalidCursorError

Pattern = Literal["cursor", "offset", "page_token"]
PaginationKind = Literal["cursor_expired", "page_shifted"]
Item = dict[str, Any]
State = dict[str, Any]


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
    """Shared configuration and pattern-bound cursor handling."""

    definition: AdapterDefinition
    state_model: type[BaseModel]

    @property
    def pattern(self) -> Pattern:
        return self.definition.pattern

    def __init__(
        self,
        *,
        codec: CursorCodec,
        page_size: int = 50,
        id_key: str = "id",
        order_key: str = "id",
        resume_cursor: str | None = None,
    ):
        if type(page_size) is not int or page_size < 1:
            raise ValueError("page_size must be a positive integer")
        self.codec = codec
        self.page_size = page_size
        self.id_key = id_key
        self.order_key = order_key
        self.initial_state = self.validate_state({})
        if resume_cursor is not None:
            envelope = codec.decode(resume_cursor)
            if (
                set(envelope) != {"pattern", "position", "configuration"}
                or envelope["pattern"] != self.pattern
                or envelope["configuration"] != [page_size, id_key, order_key]
            ):
                raise InvalidCursorError("cursor belongs to another adapter configuration")
            self.initial_state = self.validate_state(envelope["position"])

    def validate_state(self, state: State) -> State:
        try:
            return self.state_model.model_validate(state).model_dump(mode="json")
        except ValidationError as exc:
            raise InvalidCursorError("invalid adapter state") from exc

    def encode_state(self, state: State) -> str:
        return self.codec.encode(
            {
                "pattern": self.pattern,
                "position": self.validate_state(state),
                "configuration": [self.page_size, self.id_key, self.order_key],
            }
        )

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
