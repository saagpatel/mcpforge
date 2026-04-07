# mcpforge

**Generate production-ready MCP servers from a single sentence.**

[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.x-orange)](https://github.com/jlowin/fastmcp)

```bash
mcpforge generate "A todo list manager with create, read, update, and delete operations"
```

That's it. In under a minute you have a fully working MCP server — complete with tools, input validation, error handling, a pytest test suite, and a `pyproject.toml` ready to install.

---

## What is this?

[MCP (Model Context Protocol)](https://modelcontextprotocol.io) is the open standard that lets AI assistants like Claude connect to external tools and data sources. An MCP server exposes capabilities — reading files, querying databases, calling APIs — that AI models can use directly.

Building one from scratch means wiring up schemas, writing async tool handlers, configuring transports, and writing tests. It's repetitive boilerplate that gets in the way of the interesting part: the actual logic.

**mcpforge eliminates the boilerplate.** Describe what you want in plain English. Get back a complete, runnable server.

---

## What you get

When you run `mcpforge generate`, you get a full project directory:

```
todo-manager/
├── server.py          # FastMCP 3.x server — tools, validation, error handling
├── test_server.py     # pytest suite with happy paths + error cases
├── pyproject.toml     # Dependencies pinned, entry point configured
├── README.md          # Usage instructions for the generated server
└── config.json        # Claude Desktop config snippet — paste and go
```

Every generated server:
- Uses **[FastMCP 3.x](https://github.com/jlowin/fastmcp)** — the leading Python MCP framework
- Has **async tool handlers** with proper type annotations
- Validates input and raises descriptive errors
- Reads secrets and config from **environment variables** — never hardcoded
- Comes with a **self-contained test suite** that runs in-process (no server needed)

---

## Why mcpforge?

### The status quo is painful

Writing an MCP server by hand means:
- Learning FastMCP's decorator syntax and transport options
- Writing Pydantic schemas for every parameter
- Handling errors in a way MCP clients understand
- Figuring out the pytest patterns for in-process testing
- Repeating all of this for every new server

### mcpforge handles all of it

The three-stage pipeline — **plan → generate → validate** — produces servers that actually work:

1. **Plan**: An LLM extracts a structured plan (tools, params, return types) from your description. You see it before any code is written and can refine it interactively.
2. **Generate**: A second LLM pass produces idiomatic FastMCP code, guided by the structured plan and optional template hints.
3. **Validate + Self-Heal**: The generated code runs through AST parsing, ruff linting, import checking, and pytest. If anything fails, mcpforge attempts an automatic fix and re-validates — all before handing it to you.

---

## Installation

```bash
pip install mcpforge
# or
uv add mcpforge
```

Requires Python 3.12+ and an Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Quick start

### Generate a server

```bash
mcpforge generate "A GitHub API wrapper for listing issues, creating PRs, and searching repos"
```

Watch the pipeline run in your terminal, then find your new server in `./github-api-wrapper/`.

### Preview before generating

```bash
mcpforge generate --dry-run "A Slack bot that can send messages and look up channel history"
```

Shows the extracted tool plan — name, parameters, return types — without writing a single file.

### Refine the plan interactively

```bash
mcpforge generate "A weather service" --interactive
```

After seeing the plan, you can type adjustments ("add a 5-day forecast tool", "the location param should support both city names and lat/lng") and regenerate until it looks right.

### Generate from an OpenAPI spec

```bash
mcpforge generate --from-openapi stripe.yaml "Stripe payment tools"
```

Skip the planning stage entirely — mcpforge reads your spec and turns every endpoint into an MCP tool.

### Update an existing server

```bash
mcpforge update ./my-server "Add a bulk delete operation and a pagination cursor to list_todos"
```

Modify a generated server with a natural-language request. Your existing code is preserved; only the relevant parts change.

### Generate TypeScript

```bash
mcpforge generate "A filesystem browser" --language typescript
```

Produces a TypeScript server using the MCP SDK, with Vitest tests included.

### Scaffold offline

```bash
mcpforge init "My Custom Server"
```

Creates the full directory structure with a minimal working server — no API call, no internet, no API key needed. Start with the scaffolding and write your own tools.

---

## Template hints

The `--template` flag injects framework-specific guidance into the generation prompt, producing more idiomatic code for common server patterns.

| Template | Best for |
|----------|----------|
| `rest-api` | Wrapping HTTP APIs — uses `async httpx`, reads base URL + API key from env |
| `database` | SQL access — enforces parameterized queries, returns `list[dict]` |
| `filesystem` | File operations — path traversal protection, root from env var |
| `graphql` | GraphQL APIs — `gql` + `aiohttp`, handles errors in response body |
| `websocket` | Real-time connections — persistent connections, exponential backoff reconnect |
| `auth-proxy` | Authenticated services — JWT validation, Bearer token forwarding, 401 refresh |
| `queue-consumer` | Redis queues — `redis.asyncio`, BLPOP pattern, dead-letter queue on failure |

```bash
mcpforge generate "A Redis-backed job queue" --template queue-consumer
```

---

## All CLI options

### `mcpforge generate`

```
mcpforge generate DESCRIPTION [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output PATH` | `./<slug>` | Output directory |
| `-m, --model TEXT` | `claude-sonnet-4-20250514` | LLM model |
| `-t, --transport` | `streamable-http` | Transport: `streamable-http`, `stdio`, `sse` |
| `-T, --template` | — | Template hint (see above) |
| `-l, --language` | `python` | `python` or `typescript` |
| `-i, --interactive` | off | Refine the plan before generating |
| `--from-openapi FILE` | — | Generate from an OpenAPI 3.x spec |
| `--stream` | off | Stream generation output live |
| `--multi-file` | off | Split server across multiple files (Python) |
| `--dry-run` | off | Show plan only, no files written |
| `-y, --yes` | off | Skip confirmation prompts |
| `-f, --force` | off | Overwrite existing output directory |

### `mcpforge update`

```
mcpforge update PATH REQUEST
```

Apply a natural-language modification to an existing server. Runs validation and self-heal automatically.

### `mcpforge validate`

```
mcpforge validate PATH
```

Run the full validation suite (syntax, lint, import, pytest) against an existing server and report results.

### `mcpforge list`

```
mcpforge list [PATH] [--recursive]
```

Discover mcpforge-generated servers in a directory. Shows name, language, tool count, and test status.

### `mcpforge init`

```
mcpforge init NAME [--output PATH] [--transport TYPE]
```

Scaffold a minimal server without an LLM. No API key needed. Useful as a starting point.

---

## Use mcpforge as an MCP server

mcpforge can expose its own generation capabilities as MCP tools — so Claude (or any MCP-compatible client) can generate servers on your behalf.

```bash
mcpforge-server
```

This starts an MCP server with four tools: `generate`, `update`, `validate`, and `plan`. Add it to your Claude Desktop config and ask Claude to build you a server directly from the chat.

---

## How it works

```
Your description
      │
      ▼
 ┌─────────┐
 │  Plan   │  LLM call #1 — extract tools, params, return types, env vars
 └────┬────┘
      │  ServerPlan (structured, validated)
      ▼
 ┌──────────┐
 │ Generate │  LLM call #2 — produce idiomatic FastMCP code from the plan
 └────┬─────┘
      │
      ▼
 ┌──────────────┐
 │ Test Generate│  LLM call #3 — write pytest suite against the generated code
 └──────┬───────┘
        │
        ▼
 ┌──────────┐
 │ Validate │  AST parse → ruff lint → import check → pytest
 └────┬─────┘
      │  failed?
      ▼
 ┌───────────┐
 │ Self-Heal │  Surgical AST patch of broken functions + re-validate
 └─────┬─────┘
       │
       ▼
  Your server ✓
```

The planning stage is the key insight: by extracting a structured `ServerPlan` first (tool names, parameter types, return types, required env vars), the generator has a precise contract to implement rather than inferring structure from prose. This dramatically reduces hallucinated tool signatures and missing imports.

Self-heal is surgical: mcpforge parses error line numbers, uses the AST to identify which specific functions are broken, sends only those functions to the LLM for repair, and splices fixes back in. For widespread failures it falls back to a full rewrite — but most generation errors are localized.

---

## Examples

Five pre-built example servers live in [`examples/`](examples/):

| Server | What it does |
|--------|-------------|
| [`todo-server`](examples/todo-server/) | In-memory CRUD for todo items |
| [`weather-server`](examples/weather-server/) | Mock weather lookup by city |
| [`file-reader-server`](examples/file-reader-server/) | Read, list, and search local files |
| [`database-query-server`](examples/database-query-server/) | Execute SQL against SQLite |
| [`slack-notifier-server`](examples/slack-notifier-server/) | Send Slack messages via webhook |

Each is a fully runnable server. Browse the source to see what mcpforge produces.

---

## Development

```bash
git clone https://github.com/saagpatel/mcpforge
cd mcpforge
uv sync
uv run pytest tests/ -v      # 234 tests
uv run ruff check src/ tests/
```

---

## License

MIT — see [LICENSE](LICENSE).
