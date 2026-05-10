# mcpforge

[![Python](https://img.shields.io/badge/Python-3776ab?style=flat-square&logo=python)](#) [![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](#)

> One sentence. One command. A complete MCP server, ready to run.

mcpforge generates production-ready FastMCP 3.x MCP servers from plain-English descriptions. You describe what you want; it produces tools, input validation, error handling, a pytest test suite, run configuration, and client setup docs — all wired together and ready to inspect, validate, and install.

## Features

- **Plain-English generation** — describe your server in natural language; Claude writes the implementation
- **Complete project scaffold** — tools, Pydantic input models, error handling, `pyproject.toml`, and a pytest suite generated together
- **FastMCP 3.x native** — output uses modern FastMCP decorators and transport configuration, not raw MCP protocol boilerplate
- **Validate before running** — `mcpforge validate` runs syntax, security, lint, import, and pytest checks against generated servers
- **Iterate safely** — `mcpforge update` modifies an existing generated server and backs up changed files before writing
- **Discover generated servers** — `mcpforge list` finds mcpforge-generated projects in a workspace
- **Inspect and diagnose** — `mcpforge inspect` summarizes generated server shape, while `mcpforge doctor` checks local readiness
- **Machine-readable output** — status-like commands expose `--json` for agent workflows
- **OpenAPI curation controls** — include/exclude tags, operation allowlists, and operation limits keep generated integrations focused
- **Scaffold without an LLM** — `mcpforge init` creates a minimal FastMCP server skeleton for local iteration
- **MCP server mode** — `mcpforge-server` exposes generation, planning, validation, inspection, doctor, and discovery tools so AI assistants can build safely

## Quick Start

### Prerequisites
- Python 3.12+
- `uv` (recommended)
- Anthropic API key

### Installation
```bash
uv tool install fastmcp-builder
```

The PyPI distribution is `fastmcp-builder`; the installed commands remain
`mcpforge` and `mcpforge-server`.

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

# Inspect a generated server without executing it
mcpforge inspect ./my-server

# Check local prerequisites and provider readiness
mcpforge doctor
```

Useful generation flags:
- `--dry-run` displays the structured plan without writing files.
- `--no-execute` writes files but skips import and test execution.
- `--strict` treats lint errors as hard validation failures.
- `--from-openapi FILE` generates from an OpenAPI 3.x spec.
- `--openapi-include-tag TAG`, `--openapi-exclude-tag TAG`, `--openapi-operation ID`, and `--openapi-limit N` curate OpenAPI conversion.
- `--language python|typescript` chooses the target server language.
- `--auth-profile none|api-key|jwt` adds optional Python auth profile metadata and env docs.
- `--middleware-profile logging|timing|rate-limit` adds optional Python middleware profiles; repeat it to combine profiles.
- `--provider anthropic|openai` selects the generation provider. OpenAI structured-output support has an opt-in smoke, but full OpenAI generation remains gated until planning and generation smokes pass.

Useful status flags:
- `mcpforge list --json`
- `mcpforge inspect PATH --json`
- `mcpforge validate PATH --json`
- `mcpforge doctor --json`
- `mcpforge version --json`

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12+ |
| Generation | Anthropic Claude via `anthropic` SDK; OpenAI structured-output smoke support is gated |
| MCP framework | FastMCP 3.x |
| CLI | Click 8 |
| Templates | Jinja2 |
| Validation | Pydantic v2 |
| Output | Rich |

## Architecture

The `generate` command sends the user's description to Claude with a structured prompt that includes FastMCP 3.x idioms and a tool-schema contract. Claude returns a JSON plan (tool names, signatures, and descriptions) that mcpforge validates against a Pydantic model before rendering through Jinja2 templates into a complete project directory. The generated project is then validated with syntax checks, security scanning, ruff linting, import checks, and pytest execution. The `update` command reads an existing generated server, asks Claude for a targeted modification, writes backups for changed files, and validates the result.

## Current Status

As of May 10, 2026, `0.3.0` is published to PyPI as the `fastmcp-builder` distribution. The v0.3 builder lane expands mcpforge from runnable-server generation into a production integration builder with inspection, doctor checks, richer generated scaffolds, OpenAPI curation, MCP server parity, provider abstraction, remote MCP readiness docs, and live generated fixture examples for REST API, filesystem, database, authenticated OpenAPI, and TypeScript profiles. See `docs/CURRENT-STATE.md` and `docs/ROADMAP-v0.3.md`.

## License

MIT
