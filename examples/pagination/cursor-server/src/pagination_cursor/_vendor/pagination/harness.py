"""Deterministic upstream data and mutations; traversal ids are opaque and random."""

from copy import deepcopy
from typing import Any, Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .adapter import Item, PaginationAdapter, Pattern, UpstreamCursorExpired
from .cursor_codec import CursorCodec
from .patterns import CursorAdapter, OffsetAdapter, PageTokenAdapter
from .patterns.cursor import CursorBatch
from .patterns.offset import OffsetBatch
from .patterns.page_token import TokenBatch

DEMO_KEY = b"pagination-harness-demo-key-not-for-production"


class Mutation(BaseModel):
    """Apply once, immediately before the request following after_page."""

    model_config = ConfigDict(extra="forbid", strict=True)
    after_page: int = Field(ge=1)
    op: Literal["insert", "delete", "expire_cursors", "bump_version"]
    item: Item | None = None
    id: int | str | None = None

    @model_validator(mode="after")
    def arguments(self) -> Self:
        if (self.op == "insert") != (self.item is not None):
            raise ValueError("only insert requires item")
        if (self.op == "delete") != (self.id is not None):
            raise ValueError("only delete requires id")
        return self


class MutatingUpstream:
    """Live keyset/offset reads and immutable page-token snapshots.

    Mutations run between requests in script order. Version bumps invalidate
    snapshot continuity; expiry invalidates keysets and upstream tokens. Neither
    operation affects offsets. Initial duplicate ids are allowed for fault tests.
    """

    def __init__(
        self,
        items: list[Item],
        mutations: list[Mutation | dict[str, Any]] | None = None,
        *,
        id_key: str = "id",
        order_key: str = "order",
    ):
        self.id_key = id_key
        self.order_key = order_key
        self.source_id = uuid4().hex
        self.codec = CursorCodec(DEMO_KEY)
        self._items = deepcopy(items)
        self._sort()
        self.mutations = [Mutation.model_validate(m) for m in mutations or []]
        self._applied: set[int] = set()
        self.requests: list[dict[str, Any]] = []
        self.generation = 0
        self.version = 0
        self._token_counter = 0
        self._tokens: dict[str, tuple[list[Item], int]] = {}

    def _key(self, item: Item) -> tuple[Any, Any]:
        return item[self.order_key], item[self.id_key]

    def _sort(self) -> None:
        self._items.sort(key=self._key)

    @property
    def items(self) -> list[Item]:
        return deepcopy(self._items)

    def insert(self, item: Item) -> None:
        if any(row[self.id_key] == item[self.id_key] for row in self._items):
            raise ValueError("insert requires a new identity")
        self._items.append(deepcopy(item))
        self._sort()

    def delete(self, identity: int | str) -> None:
        self._items = [row for row in self._items if row[self.id_key] != identity]

    def expire_cursors(self) -> None:
        self.generation += 1
        self._tokens.clear()

    def bump_version(self) -> None:
        self.version += 1

    def _before_request(self, **request: Any) -> None:
        for index, mutation in enumerate(self.mutations):
            if index not in self._applied and mutation.after_page == len(self.requests):
                if mutation.op == "insert":
                    assert mutation.item is not None
                    self.insert(mutation.item)
                elif mutation.op == "delete":
                    assert mutation.id is not None
                    self.delete(mutation.id)
                elif mutation.op == "expire_cursors":
                    self.expire_cursors()
                else:
                    self.bump_version()
                self._applied.add(index)
        self.requests.append(request)

    def fetch_cursor(
        self, after: tuple[Any, Any] | None, limit: int, generation: int | None
    ) -> CursorBatch:
        self._before_request(pattern="cursor", after=after, limit=limit)
        if generation is not None and generation != self.generation:
            raise UpstreamCursorExpired("keyset generation expired")
        available = [row for row in self._items if after is None or self._key(row) > after]
        return CursorBatch(deepcopy(available[:limit]), len(available) > limit, self.generation)

    def fetch_offset(self, offset: int, limit: int) -> OffsetBatch:
        self._before_request(pattern="offset", offset=offset, limit=limit)
        rows = self._items[offset : offset + limit]
        return OffsetBatch(deepcopy(rows), offset + limit < len(self._items))

    def fetch_token(self, token: str | None, limit: int) -> TokenBatch:
        self._before_request(pattern="page_token", token=token, limit=limit)
        if token is None:
            snapshot, offset = self.items, 0
        elif token not in self._tokens:
            raise UpstreamCursorExpired("snapshot token expired")
        else:
            snapshot, offset = self._tokens[token]
        rows = snapshot[offset : offset + limit]
        next_token = None
        if offset + limit < len(snapshot):
            self._token_counter += 1
            next_token = f"snapshot-token-{self._token_counter}"
            self._tokens[next_token] = snapshot, offset + limit
        return TokenBatch(deepcopy(rows), next_token, self.version)

    def adapter(
        self,
        pattern: Pattern,
        page_size: int,
        *,
        codec: CursorCodec | None = None,
        resume_cursor: str | None = None,
    ) -> PaginationAdapter:
        """Convenience factory. The fixed demo key is ONLY for this synthetic harness."""
        adapter_class = {
            "cursor": CursorAdapter,
            "offset": OffsetAdapter,
            "page_token": PageTokenAdapter,
        }[pattern]
        return adapter_class(
            self,
            codec=codec or self.codec,
            source_id=self.source_id,
            page_size=page_size,
            id_key=self.id_key,
            order_key=self.order_key,
            resume_cursor=resume_cursor,
        )
