"""Credential-free SafeForge echo fixture."""

from fastmcp import FastMCP

mcp = FastMCP("SafeForge Echo")


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def echo(message: str) -> dict:
    """Return the supplied message unchanged."""
    return {"echo": message}


if __name__ == "__main__":
    mcp.run(transport="stdio")
