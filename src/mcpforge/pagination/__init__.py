"""Provider-independent pagination contracts, adapters, and bounded traversal."""

from mcpforge.pagination.adapter import AdapterDefinition, Page, PaginationAdapter, PaginationError
from mcpforge.pagination.cursor_codec import CursorCodec, InvalidCursorError
from mcpforge.pagination.patterns import CursorAdapter, OffsetAdapter, PageTokenAdapter
from mcpforge.pagination.traverse import TraversalResult, traverse

__all__ = [
    "AdapterDefinition",
    "CursorAdapter",
    "CursorCodec",
    "InvalidCursorError",
    "OffsetAdapter",
    "Page",
    "PageTokenAdapter",
    "PaginationAdapter",
    "PaginationError",
    "TraversalResult",
    "traverse",
]
