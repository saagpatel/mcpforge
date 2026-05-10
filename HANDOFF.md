# mcpforge Handoff

Last updated: 2026-05-10

## Status

`main` was the verified `0.2.0` base after the cleanup pass. Active `v0.3 Builder` work is happening on `codex/v03-builder-roadmap` in a dedicated worktree. The repo is no longer in PR/security cleanup mode: open GitHub PRs were cleared, Dependabot alerts were cleared, and the latest GitHub `main` checks were green before this feature lane began.

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

Latest local result on 2026-05-10: the baseline above passed, `uv build` produced the `0.2.0` source distribution and wheel, `uv run pytest -q` reported 322 passed and 2 skipped, discovery/inspection/doctor JSON smokes passed, the stable todo example validated with 11 tests run and 0 failed, the TypeScript todo example validated with 2 tests run and 0 failed, the new v0.3 REST/filesystem/database/TypeScript fixtures validated with 33/48/49/31 tests run and 0 failed, and hosted Python plus TypeScript generation passed with `ANTHROPIC_API_KEY` loaded from Keychain.

Opt-in hosted smoke command:

```bash
MCPFORGE_RUN_HOSTED_SMOKE=1 ANTHROPIC_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py
```

## Remaining Decisions

1. Finish v0.3 release hardening and run the full baseline.
2. Keep OpenAI provider support gated until deterministic structured-output and hosted smoke evidence exists.
3. Add deeper generated REST client behavior and optional auth/middleware profiles.

## Best Next Step

Continue on `codex/v03-builder-roadmap`, run the full verification baseline, then merge back to `main` when clean.
