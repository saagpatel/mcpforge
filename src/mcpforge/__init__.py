"""mcpforge — Generate FastMCP 3.x MCP servers from plain-English descriptions."""

from mcpforge.api_client import DEFAULT_MODEL
from mcpforge.models import (
    PromptDef,
    ResourceDef,
    ServerPlan,
    ToolDef,
    ToolParam,
    ValidationResult,
)

__version__ = "0.2.0"
__all__ = [
    "PromptDef",
    "ResourceDef",
    "ServerPlan",
    "ToolDef",
    "ToolParam",
    "ValidationResult",
    "DEFAULT_MODEL",
    "__version__",
]
