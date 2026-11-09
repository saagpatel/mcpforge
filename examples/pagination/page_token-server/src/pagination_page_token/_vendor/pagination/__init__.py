"""Provider-independent pagination contracts, adapters, and bounded traversal."""

from .adapter import AdapterDefinition, Page, PaginationAdapter, PaginationError
from .cursor_codec import CursorCodec, InvalidCursorError
from .history import TraversalHistory
from .patterns import CursorAdapter, OffsetAdapter, PageTokenAdapter
from .traverse import TraversalResult, traverse

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
    "TraversalHistory",
    "TraversalResult",
    "traverse",
]
