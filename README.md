# mcpforge

Generate production-ready FastMCP 3.x MCP servers from plain-English descriptions.

![Python](https://img.shields.io/badge/python-3.12+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## What it does

mcpforge takes a plain-English description of a service and generates a complete, runnable FastMCP 3.x server — including tool definitions, input validation, error handling, and a pytest test suite. A self-healing validation loop catches and fixes common generation errors automatically.

## Quick Start

```bash
pip install mcpforge
```

```bash
mcpforge generate "A todo list manager with create, read, update, and delete operations"
```

What you get:

- `server.py` — FastMCP 3.x server with all tools defined
- `test_server.py` — pytest test suite covering happy paths and error cases
- `pyproject.toml` — project config with dependencies pinned
- `README.md` — usage instructions for the generated server

## CLI Reference

### `generate`

```
mcpforge generate DESCRIPTION [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output PATH` | `-o` | `./<slug>` | Output directory |
| `--model MODEL` | `-m` | `claude-sonnet-4-20250514` | LLM model for generation |
| `--transport TYPE` | `-t` | `streamable-http` | MCP transport (`streamable-http`, `stdio`, `sse`) |
| `--template TYPE` | `-T` | — | Apply a template hint to guide code style |
| `--dry-run` | | `false` | Show plan only, skip code generation |
| `--yes` | `-y` | `false` | Skip confirmation prompts |
| `--force` | `-f` | `false` | Overwrite existing output directory |

### `validate`

```
mcpforge validate PATH
```

Runs the validation suite (syntax, lint, import, tests) against an existing generated server.

### `version`

```
mcpforge version
```

Prints the installed mcpforge version.

## Template Hints

The `--template` flag injects framework-specific guidance into the generation prompt, producing more idiomatic output for common server patterns.

| Template | Description |
|----------|-------------|
| `rest-api` | Wraps a REST API using `async httpx.AsyncClient`. Reads API keys and base URL from env vars, handles HTTP errors with descriptive messages. |
| `database` | Queries a database using `aiosqlite` or `asyncpg`. Enforces parameterized queries, reads connection string from env, returns results as `list[dict]`. |
| `filesystem` | Reads/writes the local filesystem via `pathlib.Path`. Enforces path traversal protection, reads root directory from env var. |

Example:

```bash
mcpforge generate "A GitHub API client for issues and PRs" --template rest-api
```

## Examples

| Example | Description |
|---------|-------------|
| [`examples/todo-server/`](examples/todo-server/) | In-memory todo list with CRUD operations |
| [`examples/weather-api/`](examples/weather-api/) | REST API wrapper for weather data |
| [`examples/sqlite-notes/`](examples/sqlite-notes/) | SQLite-backed notes with full-text search |

## Architecture

mcpforge generates servers through a structured pipeline:

1. **Plan** — Extract a structured `ServerPlan` (name, tools, params, return types) from the description using an LLM
2. **Generate** — Produce `server.py` from the plan, with optional template guidance injected into the prompt
3. **Write** — Write `server.py`, `test_server.py`, and `pyproject.toml` to the output directory
4. **Sync** — Run `uv sync` in the output directory to install dependencies
5. **Validate** — Run AST parse, ruff lint, import check, and pytest against the generated server
6. **Self-heal** — If validation fails, attempt one automatic fix pass using the error output as feedback

## Generated Server Structure

```
<slug>/
├── server.py          # FastMCP 3.x server (tools, validation, error handling)
├── test_server.py     # pytest suite using fastmcp.Client in-process testing
├── pyproject.toml     # Project config with fastmcp + dev dependencies
└── README.md          # Usage instructions
```

## Development

```bash
uv sync
uv run pytest tests/ -v
uv run ruff check src/ tests/
```
