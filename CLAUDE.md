# mcpforge

## Overview
A Python CLI that takes a plain-English description of a service and generates a complete, runnable FastMCP 3.x server with tool definitions, error handling, input validation, and pytest test suite. Uses the Anthropic API for intelligent code generation with a self-healing validation loop.

## Tech Stack
- Python: 3.12+
- FastMCP: 3.1.x (standalone, PrefectHQ/fastmcp)
- Anthropic SDK: latest (claude-sonnet-4-20250514 default model)
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
**Phase 0: Foundation**
See IMPLEMENTATION-ROADMAP.md for full phase details.

## Key Decisions
| Decision | Choice | Why |
|----------|--------|-----|
| Generation model | claude-sonnet-4-20250514 (override via --model) | Best speed/quality ratio for code gen |
| Output server framework | FastMCP 3.1.x standalone | 70% market share, best DX, actively maintained |
| Transport default | streamable-http | 2026 MCP production standard |
| Generation approach | 3-stage (plan → generate → test) | Structured plan prevents hallucinated tools |
| Validation | AST parse + ruff + import check + pytest | Multi-layer catches different failure modes |
| Self-heal | 1 retry max | Diminishing returns beyond 1 retry |

## Do NOT
- Do not generate MCP servers using the old SDK-bundled FastMCP v1 patterns — use standalone FastMCP 3.x with `from fastmcp import FastMCP`
- Do not hardcode API keys in generated server code — always use env vars
- Do not skip the planning stage — always extract a structured ServerPlan before generating code
- Do not add features not in the current phase of IMPLEMENTATION-ROADMAP.md
- Do not use synchronous HTTP calls to Anthropic API — always async
- Do not trust LLM output without validation — always run AST parse + import check minimum
