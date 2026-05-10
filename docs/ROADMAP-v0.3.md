# mcpforge v0.3 Builder Roadmap

Last updated: 2026-05-10

## Direction

mcpforge is moving from "generate a runnable MCP server" to "generate a reliable production integration surface." The `v0.3` release is optimized for agent builders who need generated MCP servers that can be discovered, inspected, validated, connected, and safely operated by Claude, Codex, OpenAI, and other MCP-capable clients.

## Implemented In This Lane

- Added read-only inspection through `mcpforge inspect PATH [--json]`.
- Added local readiness diagnostics through `mcpforge doctor [--json]`.
- Added `--json` output for `list`, `validate`, and `version`.
- Added TypeScript-aware validation dispatch in the CLI validate command.
- Added Anthropic-first provider abstraction with OpenAI explicitly gated as planned.
- Expanded `mcpforge-server` with generation parity options plus inspection, doctor, and server discovery tools.
- Added generated `.env.example`, Python `fastmcp.json`, and TypeScript README/env output.
- Added live generated fixture examples for REST API, filesystem, database, and TypeScript todo profiles.
- Expanded OpenAPI parsing with tag filters, operation allowlists, limits, auth/env metadata, operation method/path metadata, and schema-aware body descriptions.
- Expanded OpenAPI metadata with path/query/header/cookie/body parameter locations, auth placement, timeout env vars, retry-safety hints, and HTTP client package metadata.
- Added optional Python generation profiles for API-key/JWT auth metadata and logging/timing/rate-limit middleware.
- Added clean install verification script at `scripts/verify_clean_install.sh`.
- Added fixture regression checks for committed v0.3 generated examples.
- Added first-class `PromptDef`, expanded resources, prompt/resource conformance checks, and prompt guidance for generating resources and prompts.
- Hardened nested template injection checks across all plan content, not just top-level fields.

## Remaining v0.3 Work

- Prove the new OpenAPI REST/auth prompt contract through another hosted generation smoke before tagging.
- Add generated fixture coverage for an authenticated OpenAPI spec once the hosted smoke is stable.
- Keep OpenAI provider support gated until strict structured-output and hosted smoke evidence exists.

## Release Gate

Before tagging `v0.3.0`, run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mcpforge validate examples/todo-server
uv build
scripts/verify_clean_install.sh
```

Hosted smokes remain opt-in:

```bash
MCPFORGE_RUN_HOSTED_SMOKE=1 ANTHROPIC_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py
```

## Research Anchors

- MCP specification: https://modelcontextprotocol.io/specification/latest
- MCP security best practices: https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
- OpenAI remote MCP guide: https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- FastMCP server docs: https://gofastmcp.com/servers/server
- FastMCP project config: https://gofastmcp.com/v2/deployment/server-configuration
