"""Shared utilities for mcpforge."""

import re


def strip_code_fences(text: str) -> str:
    """Remove markdown ``` fences from LLM response."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()
