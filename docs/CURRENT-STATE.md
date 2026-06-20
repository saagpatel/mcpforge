# mcpforge Current State

Last updated: 2026-06-20

## Big Picture

mcpforge is a Python 3.12+ CLI and MCP server that generates runnable FastMCP 3.x servers from plain-English descriptions. It uses a structured planning stage before code generation, validates LLM output before trusting it, and includes example generated servers for regression coverage.

## Current Repo State

- Branch: `main`
- Remote state: `main` pushed to `origin/main`
- Package version: `0.3.2`
- PyPI distribution name: `fastmcp-builder`
- Import package and commands: `mcpforge`, `mcpforge-server`
- GitHub release: `v0.3.2` exists (`v0.3.1` prior)
- PyPI publish: `fastmcp-builder==0.3.2` published successfully
- Current follow-up lane: OpenAI structured-output, planning, and generation smoke gates
- Provider matrix runbook: `docs/PROVIDER-MATRIX.md`
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
- Added `docs/PROVIDER-MATRIX.md` to keep local release readiness, hosted
  provider readiness, safe local verification, and approval-required hosted
  smoke commands separated.

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

Latest local result on 2026-05-10 after the OpenAI smoke-gate lane:

- `uv run ruff check .`: passed
- `uv run ruff format --check .`: passed
- `uv run pytest -q`: 347 passed, 6 skipped
- `uv run mcpforge validate examples/todo-server`: syntax, lint, import, and 11 tests passed
- `uv run mcpforge validate examples/v03-authenticated-openapi-server`: syntax, lint, import, and 23 tests passed
- `uv build`: built `dist/fastmcp_builder-0.3.0.tar.gz` and `dist/fastmcp_builder-0.3.0-py3-none-any.whl`
- `scripts/verify_clean_install.sh`: passed and reported `mcpforge 0.3.0`
- Hosted Anthropic Python, TypeScript, and authenticated OpenAPI smokes: 3 passed, 3 skipped
- OpenAI hosted structured-output, planning, and generation smokes: present, skipped until `OPENAI_API_KEY` is set
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
- Added OpenAPI path/query/header/cookie/body parameter-location metadata, auth placement metadata, request timeout env metadata, retry-safety hints, and `httpx` package metadata.
- Added optional Python `--auth-profile` and repeatable `--middleware-profile` generation flags for API-key/JWT auth metadata and logging/timing/rate-limit middleware profiles.
- Added `scripts/verify_clean_install.sh` for clean wheel install/run verification.
- Added regression checks for committed v0.3 generated fixtures.
- Added provider abstraction with Anthropic stable and OpenAI planned/gated.
- Added first-class prompt model support, expanded resources, and resource/prompt conformance checks.
- Added live generated fixtures for REST API, filesystem, database, and TypeScript todo profiles.
- Added hosted authenticated OpenAPI generation smoke coverage and a live authenticated OpenAPI fixture with header API-key auth, request timeout/env docs, and local mocked HTTP tests.
- Added deterministic structured-output smoke tests for `generate_json`: temperature-zero calls,
  fenced JSON parsing, Pydantic schema validation, and malformed-output failure handling.
- Added an OpenAI structured-output client plus opt-in hosted structured-output, planning,
  and generation smokes while keeping full OpenAI generation gated by default.
- Added remote MCP readiness docs/config profiles and inspection readiness signals.
- Expanded OpenAPI planning with richer response schema summaries, non-2xx error cases,
  OAuth token placeholder guidance, and pagination context.
- Switched OpenAPI generated test suites to deterministic local `httpx.AsyncClient`
  fakes so hosted OpenAPI validation no longer depends on LLM-written mock code.
- Focused feature tests: 182 passed.
- New generated fixture validation:
  - REST API fixture: 33 tests run, 0 failed
  - Filesystem fixture: 48 tests run, 0 failed
  - Database fixture: 49 tests run, 0 failed
  - TypeScript todo fixture: 31 tests run, 0 failed
  - Authenticated OpenAPI fixture: 23 tests run, 0 failed

Latest v0.3 release-prep result on 2026-05-10:

- PyPI pending trusted publisher exists for `fastmcp-builder`.
- `pyproject.toml`: distribution `fastmcp-builder`, version `0.3.0`.
- `src/mcpforge/__init__.py`: CLI/runtime version `0.3.0`.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed.
- `uv run pytest -q`: 337 passed, 3 skipped.
- `uv run mcpforge validate examples/todo-server`: syntax, lint, import, and 11 tests passed.
- `uv run mcpforge validate examples/v03-authenticated-openapi-server`: syntax, lint, import, and 23 tests passed.
- `uv build --out-dir /tmp/mcpforge-dist-check --clear`: built
  `fastmcp_builder-0.3.0.tar.gz` and `fastmcp_builder-0.3.0-py3-none-any.whl`.
- Wheel metadata smoke: `Name: fastmcp-builder`, `Version: 0.3.0`.
- Wheel entry point smoke: `mcpforge` and `mcpforge-server` console scripts are present.
- Local wheel install smoke:
  `uvx --from /tmp/mcpforge-dist-check/fastmcp_builder-0.3.0-py3-none-any.whl mcpforge version --json`
  returned `0.3.0`.
- `uv run mcpforge doctor --json`: passed with `mcpforge` package version `0.3.0`.
- GitHub release `v0.3.0`: created on 2026-05-10.
- PyPI publish workflow for tag `v0.3.0`: passed on 2026-05-10.
- PyPI JSON verification: `fastmcp-builder` reports version `0.3.0` with wheel
  and sdist files.
