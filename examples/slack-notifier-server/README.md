# Slack Notifier MCP Server

Send messages and read channel history via the Slack API.

## Tools

- `send_message(channel, text)` — Send a message to a channel
- `list_channels()` — List available channels
- `get_channel_history(channel, limit?)` — Get recent messages (default: 10, max: 100)

## Setup

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | Yes | Your Slack bot OAuth token (`xoxb-...`) |

## Run

```bash
SLACK_BOT_TOKEN=your-token uv sync && uv run server.py
```

## Test

```bash
uv run pytest -v
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "slack-notifier-server": {
      "command": "uv",
      "args": ["run", "server.py"],
      "env": {"SLACK_BOT_TOKEN": "your-token-here"}
    }
  }
}
```
