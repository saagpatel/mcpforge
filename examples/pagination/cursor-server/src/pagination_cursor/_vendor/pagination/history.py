"""Bounded, process-local identity history shared by a session's adapters."""

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any
from uuid import uuid4


class HistoryError(Exception):
    """Continuing this traversal cannot safely expose another page."""


@dataclass
class _Traversal:
    position: dict[str, Any] | None
    identities: set[int | float | str] = field(default_factory=set)


class TraversalHistory:
    """LRU store; eviction/restart never recreates an existing traversal.

    Defaults retain at most 128 traversals and 10,000 emitted ids per traversal.
    Share this store (or its owning CursorCodec) across resumed calls. Completed
    traversals remain bounded replay guards until evicted. Position checks and
    page acceptance are atomic so competing resumes cannot both emit a page.
    """

    def __init__(self, *, max_traversals: int = 128, max_ids_per_traversal: int = 10_000):
        for bound in (max_traversals, max_ids_per_traversal):
            if type(bound) is not int or bound < 1:
                raise ValueError("history bounds must be positive integers")
        self.max_traversals = max_traversals
        self.max_ids_per_traversal = max_ids_per_traversal
        self._traversals: OrderedDict[str, _Traversal] = OrderedDict()
        self._lock = RLock()

    def create(self, position: dict[str, Any]) -> str:
        with self._lock:
            traversal_id = uuid4().hex
            self._traversals[traversal_id] = _Traversal(deepcopy(position))
            if len(self._traversals) > self.max_traversals:
                self._traversals.popitem(last=False)
            return traversal_id

    def _current(self, traversal_id: str, position: dict[str, Any]) -> _Traversal:
        entry = self._traversals.get(traversal_id)
        if entry is None:
            raise HistoryError("traversal history unavailable (evicted or process restarted)")
        if entry.position != position:
            raise HistoryError("traversal position already consumed or belongs to another page")
        self._traversals.move_to_end(traversal_id)
        return entry

    def check(self, traversal_id: str, position: dict[str, Any]) -> None:
        with self._lock:
            self._current(traversal_id, position)

    def reposition(
        self, traversal_id: str, position: dict[str, Any], replacement: dict[str, Any]
    ) -> None:
        """Refresh an expired keyset generation without forgetting emitted ids."""
        with self._lock:
            self._current(traversal_id, position).position = deepcopy(replacement)

    def accept(
        self,
        traversal_id: str,
        position: dict[str, Any],
        identities: set[int | float | str],
        continuation: dict[str, Any] | None,
    ) -> None:
        with self._lock:
            entry = self._current(traversal_id, position)
            if entry.identities & identities:
                raise HistoryError("duplicate id already emitted in this traversal")
            if len(entry.identities) + len(identities) > self.max_ids_per_traversal:
                del self._traversals[traversal_id]
                raise HistoryError("traversal history unavailable (identity bound exceeded)")
            entry.identities.update(identities)
            entry.position = deepcopy(continuation)
