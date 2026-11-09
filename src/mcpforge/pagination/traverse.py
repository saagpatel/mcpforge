"""Bounded traversal with atomic page acceptance and shared failure semantics."""

from dataclasses import dataclass
from typing import Any

from mcpforge.contracts import FailureContract, ToolOutcome, resolve_outcome
from mcpforge.pagination.adapter import Item, PaginationAdapter, PaginationError, State


@dataclass
class TraversalResult:
    """Pages counts fetched pages, including rejected pages, but not raised fetches.

    Failed outcomes expose no items and their cursors restart from the beginning.
    Incomplete outcomes follow the adapter definition; snapshot restarts must not
    be concatenated to a previous partial result.
    """

    items: list[Item]
    outcome: ToolOutcome
    pages: int
    resume_cursor: str | None


def traverse(
    adapter: PaginationAdapter, contract: FailureContract, max_pages: int
) -> TraversalResult:
    """Traverse until exhaustion or a pagination failure; never accept a bad page.

    A page budget exhausted before the last page is page_shifted: completeness
    could not be established. The resume cursor points at the next unconsumed page.
    """
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError("max_pages must be a positive integer")
    items: list[Item] = []
    seen: set[Any] = set()
    pages = 0
    state: State = adapter.initial_state
    boundary = state.get("boundary")
    previous: tuple[Any, Any] | None = tuple(boundary) if boundary is not None else None

    def failure(exc: PaginationError) -> TraversalResult:
        resume_state = exc.resume_state
        if resume_state is not None and not (items and contract.partial_result_allowed):
            # Nothing is exposed on failure, so resuming past accepted pages would skip items.
            resume_state = {}
        resume = adapter.encode_state(resume_state) if resume_state is not None else None
        outcome = resolve_outcome(contract, exc.kind, bool(items), str(exc), resume)
        return TraversalResult(
            items if outcome.status == "incomplete" else [], outcome, pages, resume
        )

    for _ in range(max_pages):
        try:
            page = adapter.fetch_page(state)
            pages += 1
            page_ids: set[Any] = set()
            last = previous
            try:
                for item in page.items:
                    identity = item[adapter.id_key]
                    key = item[adapter.order_key], identity
                    if (
                        identity in seen
                        or identity in page_ids
                        or (last is not None and key <= last)
                    ):
                        raise PaginationError("page_shifted", "duplicate id or nonascending items")
                    page_ids.add(identity)
                    last = key
            except (KeyError, TypeError) as exc:
                raise PaginationError("page_shifted", "invalid identity or ordering keys") from exc
            items.extend(page.items)
            seen.update(page_ids)
            previous = last
            next_state = adapter.next_state(page)
            if next_state is None:
                return TraversalResult(
                    items, ToolOutcome(status="complete", failure=None), pages, None
                )
            if next_state == state:
                raise PaginationError("page_shifted", "adapter state made no progress")
            state = next_state
        except PaginationError as exc:
            return failure(exc)
    return failure(PaginationError("page_shifted", "page budget exhausted", state))