- Clean PyPI install smoke:
  `uvx --from fastmcp-builder==0.3.0 mcpforge version --json` returned `0.3.0`.

Latest follow-up hardening result on 2026-05-10:

- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed.
- `uv run pytest -q`: 347 passed, 6 skipped.
- `uv run mcpforge validate examples/todo-server`: syntax, lint, import, and 11 tests passed.
- `uv run mcpforge validate examples/v03-authenticated-openapi-server`: syntax, lint, import, and 23 tests passed.
- `uv run mcpforge inspect examples/v03-authenticated-openapi-server --json`: remote MCP readiness reported `ready: true`.
- FastMCP HTTP smoke against `examples/v03-authenticated-openapi-server/fastmcp.json`: server started on a local test port with env vars set.
- `uv build`: built `fastmcp_builder-0.3.0` source distribution and wheel.
- `scripts/verify_clean_install.sh`: passed and reported `mcpforge 0.3.0`.
- Hosted Anthropic Python, TypeScript, and authenticated OpenAPI smokes: 3 passed, 3 OpenAI smokes skipped.
- Hosted OpenAI structured-output, planning, and generation smokes: added but skipped because `OPENAI_API_KEY` is not set in this environment.

Latest provider-matrix retry on 2026-05-10:

- `OPENAI_API_KEY` is not available in the shell or under the checked common Keychain service names (`OPENAI_API_KEY`, `openai_api_key`, `openai`, `OPENAI`), so the OpenAI structured-output, planning, and generation smokes still skip.
- `ANTHROPIC_API_KEY` is available from Keychain, but hosted Anthropic Python, TypeScript, and authenticated OpenAPI smokes now fail before generation because the Anthropic API returns `Your credit balance is too low to access the Anthropic API`.
- No OpenAI ungating happened. The provider remains gated by default until the OpenAI smoke trio passes with a real key and the Anthropic release matrix is green again.

Latest v0.3.2 release result on 2026-06-20:

- PR `#38` merged the `0.3.2` release prep to `main`.
- Git tag `v0.3.2` points at the merge commit on `main`.
- GitHub Actions `Publish to PyPI` completed successfully for tag `v0.3.2`.
- PyPI verification: `fastmcp-builder==0.3.2` is installable from PyPI.
- Clean PyPI install smoke:
  `uvx --from fastmcp-builder==0.3.2 mcpforge version` returned `mcpforge 0.3.2`.
- Forcing reason: removed a personal email address from published package
  metadata (`[project.authors]`); PyPI metadata is immutable, so a new release
  was required to correct the public project page.
- Currency: bumped the `fastmcp` floor to `>=3.4.2` and revalidated generated
  server shape (347 repo tests + all 9 example suites) with no live generation.
- Hosted provider smokes were intentionally not run for this release; they
  remain opt-in and approval-gated.

Latest v0.3.1 patch release result on 2026-06-19:

- PR `#32` merged the `0.3.1` release prep to `main`.
- Git tag `v0.3.1` points at the merge commit on `main`.
- GitHub Actions `Publish to PyPI` completed successfully for tag `v0.3.1`.
- PyPI verification: `fastmcp-builder==0.3.1` reports wheel and source distribution files.
- Clean PyPI install smoke:
  `uvx --from fastmcp-builder==0.3.1 mcpforge version --json` returned `0.3.1`.
- Hosted provider smokes were intentionally not run for this patch release; they remain opt-in and approval-gated.

Opt-in hosted smoke commands:

See `docs/PROVIDER-MATRIX.md` for the current provider gate matrix, safe local
verification commands, and hosted-smoke approval rules.

```bash
MCPFORGE_RUN_HOSTED_SMOKE=1 ANTHROPIC_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py
MCPFORGE_RUN_HOSTED_TS_SMOKE=1 ANTHROPIC_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_generate_typescript_echo_server
MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE=1 ANTHROPIC_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_generate_openapi_auth_server
MCPFORGE_RUN_HOSTED_OPENAI_SMOKE=1 OPENAI_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_structured_output_smoke
MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE=1 OPENAI_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_planning_smoke
MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE=1 MCPFORGE_ENABLE_OPENAI_PROVIDER=1 OPENAI_API_KEY=... uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_generate_echo_server
```

Hosted generation with a real `ANTHROPIC_API_KEY` passed on 2026-05-10, including the authenticated OpenAPI smoke.
The OpenAI hosted structured-output, planning, and generation smokes are present but
still require `OPENAI_API_KEY` for live verification in this environment.

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
- The TypeScript and authenticated OpenAPI generation paths are covered by real-key smokes.
- Full OpenAI provider generation remains gated by default. The real CLI path can only
  be exercised for smokes with `MCPFORGE_ENABLE_OPENAI_PROVIDER=1`.

## Recommended Next Moves

1. Add `OPENAI_API_KEY` to this execution environment or Keychain under `OPENAI_API_KEY`, then run the opt-in OpenAI structured-output, planning, and generation hosted smokes.
2. Replenish Anthropic API credits and rerun the hosted Anthropic Python, TypeScript, and authenticated OpenAPI smoke matrix.
3. Move OpenAI out of gated status only after all OpenAI hosted smokes pass repeatedly and the Anthropic release matrix is green again.
4. Use `docs/PROVIDER-MATRIX.md` as the release-gate checklist for any next
   provider-matrix audit or publish decision.
