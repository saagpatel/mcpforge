# mcpforge

## Overview
A Python CLI that takes a plain-English description of a service and generates a complete, runnable FastMCP 3.x server with tool definitions, error handling, input validation, and pytest test suite. Uses the Anthropic API for intelligent code generation with a self-healing validation loop.

## Tech Stack
- Python: 3.12+
- FastMCP: 3.2.x (standalone, PrefectHQ/fastmcp)
- Anthropic SDK: latest (claude-sonnet-4-6 default model — pinned; see MODEL PIN in api_client.py)
- Click: latest — CLI framework
- Pydantic: v2 — structured data models and LLM output parsing
- Jinja2: latest — output file templates
- Rich: latest — terminal UI (spinners, colored output)
- pytest + pytest-asyncio: testing
- ruff: linting
- uv: package management

## Development Conventions
- Python 3.12+ features only (match statements, type union syntax `X | Y`)
- src layout: all source under `src/mcpforge/`
- Type hints on every function signature — no `Any` types
- Async by default for all Anthropic API calls
- ruff for linting and formatting — zero tolerance for warnings
- pytest for all tests — no unittest
- Conventional commits: feat:, fix:, chore:, docs:

## Current Phase
**Active — v0.3.0 published to PyPI (fastmcp-builder)**

v0.3.0 is live on PyPI. The current focus is provider matrix expansion: Anthropic is the default, OpenAI remains gated behind hosted structured-output/planning/generation smokes. See `docs/CURRENT-STATE.md` for the verified baseline.

## Key Decisions
| Decision | Choice | Why |
|----------|--------|-----|
| Generation model | claude-sonnet-4-6 (override via --model) | Pinned pre-Opus-4.7: relies on temperature=0 for deterministic JSON output — see MODEL PIN in api_client.py |
| Output server framework | FastMCP 3.2.x standalone | 70% market share, best DX, actively maintained |
| Transport default | streamable-http | 2026 MCP production standard |
| Generation approach | 3-stage (plan → generate → test) | Structured plan prevents hallucinated tools |
| Validation | AST parse + ruff + import check + pytest | Multi-layer catches different failure modes |
| Self-heal | 1 retry max | Diminishing returns beyond 1 retry |

## Do NOT
- Do not generate MCP servers using the old SDK-bundled FastMCP v1 patterns — use standalone FastMCP 3.x with `from fastmcp import FastMCP`
- Do not hardcode API keys in generated server code — always use env vars
- Do not skip the planning stage — always extract a structured ServerPlan before generating code
- Do not treat older roadmap phase labels as current without checking `docs/CURRENT-STATE.md`
- Do not use synchronous HTTP calls to Anthropic API — always async
- Do not trust LLM output without validation — always run AST parse + import check minimum

<!-- portfolio-context:start -->
# Portfolio Context

## What This Project Is

A Python CLI that takes a plain-English description of a service and generates a complete, runnable FastMCP 3.x server with tool definitions, error handling, input validation, and pytest test suite. Uses the Anthropic API for intelligent code generation with a self-healing validation loop.

## Current State

**Active — v0.3.0 published to PyPI as `fastmcp-builder`**
See `docs/CURRENT-STATE.md` for the current resume checkpoint.

## Stack

- Python: 3.12+
- FastMCP: 3.2.x (standalone, PrefectHQ/fastmcp)
- Anthropic SDK: latest (claude-sonnet-4-6 default model — pinned; see MODEL PIN in api_client.py)
- Click: latest — CLI framework
- Pydantic: v2 — structured data models and LLM output parsing
- Jinja2: latest — output file templates
- Rich: latest — terminal UI (spinners, colored output)
- pytest + pytest-asyncio: testing
- ruff: linting
- uv: package management

## How To Run

- Python 3.12+ features only (match statements, type union syntax `X | Y`)
- src layout: all source under `src/mcpforge/`
- Type hints on every function signature — no `Any` types
- Async by default for all Anthropic API calls
- ruff for linting and formatting — zero tolerance for warnings
- pytest for all tests — no unittest
- Conventional commits: feat:, fix:, chore:, docs:

## Known Risks

- Do not generate MCP servers using the old SDK-bundled FastMCP v1 patterns — use standalone FastMCP 3.x with `from fastmcp import FastMCP`
- Do not hardcode API keys in generated server code — always use env vars
- Do not skip the planning stage — always extract a structured ServerPlan before generating code
- Do not treat older roadmap phase labels as current without checking `docs/CURRENT-STATE.md`
- Do not use synchronous HTTP calls to Anthropic API — always async
- Do not trust LLM output without validation — always run AST parse + import check minimum

## Next Recommended Move

Use this context plus the README and `docs/CURRENT-STATE.md` to resume the next active task. The current frontier is provider matrix expansion: add `OPENAI_API_KEY` and replenish Anthropic credits, then run the hosted smoke matrix before ungating OpenAI generation.

<!-- portfolio-context:end -->
