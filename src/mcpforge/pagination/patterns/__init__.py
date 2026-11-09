"""The three supported pagination patterns and their declarative definitions."""

from mcpforge.pagination.patterns.cursor import CursorAdapter
from mcpforge.pagination.patterns.offset import OffsetAdapter
from mcpforge.pagination.patterns.page_token import PageTokenAdapter

DEFINITIONS = tuple(cls.definition for cls in (CursorAdapter, OffsetAdapter, PageTokenAdapter))

__all__ = ["DEFINITIONS", "CursorAdapter", "OffsetAdapter", "PageTokenAdapter"]
