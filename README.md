# mcpforge

[![Python](https://img.shields.io/badge/Python-3776ab?style=flat-square&logo=python)](#) [![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](#)

> One sentence. One command. A complete MCP server, ready to run.

mcpforge generates production-ready FastMCP 3.x MCP servers from plain-English descriptions. You describe what you want; it produces tools, input validation, error handling, a pytest test suite, and a `pyproject.toml` — all wired together and ready to install.

## Features

- **Plain-English generation** — describe your server in natural language; Claude writes the implementation
- **Complete project scaffold** — tools, Pydantic input models, error handling, `pyproject.toml`, and a pytest suite generated together
- **FastMCP 3.x native** — output uses modern FastMCP decorators and transport configuration, not raw MCP protocol boilerplate
- **Inspect before running** — `mcpforge inspect` loads any MCP server and shows its full tool schema without running it
- **Iterate and extend** — `mcpforge extend` adds new tools to an existing generated server without regenerating from scratch
- **MCP server mode** — `mcpforge-server` exposes generation itself as an MCP tool, so AI assistants can generate servers on demand

## Quick Start

### Prerequisites
- Python 3.12+
- `uv` (recommended)
- Anthropic API key

### Installation
```bash
uv tool install mcpforge
```

### Usage
```bash
# Generate a new MCP server
mcpforge generate "A todo list manager with create, read, update, and delete operations"

# Inspect an existing server's tool schema
mcpforge inspect ./my-server

# Add a new tool to an existing server
mcpforge extend ./my-server "Add a tool to export todos as CSV"
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12+ |
| Generation | Anthropic Claude via `anthropic` SDK |
| MCP framework | FastMCP 3.x |
| CLI | Click 8 |
| Templates | Jinja2 |
| Validation | Pydantic v2 |
| Output | Rich |

## Architecture

The `generate` command sends the user's description to Claude with a structured prompt that includes FastMCP 3.x idioms and a tool-schema contract. Claude returns a JSON plan (tool names, signatures, and descriptions) that mcpforge validates against a Pydantic model before rendering through Jinja2 templates into a complete project directory. The `extend` command reads the existing project's tool list, appends the new tool spec to the plan, and rerenders only the changed files — keeping manual edits to other parts of the server intact.

## License

MIT