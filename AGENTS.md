# AGENTS.md

## What This Project Is

`mcpforge` is a Python 3.12+ CLI and MCP server that generates runnable FastMCP servers from plain-English descriptions, then validates generated projects before they are trusted.

## Current State

Use `docs/PROVIDER-MATRIX.md` for hosted-provider readiness, `CHANGELOG.md` for release history, and live git/package state for current release context before acting.

## Stack

- Python 3.12+
- FastMCP
- `uv`
- pytest
- ruff
- Generated Python and TypeScript MCP server examples

## Working and completion

- Own the requested outcome through implementation, appropriate verification, and authorized delivery; do not stop at a plan or a partial first step.
- Inspect the actual checkout, branch, relevant files, and applicable instructions before editing. Preserve unrelated work and existing branches.
- Make reasonable, reversible decisions within scope without repeated questions. Ask only when a missing answer is necessary to preserve the user's intent or authority.
- Continue independent authorized work when one step is blocked, and report actual blockers clearly.
- Verify actual results with the smallest meaningful check, then the required baseline. Distinguish local or Cloud tests from hosted-provider, deployment, or production proof.
- When authorized, finish committing on a task branch, pushing, and opening a PR; verify the remote branch and PR. Merge, publish, deploy, or widen access only with explicit authorization.

## How To Run

Core verification baseline:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mcpforge validate examples/todo-server
uv build
```

Use hosted generation smoke tests only when the task explicitly authorizes the required provider credentials.

## Cursor Cloud specific instructions

- `.cursor/environment.json` is the repo-local Cloud environment definition; it runs `.cursor/install.sh` during each Build.
- The Cloud setup pins Python `3.12.13` and uv `0.12.12`, installs dependencies with the tracked `uv.lock`, and runs non-hosted lint, format, test, and package-build checks.
- Do not copy local `.env` files, provider keys, keychains, browser profiles, or other credentials into a Cloud environment. Add any explicitly authorized provider secrets through Cursor's environment-scoped Secrets settings.
- Hosted generation smoke tests are intentionally not part of the baseline Build because they require external provider credentials and network access.

## Codex Cloud specific instructions

- Follow automatically supplied working instructions and any referenced reusable startup guide before development commands. Use the existing isolated task checkout; an extra worktree is not needed by default.
- Prepared Cloud startup governs dependency preparation and does not prohibit authorized source edits or commits. Follow its conditional installation refresh without upgrading dependencies or changing locks to bypass startup problems.
- Local configuration, tools, credentials, browser sign-ins, and services do not automatically transfer. Verify available capabilities; select parent model and reasoning in the Cloud product UI rather than inventing local configuration knobs.
- Preserve Cloud network, privacy, approval, and secret settings. Keep hosted opt-ins disabled for the credential-free baseline, and keep machine-specific infrastructure, personal memory, and secrets out of the repository.

## Known Risks

- Generated MCP servers can widen local tool reach; validate generated code before installing or wiring it into clients.
- Do not read provider keys, `.env` files, keychains, OAuth stores, browser profiles, raw logs, private transcripts, or credential-bearing configs.
- Keep PyPI/package naming, release state, and docs/template drift synchronized before any publish framing.

## Next Recommended Move

For this repo, first decide publish/park or active follow-up status, then verify the provider matrix, changelog, package metadata, and live git before doing feature work.
