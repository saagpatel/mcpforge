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
- Added authenticated OpenAPI hosted smoke coverage and a checked-in authenticated OpenAPI fixture.
- Added deterministic structured-output smoke tests for the current provider interface.
- Added OpenAI structured-output client support plus opt-in hosted structured-output,
  planning, and generation smokes, while keeping full OpenAI generation gated by default.
- Added remote MCP readiness docs/config profiles and inspection readiness signals.
- Expanded OpenAPI planning with response schema summaries, error cases, OAuth token placeholders, and pagination context.
- Switched OpenAPI generated test suites to deterministic local `httpx.AsyncClient`
  fakes so OpenAPI validation checks auth/query/body wiring without LLM-written mocks.

## Remaining v0.3 Work

- Add `OPENAI_API_KEY` to the execution environment or Keychain under `OPENAI_API_KEY`.
- Replenish Anthropic API credits; the latest hosted Anthropic matrix retry was blocked by low credit balance before generation.
- Run the OpenAI hosted structured-output, planning, and generation smokes once `OPENAI_API_KEY` is available.
- Keep OpenAI provider generation gated until those smokes pass repeatedly.
- Run a release-candidate verification pass that includes hosted Anthropic, authenticated OpenAPI, and all OpenAI smokes before the next tag.

## Release Gate

Release gate for `v0.3.0` (completed 2026-05-10). Commands run before tagging:

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
MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE=1 ANTHROPIC_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_generate_openapi_auth_server
MCPFORGE_RUN_HOSTED_OPENAI_SMOKE=1 OPENAI_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_structured_output_smoke
MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE=1 OPENAI_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_planning_smoke
MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE=1 MCPFORGE_ENABLE_OPENAI_PROVIDER=1 OPENAI_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_generate_echo_server
```

## Research Anchors

- MCP specification: https://modelcontextprotocol.io/specification/latest
- MCP security best practices: https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
- OpenAI remote MCP guide: https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- FastMCP server docs: https://gofastmcp.com/servers/server
- FastMCP project config: https://gofastmcp.com/v2/deployment/server-configuration
