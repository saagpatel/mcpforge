"""mcpforge — Generate FastMCP 3.x MCP servers from plain-English descriptions."""

from mcpforge.models import (
    ResourceDef,
    ServerPlan,
    ToolDef,
    ToolParam,
    ValidationResult,
)

__version__ = "0.2.0"
__all__ = [
    "ResourceDef",
    "ServerPlan",
    "ToolDef",
    "ToolParam",
    "ValidationResult",
    "__version__",
]
