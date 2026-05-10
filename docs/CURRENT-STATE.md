# mcpforge Current State

Last updated: 2026-05-10

## Big Picture

mcpforge is a Python 3.12+ CLI and MCP server that generates runnable FastMCP 3.x servers from plain-English descriptions. It uses a structured planning stage before code generation, validates LLM output before trusting it, and includes example generated servers for regression coverage.

## Current Repo State

- Branch: `main`
- Remote state: `main` pushed to `origin/main`
- Package version: `0.2.0`
- GitHub PR queue: cleared during the latest cleanup pass
- Dependabot alerts: cleared during the latest cleanup pass
- CI posture: green on the latest pushed `main`
- Local test posture: green on the latest cleanup pass

## What Was Just Completed

- Fixed generated example servers so validation failures are real and actionable instead of hidden behind FastMCP error-shape mismatches.
- Updated validation result handling so executed test failures make CLI and MCP validation outputs fail truthfully.
- Adjusted the macOS sandbox profile so pytest can initialize normally in sandboxed validation.
- Removed duplicate PR template casing that caused Git/PR confusion on macOS.
- Updated CI to the supported Python 3.12 line.
- Folded in Dependabot package and GitHub Actions updates.
- Refreshed root and todo-example lockfiles for security fixes.
- Closed stale or superseded Dependabot PRs after their changes were covered on `main`.
- Hardened the TypeScript validation path so Vitest test counts are reported from the
  actual test summary, and removed a duplicate `npm install` from the TypeScript CLI flow.
- Added TypeScript-generated project metadata so `mcpforge list` can discover
  TypeScript servers alongside Python servers.
- Tightened hosted TypeScript test generation so generated Vitest suites handle
  strict MCP result typing, then verified the hosted `--language typescript` path.

## Current Command Surface

- `mcpforge generate DESCRIPTION`
- `mcpforge update PATH REQUEST`
- `mcpforge validate PATH`
- `mcpforge list [PATH]`
- `mcpforge init NAME`
- `mcpforge version`
- `mcpforge-server`

There is no current `mcpforge inspect` command. Older docs that mention it should be treated as stale.

## Verification Baseline

Use this baseline before claiming release readiness:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mcpforge validate examples/todo-server
uv build
```

Latest local result on 2026-05-10:

- `uv run ruff check .`: passed
- `uv run ruff format --check .`: passed
- `uv run pytest`: 300 passed, 2 skipped
- `uv run mcpforge validate examples/todo-server`: syntax, lint, import, and 11 tests passed
- `uv build`: built `dist/mcpforge-0.2.0.tar.gz` and `dist/mcpforge-0.2.0-py3-none-any.whl`
- CLI smoke: `mcpforge --help`, `mcpforge version`, and `mcpforge list examples --recursive` passed
- Python example tests: todo, file-reader, database-query, slack-notifier, and weather examples passed with `uv run --directory ... pytest`
- TypeScript example validation: the `examples/ts-todo-server` path validates from a
  temporary copy and reports 2 tests run, 0 failed
- Discovery smoke: `mcpforge list examples --recursive` now includes the TypeScript todo example
- Hosted generation smoke: passed with `ANTHROPIC_API_KEY` loaded from Keychain
- Hosted TypeScript generation smoke: passed with `ANTHROPIC_API_KEY` loaded from Keychain

Opt-in hosted smoke command:

```bash
MCPFORGE_RUN_HOSTED_SMOKE=1 ANTHROPIC_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py
```

Hosted generation with a real `ANTHROPIC_API_KEY` passed on 2026-05-10.

Optional broader generated-example checks:

```bash
uv run --directory examples/todo-server pytest
uv run --directory examples/file-reader-server pytest
uv run --directory examples/database-query-server pytest
uv run --directory examples/slack-notifier-server pytest
uv run --directory examples/weather-server pytest
```

## Known Risks

- Provider/model behavior is sensitive: do not change the default model or structured JSON generation path without deterministic evidence.
- Generated templates and prompt contracts are high-impact surfaces; use a dedicated worktree before changing them.
- The TypeScript generation path is now covered by a real-key smoke, but provider/model
  behavior still needs deterministic evidence before any provider expansion.

## Recommended Next Moves

1. Decide whether this verified `0.2.0` state is a publish/tag moment or a continue-building moment.
2. If releasing, tag/publish `0.2.0` from the current green `main`.
3. If continuing, prioritize one focused lane:
   - generated-template polish,
   - provider/model controls,
   - or richer coordination/workflow features.
