"""Credential-free SafeForge echo fixture."""

from fastmcp import FastMCP

mcp = FastMCP("SafeForge Echo")


@mcp.tool
async def echo(message: str) -> dict:
    """Return the supplied message unchanged."""
    return {"echo": message}


if __name__ == "__main__":
    mcp.run(transport="stdio")
