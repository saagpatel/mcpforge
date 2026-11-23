"""Shared utilities for mcpforge."""

import json
import re
from pathlib import Path
from typing import Any


def read_optional_json_object(path: Path) -> dict[str, Any]:
    """Read a project config, allowing a missing file but reporting unusable content."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (ValueError, OSError) as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Invalid {path}: expected a JSON object")
    return data


def strip_code_fences(text: str) -> str:
    """Remove markdown ``` fences from LLM response."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()
