"""Slack notification MCP server."""

import os

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import McpError

mcp = FastMCP("Slack Notifier")

SLACK_API_BASE = "https://slack.com/api"


def _get_token() -> str:
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        raise McpError("SLACK_BOT_TOKEN environment variable is not set")
    return token


@mcp.tool
async def send_message(channel: str, text: str) -> dict:
    """Send a message to a Slack channel."""
    token = _get_token()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SLACK_API_BASE}/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"channel": channel, "text": text},
        )
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"):
        raise McpError(f"Slack API error: {data.get('error', 'unknown')}")
    return {"ok": True, "channel": channel, "ts": data.get("ts", "")}


@mcp.tool
async def list_channels() -> dict:
    """List available Slack channels."""
    token = _get_token()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SLACK_API_BASE}/conversations.list",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"):
        raise McpError(f"Slack API error: {data.get('error', 'unknown')}")
    channels = [
        {"id": ch["id"], "name": ch["name"]}
        for ch in data.get("channels", [])
    ]
    return {"channels": channels}


@mcp.tool
async def get_channel_history(channel: str, limit: int = 10) -> dict:
    """Get recent messages from a Slack channel."""
    token = _get_token()
    if not 1 <= limit <= 100:
        raise McpError("limit must be between 1 and 100")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SLACK_API_BASE}/conversations.history",
            headers={"Authorization": f"Bearer {token}"},
            params={"channel": channel, "limit": limit},
        )
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"):
        raise McpError(f"Slack API error: {data.get('error', 'unknown')}")
    messages = [
        {"text": msg.get("text", ""), "ts": msg.get("ts", "")}
        for msg in data.get("messages", [])
    ]
    return {"channel": channel, "messages": messages}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
