# mcpforge

[![Python](https://img.shields.io/badge/Python-3776ab?style=flat-square&logo=python)](#) [![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](#)

> One sentence. One command. A complete MCP server, ready to run.

mcpforge generates production-ready FastMCP 3.x MCP servers from plain-English descriptions. You describe what you want; it produces tools, input validation, error handling, a pytest test suite, and a `pyproject.toml` — all wired together and ready to install.

## Features

- **Plain-English generation** — describe your server in natural language; Claude writes the implementation
- **Complete project scaffold** — tools, Pydantic input models, error handling, `pyproject.toml`, and a pytest suite generated together
- **FastMCP 3.x native** — output uses modern FastMCP decorators and transport configuration, not raw MCP protocol boilerplate
- **Validate before running** — `mcpforge validate` runs syntax, security, lint, import, and pytest checks against generated servers
- **Iterate safely** — `mcpforge update` modifies an existing generated server and backs up changed files before writing
- **Discover generated servers** — `mcpforge list` finds mcpforge-generated projects in a workspace
- **Scaffold without an LLM** — `mcpforge init` creates a minimal FastMCP server skeleton for local iteration
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

# Validate an existing generated server
mcpforge validate ./my-server

# Modify an existing generated server
mcpforge update ./my-server "Add a tool to export todos as CSV"

# Find generated servers in the current workspace
mcpforge list . --recursive
```

Useful generation flags:
- `--dry-run` displays the structured plan without writing files.
- `--no-execute` writes files but skips import and test execution.
- `--strict` treats lint errors as hard validation failures.
- `--from-openapi FILE` generates from an OpenAPI 3.x spec.
- `--language python|typescript` chooses the target server language.

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

The `generate` command sends the user's description to Claude with a structured prompt that includes FastMCP 3.x idioms and a tool-schema contract. Claude returns a JSON plan (tool names, signatures, and descriptions) that mcpforge validates against a Pydantic model before rendering through Jinja2 templates into a complete project directory. The generated project is then validated with syntax checks, security scanning, ruff linting, import checks, and pytest execution. The `update` command reads an existing generated server, asks Claude for a targeted modification, writes backups for changed files, and validates the result.

## Current Status

As of May 9, 2026, `main` is green after the validation, example, CI, and dependency cleanup pass. Open GitHub PRs and Dependabot alerts were cleared, and the release-readiness baseline is tracked in `docs/CURRENT-STATE.md`.

## License

MIT
