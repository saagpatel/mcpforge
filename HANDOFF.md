# mcpforge Handoff

Last updated: 2026-05-10

## Status

`main` is the published `0.3.0` base. The repo is no longer in PR/security cleanup mode: open GitHub PRs were cleared, Dependabot alerts were cleared, and `fastmcp-builder==0.3.0` is published on PyPI. The current follow-up is provider-matrix readiness: OpenAI remains gated, and live hosted smokes are blocked on missing OpenAI credentials plus Anthropic account credits.

## What This Project Is

mcpforge generates complete FastMCP 3.x server projects from natural-language descriptions. It plans first, generates code and tests, writes a runnable project, and validates the generated server before reporting success.

## What Was Just Completed

- Fixed generated example servers to use normal Python exceptions instead of invalid string-based `McpError` usage.
- Made validation truthfully fail when generated-server tests execute and fail.
- Updated MCP validation output to distinguish structural validity from executed-test health.
- Fixed the macOS sandbox profile so pytest logging can open `/dev/null`.
- Removed the duplicate uppercase/lowercase PR template conflict.
- Updated CI to Python 3.12.
- Merged Dependabot package and GitHub Actions updates into `main`.
- Refreshed root and todo-example locks to resolve active dependency alerts.
- Closed stale or superseded Dependabot PRs.
- Ran Codex operating-surface closeout after the repo work: `run-codex-evals` passed 9/9, hook health passed, closure gate passed, and truth reconciliation was clean.
- Hardened TypeScript validation so Vitest test counts come from the real test
  summary, and removed a duplicate dependency install from TypeScript generation.
- Added TypeScript-generated project metadata so `mcpforge list` discovers
  TypeScript servers alongside Python servers.
- Tightened TypeScript test generation so hosted `--language typescript` output
  validates under strict MCP result typing.
- Started the `v0.3 Builder` roadmap: inspection, doctor, JSON outputs, MCP server parity,
  richer generated scaffolds, OpenAPI curation, provider abstraction, prompt/resource model
  support, and nested template injection hardening.
- Added live generated fixtures for REST API, filesystem, database, and TypeScript todo
  profiles, including generated `.env.example`, README, config, tests, and validation checks.
- Added the next v0.3 hardening pass: OpenAPI parameter/auth placement metadata,
  optional Python auth/middleware generation profiles, clean install verification script,
  and fixture regression checks.
- Proved the authenticated OpenAPI generation path with a hosted smoke and added the
  `v03-authenticated-openapi-server` fixture.
- Added deterministic structured-output smoke tests for the Anthropic provider
  interface while keeping OpenAI provider support gated.
- Added a gated OpenAI structured-output client and opt-in hosted structured-output,
  planning, and generation smokes.
- Added remote MCP readiness docs/config profiles and inspection readiness signals.
- Expanded OpenAPI planning with richer response summaries, non-2xx error cases,
  OAuth token placeholder guidance, and pagination context.
- Switched OpenAPI generated test suites to deterministic local `httpx.AsyncClient`
  fakes so hosted OpenAPI validation no longer depends on LLM-written mock code.

## Current Command Surface

- `mcpforge generate DESCRIPTION`
- `mcpforge update PATH REQUEST`
- `mcpforge validate PATH`
- `mcpforge list [PATH]`
- `mcpforge inspect PATH`
- `mcpforge doctor`
- `mcpforge init NAME`
- `mcpforge version`
- `mcpforge-server`

Status-like commands now support `--json` where useful.

## Verification To Re-Run

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mcpforge validate examples/todo-server
uv build
```

Latest local result on 2026-05-10: the baseline above passed, `uv run pytest -q` reported 347 passed and 6 skipped, `uv build` produced the `fastmcp-builder` source distribution and wheel, `scripts/verify_clean_install.sh` reported `mcpforge 0.3.0`, the stable todo example validated with 11 tests run and 0 failed, the authenticated OpenAPI fixture validated with 23 tests run and 0 failed, `mcpforge inspect` reported the authenticated OpenAPI fixture as remote MCP ready, the authenticated fixture started through `fastmcp run fastmcp.json` on a local HTTP test port with env vars set, hosted Python, TypeScript, and authenticated OpenAPI generation passed with `ANTHROPIC_API_KEY` loaded from Keychain, and the new OpenAI hosted structured-output/planning/generation smokes are present but skipped until `OPENAI_API_KEY` is set.

Latest provider-matrix retry on 2026-05-10: `OPENAI_API_KEY` was not available in the shell or common Keychain service names, so the OpenAI smoke trio skipped. `ANTHROPIC_API_KEY` was available from Keychain, but hosted Anthropic Python, TypeScript, and authenticated OpenAPI smokes failed before generation because the Anthropic API reported low credit balance. Keep OpenAI gated until both provider conditions are repaired and the hosted matrix is green.

Opt-in hosted smoke command:

```bash
MCPFORGE_RUN_HOSTED_SMOKE=1 ANTHROPIC_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py
MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE=1 ANTHROPIC_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_generate_openapi_auth_server
MCPFORGE_RUN_HOSTED_OPENAI_SMOKE=1 OPENAI_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_structured_output_smoke
MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE=1 OPENAI_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_planning_smoke
MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE=1 MCPFORGE_ENABLE_OPENAI_PROVIDER=1 OPENAI_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_generate_echo_server
```

## Remaining Decisions

1. Keep full OpenAI provider generation gated until OpenAI structured-output, planning, and generation hosted smokes pass.
2. Add `OPENAI_API_KEY` to this shell or Keychain under `OPENAI_API_KEY`, then run the OpenAI hosted smoke trio.
3. Replenish Anthropic API credits, then rerun the hosted Anthropic Python, TypeScript, and authenticated OpenAPI smoke matrix.

## Best Next Step

Repair provider access first: add `OPENAI_API_KEY` and replenish Anthropic credits, then rerun the hosted matrix before changing OpenAI's gated status.
