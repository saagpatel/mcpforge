# mcpforge Current State

Last updated: 2026-05-10

## Big Picture

mcpforge is a Python 3.12+ CLI and MCP server that generates runnable FastMCP 3.x servers from plain-English descriptions. It uses a structured planning stage before code generation, validates LLM output before trusting it, and includes example generated servers for regression coverage.

## Current Repo State

- Branch: `main`
- Remote state: `main` pushed to `origin/main`
- Package version: `0.3.0`
- PyPI distribution name: `fastmcp-builder`
- Import package and commands: `mcpforge`, `mcpforge-server`
- GitHub release: `v0.2.0` exists
- PyPI publish: pending `v0.3.0` release after distribution rename
- Current v0.3 builder lane: merged into `main` after verification
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
- `mcpforge inspect PATH`
- `mcpforge doctor`
- `mcpforge init NAME`
- `mcpforge version`
- `mcpforge-server`

Status-like commands now support `--json` where useful.

## Verification Baseline

Use this baseline before claiming release readiness:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mcpforge validate examples/todo-server
uv build
```

Latest local result on 2026-05-10 after the v0.3 fixture lane:

- `uv run ruff check .`: passed
- `uv run ruff format --check .`: passed
- `uv run pytest -q`: 322 passed, 2 skipped
- `uv run mcpforge validate examples/todo-server`: syntax, lint, import, and 11 tests passed
- `uv build`: built `dist/mcpforge-0.2.0.tar.gz` and `dist/mcpforge-0.2.0-py3-none-any.whl`
- CLI smoke: `mcpforge list examples --recursive --json`, `mcpforge inspect`, and `mcpforge doctor --json` passed
- Python example tests: todo, file-reader, database-query, slack-notifier, and weather examples passed with `uv run --directory ... pytest`
- TypeScript example validation: the `examples/ts-todo-server` path validates from a
  temporary copy and reports 2 tests run, 0 failed
- Discovery smoke: `mcpforge list examples --recursive` now includes the TypeScript todo example
- Hosted generation smoke: passed with `ANTHROPIC_API_KEY` loaded from Keychain
- Hosted TypeScript generation smoke: passed with `ANTHROPIC_API_KEY` loaded from Keychain
- Release-prep cleanup: `AGENTS.md`, `CHANGELOG.md`, `PUBLISHING.md`, and
  packaging metadata were refreshed for `0.2.0`
- GitHub release `v0.2.0`: created on 2026-05-10
- PyPI publish workflow: build and tests passed, publish failed with
  `invalid-publisher` because PyPI has no matching trusted publisher for
  `repo:saagpatel/mcpforge:environment:pypi`
- PyPI trusted-publisher setup attempt: reached
  `https://pypi.org/manage/account/publishing/`, but PyPI required account
  login before a pending publisher could be created
- PyPI trusted-publisher follow-up: account access was verified, PyPI rejected
  the original `mcpforge` project name as too similar to existing projects
  including `mcp-forge` and `mcp-forge-cli`, and a pending trusted publisher was
  registered for `fastmcp-builder` with repository `saagpatel/mcpforge`,
  workflow `publish.yml`, and environment `pypi`

Latest v0.3 feature-lane result on 2026-05-10:

- Added `inspect`, `doctor`, and JSON output surfaces.
- Added MCP server parity for language/template/OpenAPI/multi-file/no-execute/strict/dry-run generation options.
- Added generated `.env.example`, Python `fastmcp.json`, and TypeScript README/env scaffolding.
- Added OpenAPI curation and auth/env operation metadata.
- Added provider abstraction with Anthropic stable and OpenAI planned/gated.
- Added first-class prompt model support, expanded resources, and resource/prompt conformance checks.
- Added live generated fixtures for REST API, filesystem, database, and TypeScript todo profiles.
- Focused feature tests: 182 passed.
- New generated fixture validation:
  - REST API fixture: 33 tests run, 0 failed
  - Filesystem fixture: 48 tests run, 0 failed
  - Database fixture: 49 tests run, 0 failed
  - TypeScript todo fixture: 31 tests run, 0 failed

Latest v0.3 release-prep result on 2026-05-10:

- PyPI pending trusted publisher exists for `fastmcp-builder`.
- `pyproject.toml`: distribution `fastmcp-builder`, version `0.3.0`.
- `src/mcpforge/__init__.py`: CLI/runtime version `0.3.0`.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed.
- `uv run pytest -q`: 322 passed, 2 skipped.
- `uv run mcpforge validate examples/todo-server`: syntax, lint, import, and 11 tests passed.
- `uv build --out-dir /tmp/mcpforge-dist-check --clear`: built
  `fastmcp_builder-0.3.0.tar.gz` and `fastmcp_builder-0.3.0-py3-none-any.whl`.
- Wheel metadata smoke: `Name: fastmcp-builder`, `Version: 0.3.0`.
- Wheel entry point smoke: `mcpforge` and `mcpforge-server` console scripts are present.
- Local wheel install smoke:
  `uvx --from /tmp/mcpforge-dist-check/fastmcp_builder-0.3.0-py3-none-any.whl mcpforge version --json`
  returned `0.3.0`.
- `uv run mcpforge doctor --json`: passed with `mcpforge` package version `0.3.0`.

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

1. Commit the `fastmcp-builder` distribution rename and `0.3.0` version bump.
2. Tag `v0.3.0` and let the `Publish to PyPI` workflow create the first PyPI
   release through the pending trusted publisher.
3. After PyPI publish succeeds, run a clean install smoke:
   `uvx --from fastmcp-builder==0.3.0 mcpforge version`.
4. Continue v0.3 hardening with deeper generated REST client behavior and optional auth/middleware profiles.
