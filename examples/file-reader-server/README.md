# File Reader MCP Server

Provides safe read-only access to a local filesystem directory.

## Tools

- `read_file(path)` — Read a file's contents
- `list_files(directory?)` — List files and subdirectories
- `search_files(pattern)` — Search files by glob pattern
- `get_file_info(path)` — Get file metadata

## Setup

| Variable | Required | Description |
|----------|----------|-------------|
| `FILES_ROOT` | No (default: `.`) | Root directory for file access |

All paths are restricted to FILES_ROOT — path traversal attempts are rejected.

## Run

```bash
FILES_ROOT=/path/to/files uv sync && uv run server.py
```

## Test

```bash
uv run pytest -v
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "file-reader-server": {
      "command": "uv",
      "args": ["run", "server.py"],
      "env": {"FILES_ROOT": "/path/to/allowed/directory"}
    }
  }
}
```
