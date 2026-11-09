"""The three supported pagination patterns and their declarative definitions."""

from .cursor import CursorAdapter
from .offset import OffsetAdapter
from .page_token import PageTokenAdapter

DEFINITIONS = tuple(cls.definition for cls in (CursorAdapter, OffsetAdapter, PageTokenAdapter))

__all__ = ["DEFINITIONS", "CursorAdapter", "OffsetAdapter", "PageTokenAdapter"]
