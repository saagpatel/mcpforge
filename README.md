# mcpforge

<!-- mcp-name: io.github.saagpatel/mcpforge -->

[![PyPI](https://img.shields.io/pypi/v/fastmcp-builder?style=flat-square&logo=pypi&logoColor=white&label=PyPI)](https://pypi.org/project/fastmcp-builder/)
[![Python](https://img.shields.io/pypi/pyversions/fastmcp-builder?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/fastmcp-builder/)
[![CI](https://img.shields.io/github/actions/workflow/status/saagpatel/mcpforge/ci.yml?style=flat-square&logo=githubactions&logoColor=white&label=CI)](https://github.com/saagpatel/mcpforge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](https://github.com/saagpatel/mcpforge/blob/main/LICENSE)

> ### One English sentence in. A tested, spec-free FastMCP 3.x server out.

**mcpforge** turns a plain-English description into a complete FastMCP 3.x MCP server — tools, Pydantic input validation, error handling, a pytest suite, run config, and client setup docs — all wired together and ready to inspect, validate, and install. There's no MCP schema or protocol boilerplate to hand-write: the sentence is the spec. You write it; Claude writes the implementation; mcpforge runs the generated test suite and validators before you ever run it.

## ⚡ 60-second start

![mcpforge demo: one command to a tested, validated MCP server](https://raw.githubusercontent.com/saagpatel/mcpforge/main/docs/assets/hero.gif)

You need Python 3.12+, [`uv`](https://docs.astral.sh/uv/), and an Anthropic API key.

```bash
uv tool install fastmcp-builder      # or: pip install fastmcp-builder
export ANTHROPIC_API_KEY="your_anthropic_api_key"

mcpforge generate "A weather server that returns today's forecast for a city" -o weather-server
```

> **No key yet? Try the demo.** `mcpforge demo` runs the real plan → generate → validate pipeline against a built-in recording and writes a complete, validated weather server — no API key, no spend. It's the fastest way to see exactly what mcpforge produces:
>
> ```bash
> uvx --from fastmcp-builder mcpforge demo
> ```

> **Bring your own key (BYOK).** Generation runs on *your* Anthropic API key — mcpforge calls the Claude API directly and nothing is proxied through a hosted service. A single `generate` makes a few model calls (plan → server → tests), so a typical run costs roughly **$0.05–$0.30** in API usage on the default model (`claude-sonnet-4-6`). That figure is an **estimate** — it scales with server complexity and your chosen model, and is not a live measurement. Everything that doesn't call the model — `validate`, `inspect`, `list`, `doctor`, and `init` — is free.

That's the whole loop. mcpforge plans the tools, generates the code, then runs syntax, security, lint, import, and pytest checks against the result — so what lands in `./weather-server/` is already validated:

```python
# weather-server/server.py  (excerpt)
"""Weather forecast MCP server."""

from fastmcp import FastMCP

mcp = FastMCP("Weather")

# Illustrative lookup — describe a real source and mcpforge wires the call for you.
_FORECASTS: dict[str, dict] = {
    "san francisco": {"high_c": 18, "low_c": 12, "summary": "Foggy"},
    "denver": {"high_c": 24, "low_c": 9, "summary": "Clear"},
}


@mcp.tool
async def get_forecast(city: str) -> dict:
    """Return today's forecast for a city."""
    key = city.strip().lower()
    if key not in _FORECASTS:
        raise ValueError(f"No forecast available for {city!r}")
    return {"city": city, **_FORECASTS[key]}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

Every generation also produces `test_server.py` (a real pytest suite), `pyproject.toml`, a `README.md`, and an MCP client `config.json` — a complete project, not a snippet. Run it with:

```bash
cd weather-server
uv run server.py            # start the server (streamable-http)
uv run pytest -v            # run the generated tests
mcpforge validate .         # re-run the full validation suite anytime
```

![Generated server: tests pass, then it runs](https://raw.githubusercontent.com/saagpatel/mcpforge/main/docs/assets/run-and-test.gif)

> The snippet above is an illustrative toy ("weather") for the docs. Real generations match your description — see [`examples/`](https://github.com/saagpatel/mcpforge/tree/main/examples) for live generated servers (todo, file reader, database query, Slack notifier, TypeScript).

## Build, then audit — the MCP toolkit

mcpforge has a sibling: **[mcp-audit](https://github.com/saagpatel/MCPAudit)** (`mcp-audits` on PyPI). They're two halves of one workflow — forge a server, then audit what your agents can actually touch before you trust it.

| Stage | Tool | What it does |
|-------|------|--------------|
| **Build** | `mcpforge` | Generate a complete, tested MCP server from one sentence. |
| **Audit** | `mcp-audit` | Scan every MCP server wired into your machine and risk-score what each one can reach. |

```bash
# build
mcpforge generate "A weather server that returns today's forecast for a city" -o weather-server

# audit everything your agents can reach (read-only, no install needed)
uvx --from mcp-audits mcp-audit scan --ssrf-check
```

<!-- Record the build+audit GIF (`vhs docs/assets/build-then-audit.tape`), then uncomment the line below: -->
<!-- ![Forge a server, then audit your MCP surface](https://raw.githubusercontent.com/saagpatel/mcpforge/main/docs/assets/build-then-audit.gif) -->

`mcp-audit` is read-only by default — it never edits a config and reports env-var key names only, never values. Build with confidence, then verify your blast radius.

Registry-ready metadata lives in [`server.json`](server.json) with the MCP Registry name
`io.github.saagpatel/mcpforge` and PyPI package `fastmcp-builder`. Treat that metadata as
discovery/provenance context, not as proof that generated servers are safe to run without review.

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

## More commands

The PyPI distribution is `fastmcp-builder`; the installed commands are `mcpforge` and `mcpforge-server`. Beyond `generate`:

```bash
# See it work with no API key — generate a weather server from a built-in recording
mcpforge demo

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
- `--provider anthropic|openai|openrouter` selects the generation provider. `openrouter` is the "bring any model" path: set `OPENROUTER_API_KEY` and pick any OpenRouter model with `--model` (e.g. `--model anthropic/claude-opus-4.8`), including free and low-cost ones. Generation quality and structured-output support vary by model — the recommended models are Claude Opus 4.8 (xHigh) and/or GPT 5.5 (High/Extra High). The `openai` package is a default dependency (included in all installs) because it backs both `--provider openai` and `--provider openrouter`; set `MCPFORGE_ENABLE_OPENAI_PROVIDER=1` to enable the direct OpenAI provider for use with `OPENAI_API_KEY`.

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
| Generation | Anthropic Claude via `anthropic` SDK; OpenAI and OpenRouter via `openai` SDK (included by default) |
| MCP framework | FastMCP 3.x |
| CLI | Click 8 |
| Templates | Jinja2 |
| Validation | Pydantic v2 |
| Output | Rich |

## Architecture

The `generate` command sends the user's description to Claude with a structured prompt that includes FastMCP 3.x idioms and a tool-schema contract. Claude returns a JSON plan (tool names, signatures, and descriptions) that mcpforge validates against a Pydantic model before rendering through Jinja2 templates into a complete project directory. The generated project is then validated with syntax checks, security scanning, ruff linting, import checks, and pytest execution. The `update` command reads an existing generated server, asks Claude for a targeted modification, writes backups for changed files, and validates the result.

## Current Status — v0.3.3

mcpforge is published to PyPI as `fastmcp-builder` v0.3.3. This release adds the
`mcpforge demo` command (try the full generate pipeline with no API key, no cost),
an OpenRouter provider (`--provider openrouter`) for running generation against any
OpenRouter-hosted model, and official MCP Registry metadata. The `generate`,
`update`, `validate`, `inspect`, `doctor`, and `demo` commands work against
FastMCP 3.4.2+.

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

## License

MIT
