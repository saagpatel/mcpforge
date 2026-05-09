# mcpforge Handoff

Last updated: 2026-05-09

## Status

`main` is the active branch and was pushed after the latest cleanup pass. The repo is no longer in PR/security cleanup mode: open GitHub PRs were cleared, Dependabot alerts were cleared, and the latest GitHub `main` checks were green.

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

## Current Command Surface

- `mcpforge generate DESCRIPTION`
- `mcpforge update PATH REQUEST`
- `mcpforge validate PATH`
- `mcpforge list [PATH]`
- `mcpforge init NAME`
- `mcpforge version`
- `mcpforge-server`

Note: there is no current `mcpforge inspect` command.

## Verification To Re-Run

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mcpforge validate examples/todo-server
uv build
```

Latest local result on 2026-05-09: the baseline above passed, `uv build` produced the `0.2.0` source distribution and wheel, `uv run pytest` reported 300 passed and 1 skipped, CLI help/version/list smokes passed, all five Python example server test files passed when run from their own example projects, and the TypeScript todo example validated from a temporary copy with 2 tests run and 0 failed. Hosted generation was blocked because `ANTHROPIC_API_KEY` was not available in this shell or the usual local Keychain entries.

Opt-in hosted smoke command:

```bash
MCPFORGE_RUN_HOSTED_SMOKE=1 ANTHROPIC_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py
```

## Remaining Decisions

1. Decide whether to publish/tag the current `0.2.0` state or continue building before release.
2. Run the opt-in hosted `mcpforge generate` smoke with `ANTHROPIC_API_KEY` before making a public release claim.
3. Pick the next feature lane: hosted TypeScript generation smoke, generated-template polish, provider/model controls, or coordination/workflow expansion.

## Best Next Step

Run the release-readiness baseline, then either prepare a release tag or open a focused branch for the next feature lane.
