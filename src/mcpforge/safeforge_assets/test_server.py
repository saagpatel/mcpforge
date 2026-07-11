"""Tests for the credential-free SafeForge echo fixture."""

from fastmcp import Client
from server import mcp


async def test_echo() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("echo", {"message": "hello"})
        assert result.data == {"echo": "hello"}
