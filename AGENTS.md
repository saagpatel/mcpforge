# AGENTS.md

## What This Project Is

`mcpforge` is a Python 3.12+ CLI and MCP server that generates runnable FastMCP servers from plain-English descriptions, then validates generated projects before they are trusted.

## Current State

Use `docs/PROVIDER-MATRIX.md` for hosted-provider readiness, `CHANGELOG.md` for release history, and live git/package state for current release context before acting.

## Stack

- Python 3.12+
- FastMCP
- `uv`
- pytest
- ruff
- Generated Python and TypeScript MCP server examples

## How To Run

Core verification baseline:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mcpforge validate examples/todo-server
uv build
```

Use hosted generation smoke tests only when the task explicitly authorizes the required provider credentials.

## Known Risks

- Generated MCP servers can widen local tool reach; validate generated code before installing or wiring it into clients.
- Do not read provider keys, `.env` files, keychains, OAuth stores, browser profiles, raw logs, private transcripts, or credential-bearing configs.
- Keep PyPI/package naming, release state, and docs/template drift synchronized before any publish framing.

## Next Recommended Move

For this repo, first decide publish/park or active follow-up status, then verify the provider matrix, changelog, package metadata, and live git before doing feature work.
